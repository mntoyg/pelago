"""Open question 13: week-to-week agreement of the cell ranking under (a) today's weights, (b) a lower front weight, (c) the front
smoothed over several days. Same metrics as REVIEW-004: Spearman, share of the top 20% that stays, against 20% for a random map.

The default weights in the area config are NOT changed here: a variant is a copy of the parameters inside this module.
Numbers only. High agreement means calm maps, not correct maps.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from fsi.config import SUBSCORES, FsiParams
from fsi.model import CellInputs, score_area
from ingest.timeutil import parse_utc

from . import checks
from .front_check import fetch_field
from .inputs import PoliteHttp, check_cache_dir

RANDOM_TOP20 = 0.2     # the share of the top 20% that a map with no skill would keep


def weights_variant(p: FsiParams, front_factor: float | None = None, only: tuple[str, ...] | None = None) -> FsiParams:
    """A copy of p with the front weight multiplied, or with every weight outside `only` set to 0 (references)."""
    w = dict(p.weights)
    if front_factor is not None:
        w["front"] = w["front"] * front_factor
    if only is not None:
        w = {k: (v if k in only else 0.0) for k, v in w.items()}
    return replace(p, weights=w)


def strip_chlorophyll(history: dict[date, list[CellInputs]]) -> dict[date, list[CellInputs]]:
    return {d: [replace(c, chl_mg_m3=None, chl_observed_at=None, chl_product=None) for c in cells] for d, cells in history.items()}


def week_pairs(dates, gap: int = 7) -> list[tuple[date, date]]:
    ds = sorted(set(dates))
    return [(a, a + timedelta(days=gap)) for a in ds if a + timedelta(days=gap) in set(ds)]


def spread_pairs(pairs: list[tuple[date, date]], n: int) -> list[tuple[date, date]]:
    """n pairs spread evenly over the list (the first and the last included when n >= 2)."""
    if n >= len(pairs):
        return list(pairs)
    idx = sorted({round(i * (len(pairs) - 1) / (n - 1)) for i in range(n)}) if n > 1 else [0]
    return [pairs[i] for i in idx]


def window_days(d: date, k: int) -> list[date]:
    """The k days ending on d, oldest first."""
    if k < 1:
        raise ValueError("window length must be at least 1")
    return [d - timedelta(days=i) for i in range(k - 1, -1, -1)]


def check_no_overlap(d1: date, d2: date, k: int) -> None:
    """The two windows of a pair must not share a day: otherwise the agreement between the two maps is partly the same data twice."""
    if set(window_days(d1, k)) & set(window_days(d2, k)):
        raise ValueError("the smoothing windows of the two dates overlap")


def smooth_front(cells: list[CellInputs], daily: list[dict[int, float | None]]) -> list[CellInputs]:
    """Replace each cell's gradient with the mean of the gradients that exist in the window. A day without a value is left out of the
    mean, never counted as 0. The SST value, its date and every other input are unchanged."""
    out = []
    for c in cells:
        vals = [g[c.cell_id] for g in daily if g.get(c.cell_id) is not None and np.isfinite(g[c.cell_id])]
        out.append(replace(c, sst_grad_c_per_km=float(np.mean(vals)) if vals and c.sst_c is not None else None))
    return out


# -- daily SST (live, cached outside the repository) ----------------------------------------------------------------------
def fetch_sst_day(area, d: date, cache_dir: Path, http: PoliteHttp | None, log=print):
    """({cell_id: gradient or None}, observed_at, http). From the cache when present; None http means offline (cache only)."""
    cache = check_cache_dir(cache_dir) / area.area_id
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f"{d.isoformat()}.json"
    if f.exists():
        j = json.loads(f.read_text(encoding="utf-8"))
        return {int(k): v for k, v in j["grad"].items()}, parse_utc(j["observed_at"]), http
    if http is None:
        return None, None, http
    rows, observed, _field, http = fetch_field(area, d, http)
    grad = {r.cell_id: r.extra.get("grad_c_per_km") for r in rows}
    f.write_text(json.dumps({"observed_at": observed.isoformat(), "grad": {str(k): v for k, v in grad.items()}}), encoding="utf-8")
    log(f"{d}: observed {observed:%Y-%m-%d %H:%MZ} (requests so far {http.count})")
    return grad, observed, http


# -- metrics ---------------------------------------------------------------------------------------------------------------
def pair_metrics(scored: dict[date, list], pairs: list[tuple[date, date]]) -> list[dict]:
    rows = []
    for a, b in pairs:
        va = {s.cell_id: s.fsi for s in scored[a] if s.fsi is not None}
        vb = {s.cell_id: s.fsi for s in scored[b] if s.fsi is not None}
        common = sorted(set(va) & set(vb))
        if len(common) < 3:
            continue
        rows.append({"from": a, "to": b, "cells": len(common),
                     "spearman": checks.spearman([va[c] for c in common], [vb[c] for c in common]),
                     "top20_kept": checks.overlap(checks.top_set({c: va[c] for c in common}), checks.top_set({c: vb[c] for c in common})),
                     "mean_abs_change": float(np.mean([abs(va[c] - vb[c]) for c in common]))})
    return rows


def summarise(rows: list[dict]) -> dict:
    out = {"pairs": len(rows)}
    for k in ("spearman", "top20_kept", "mean_abs_change"):
        v = [r[k] for r in rows if r[k] is not None]
        out[k] = statistics.fmean(v) if v else None
        out[k + "_se"] = (statistics.stdev(v) / len(v) ** 0.5) if len(v) > 1 else None
    out["undefined_spearman"] = sum(r["spearman"] is None for r in rows)
    return out


def score_variant(history: dict[date, list[CellInputs]], p: FsiParams, level: str = "trial") -> dict[date, list]:
    return {d: score_area(cells, d, p, level) for d, cells in history.items()}


def gradient_spearman(g1: dict[int, float | None], g2: dict[int, float | None]) -> float | None:
    """Rank correlation of two cell gradient maps over the cells that have a value in both (None when undefined)."""
    common = sorted(c for c in g1 if g1[c] is not None and g2.get(c) is not None)
    return checks.spearman([g1[c] for c in common], [g2[c] for c in common])


def mean_defined(xs) -> float | None:
    v = [x for x in xs if x is not None]
    return statistics.fmean(v) if v else None
