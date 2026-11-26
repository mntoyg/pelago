"""Historical inputs for the back-test: the SAME fetchers the daily ingest uses, called for past dates, kept in memory and in a
JSON cache OUTSIDE the repository. Nothing here writes to the database and nothing downloaded is committed.

Politeness and limits (PM decision 9): NOAA ERDDAP only (SST, chlorophyll; depth is static and fetched once), at most
`max_requests` requests in total (counted), at least `pause_s` seconds between two requests, the ingest's generic User-Agent.
"""
from __future__ import annotations

import json
import time as _time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from fsi.model import CellInputs
from ingest.fetchers import registry
from ingest.fetchers.base import FetchError, HttpGet, Row, http_get
from ingest.pipeline import validate_rows
from ingest.timeutil import parse_utc

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_VERSION = 1


class RequestCap(Exception):
    """The request budget is used up: stop, report what was done, never go on."""


class PoliteHttp:
    """Counts requests, refuses past the cap, and keeps at least pause_s seconds between two requests."""
    def __init__(self, inner: HttpGet = http_get, max_requests: int = 250, pause_s: float = 2.0,
                 clock: Callable[[], float] = _time.monotonic, sleep: Callable[[float], None] = _time.sleep):
        if max_requests < 0 or pause_s < 0:
            raise ValueError("max_requests and pause_s must not be negative")
        self.inner, self.cap, self.pause, self.clock, self.sleep = inner, max_requests, pause_s, clock, sleep
        self.count, self._last = 0, None

    def __call__(self, url: str, timeout: float) -> bytes:
        if self.count >= self.cap:
            raise RequestCap
        if self._last is not None:
            wait = self.pause - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self.count += 1
        self._last = self.clock()
        return self.inner(url, timeout)


def check_cache_dir(cache_dir: Path) -> Path:
    """The cache holds raw upstream values and must never end up in git: refuse a folder inside this repository."""
    p = cache_dir.resolve()
    if p == REPO_ROOT or REPO_ROOT in p.parents:
        raise ValueError("the cache folder must be outside the repository")
    return p


def weekly_dates(end: date, count: int, step_days: int = 7) -> list[date]:
    """`count` dates ending at `end`, `step_days` apart, ordered so that stopping early still leaves an even spread over the
    year: every 4th date first, then the ones halfway between, then the rest."""
    ds = [end - timedelta(days=step_days * i) for i in range(count)]
    order = sorted(range(count), key=lambda i: (i % 4 != 0, i % 2 != 0, i))
    return [ds[i] for i in order]


def _ser(c: CellInputs) -> dict:
    iso = lambda t: None if t is None else t.isoformat()
    return {"cell_id": c.cell_id, "sst_c": c.sst_c, "sst_observed_at": iso(c.sst_observed_at), "sst_grad_c_per_km": c.sst_grad_c_per_km,
            "chl_mg_m3": c.chl_mg_m3, "chl_observed_at": iso(c.chl_observed_at), "chl_product": c.chl_product, "depth_m": c.depth_m}


def _de(d: dict) -> CellInputs:
    t = lambda s: None if s is None else parse_utc(s)
    return CellInputs(d["cell_id"], d["sst_c"], t(d["sst_observed_at"]), d["sst_grad_c_per_km"], d["chl_mg_m3"],
                      t(d["chl_observed_at"]), d["chl_product"], d["depth_m"])


def _rows(area, variable: str, run_date: date, http: HttpGet, no_sleep) -> tuple[list[Row] | None, str | None]:
    """Same order as ingest.pipeline for one attempt per source: primary, then fallback. (rows, None) or (None, last code)."""
    code = "error"
    for ref in area.chain(variable):
        try:
            rows = registry.build(ref.source_id, area, http=http, sleep=no_sleep).fetch(area, run_date)
            validate_rows(variable, rows, area.cell_ids())
            return rows, None
        except FetchError as exc:
            code = exc.code
    return None, code


def fetch_depth(area, run_date: date, http: HttpGet) -> dict[int, float | None]:
    rows, code = _rows(area, "depth", run_date, http, lambda s: None)
    if rows is None:
        raise RuntimeError(f"depth could not be fetched ({code})")
    return {r.cell_id: r.value for r in rows}


def fetch_date(area, d: date, http: HttpGet, depth: dict[int, float | None]) -> dict:
    """{'cells': [...], 'codes': {'sst': code|None, 'chl': code|None}}. A variable that failed leaves its inputs None."""
    no_sleep = lambda s: None
    sst, c_sst = _rows(area, "sst", d, http, no_sleep)
    chl, c_chl = _rows(area, "chl", d, http, no_sleep)
    by_sst = {r.cell_id: r for r in sst or []}
    by_chl = {r.cell_id: r for r in chl or []}
    cells = []
    for cid in area.cell_ids():
        s, c = by_sst.get(cid), by_chl.get(cid)
        cells.append(CellInputs(cid, s.value if s else None, s.observed_at if s else None,
                                (s.extra.get("grad_c_per_km") if s else None), c.value if c else None,
                                c.observed_at if c else None, (c.product or "daily") if c and c.value is not None else None,
                                depth.get(cid)))
    return {"cells": cells, "codes": {"sst": c_sst, "chl": c_chl}}


def load_history(area, dates: list[date], cache_dir: Path, http: PoliteHttp | None, log=print) -> tuple[dict, dict]:
    """Returns ({date: [CellInputs]}, {'fetched': n, 'from_cache': n, 'failed': {date: codes}, 'stopped_by_cap': bool}).
    http=None means offline: only the cache is used."""
    cache = check_cache_dir(cache_dir) / area.area_id
    cache.mkdir(parents=True, exist_ok=True)
    stats = {"fetched": 0, "from_cache": 0, "failed": {}, "stopped_by_cap": False, "requests": 0}
    depth_file = cache / "depth.json"
    depth = None
    if depth_file.exists():
        depth = {int(k): v for k, v in json.loads(depth_file.read_text(encoding="utf-8"))["depth"].items()}
    out: dict[date, list[CellInputs]] = {}
    for d in dates:
        f = cache / f"{d.isoformat()}.json"
        if f.exists():
            j = json.loads(f.read_text(encoding="utf-8"))
            if j.get("version") == CACHE_VERSION:
                out[d] = [_de(x) for x in j["cells"]]
                stats["from_cache"] += 1
                if any(j["codes"].values()):
                    stats["failed"][d] = j["codes"]
                continue
        if http is None:
            continue
        try:
            if depth is None:
                depth = fetch_depth(area, d, http)
                depth_file.write_text(json.dumps({"version": CACHE_VERSION, "depth": {str(k): v for k, v in depth.items()}}), encoding="utf-8")
            r = fetch_date(area, d, http, depth)
        except RequestCap:
            stats["stopped_by_cap"] = True
            log(f"request cap reached before {d}; stopping")
            break
        if any(c and FetchError(c).retryable for c in r["codes"].values()):
            stats["failed"][d] = r["codes"]            # a network error says nothing about the data: not cached, not scored
            log(f"{d}: transient failure {r['codes']}; left out")
            continue
        f.write_text(json.dumps({"version": CACHE_VERSION, "codes": r["codes"], "cells": [_ser(c) for c in r["cells"]]}), encoding="utf-8")
        out[d] = r["cells"]
        stats["fetched"] += 1
        if any(r["codes"].values()):
            stats["failed"][d] = r["codes"]
        log(f"{d}: sst={r['codes']['sst'] or 'ok'} chl={r['codes']['chl'] or 'ok'} (requests so far {http.count})")
    stats["requests"] = http.count if http else 0
    return out, stats
