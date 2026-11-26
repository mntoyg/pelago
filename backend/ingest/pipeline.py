"""Order of work per variable (README section 4): retry the primary, then the next fetcher of the chain, then keep the
latest stored data with its age (S p.5). Every attempt is one job_runs row with a short error_code only."""
from __future__ import annotations

import logging
import math
import time as _time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from .db import AttemptLimit, Writer
from .fetchers import registry
from .fetchers.base import FetchError, Row
from .timeutil import UTC, local_date_of

log = logging.getLogger("ingest")
VARIABLES = ("sst", "chl", "depth", "wave_wind")
# plausible ranges: tighter than nothing, looser than the CHECK constraints in schema.sql (which are the second line)
RANGES = {"value": {"sst": (-2.0, 40.0), "chl": (0.0, 1000.0), "depth": (0.0, 12000.0), "wave_wind": (0.0, 30.0)},
          "grad_c_per_km": (0.0, 100.0), "wind_kmh": (0.0, 400.0)}
# carried-forward data older than this many days is not worth keeping (it would be expired anyway)
_MAX_AGE_KEY = {"sst": "sst", "chl": "chl"}
CARRY_FORWARD = ("sst", "chl", "depth")   # wave/wind is a window maximum for ONE local date and is never carried


@dataclass
class VariableResult:
    variable: str
    status: str              # success | partial | failed
    source_id: str | None
    role: str | None
    cells_with_value: int
    error_code: str | None


def validate_rows(variable: str, rows: list[Row], expected_cells: list[int]) -> None:
    """Raises FetchError('bad_shape' | 'bad_value'). Nothing out of range or non-finite reaches the database."""
    if sorted(r.cell_id for r in rows) != sorted(expected_cells):
        raise FetchError("bad_shape")            # missing, duplicated or foreign cells
    lo, hi = RANGES["value"][variable]
    for r in rows:
        checks = [(r.value, lo, hi)]
        if variable == "sst":
            checks.append((r.extra.get("grad_c_per_km"), *RANGES["grad_c_per_km"]))
        if variable == "wave_wind":
            checks.append((r.extra.get("wind_kmh"), *RANGES["wind_kmh"]))
        for v, a, b in checks:
            if v is None:
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not a <= v <= b:
                raise FetchError("bad_value")
        if r.value is not None and variable != "depth" and (r.observed_at is None or r.observed_at.tzinfo is None):
            raise FetchError("bad_value")        # a value without its own UTC observation time is not stored
        if variable == "sst" and r.value is None and r.extra.get("grad_c_per_km") is not None:
            raise FetchError("bad_value")


def _counts(rows: list[Row]) -> dict:
    return {"cells_total": len(rows), "cells_with_value": sum(1 for r in rows if r.value is not None)}


def _data_date(rows: list[Row], tz: str) -> date | None:
    ts = [r.observed_at for r in rows if r.observed_at is not None]
    return local_date_of(max(ts), tz) if ts else None


def ingest_variable(area, run_date: date, variable: str, w: Writer, factory: Callable = registry.build,
                    sleep: Callable[[float], None] = _time.sleep, backoff_s: float = 2.0) -> VariableResult:
    last_code = "error"
    for ref in area.chain(variable):
        try:
            fetcher = factory(ref.source_id, area)
        except FetchError as exc:                # unknown source, or a licence route that does not allow it
            last_code = exc.code
            _record_failure(w, area, run_date, variable, ref, exc.code)
            continue
        for attempt in range(1, area.retries + 1):
            try:
                run_id, _n = w.start_run(area.area_id, run_date, variable, ref.source_id, ref.role)
            except AttemptLimit:
                last_code = "attempt_limit"
                break
            try:
                rows = fetcher.fetch(area, run_date)
                validate_rows(variable, rows, area.cell_ids())
            except FetchError as exc:
                code, retryable = exc.code, exc.retryable
            except Exception as exc:             # a bug in a fetcher must not stop the other variables
                log.error("fetcher %s crashed: %s", ref.source_id, type(exc).__name__)
                code, retryable = "internal_error", False
            else:
                try:
                    n = w.write_rows(area.area_id, run_date, variable, rows, run_id)
                except Exception as exc:
                    log.error("write failed: %s", type(exc).__name__)
                    w.finish_run(run_id, "failed", 0, None, "write_failed", {})
                    last_code = "write_failed"
                    return VariableResult(variable, "failed", ref.source_id, ref.role, 0, "write_failed")
                c = _counts(rows)
                w.finish_run(run_id, "success", n, _data_date(rows, area.timezone), None, c)
                return VariableResult(variable, "success", ref.source_id, ref.role, c["cells_with_value"], None)
            w.finish_run(run_id, "failed", 0, None, code, {})
            last_code = code
            log.warning("%s via %s attempt %d failed: %s", variable, ref.source_id, attempt, code)
            if not retryable:
                break
            if attempt < area.retries:
                sleep(backoff_s * attempt)
    return _carry_forward(area, run_date, variable, w, last_code)


def _record_failure(w: Writer, area, run_date, variable, ref, code: str) -> None:
    try:
        run_id, _ = w.start_run(area.area_id, run_date, variable, ref.source_id, ref.role)
    except AttemptLimit:
        return
    w.finish_run(run_id, "failed", 0, None, code, {})


def _carry_forward(area, run_date: date, variable: str, w: Writer, last_code: str) -> VariableResult:
    """Every fetcher failed: keep the newest earlier values with THEIR OWN observation time, so their age grows and the
    freshness weight falls (S p.5). Wave/wind is never carried (a window maximum belongs to one date)."""
    old = w.latest_before(area.area_id, run_date, variable) if variable in CARRY_FORWARD else []
    limit = area.max_age_days.get(_MAX_AGE_KEY.get(variable, ""), {}).get("max") if variable in _MAX_AGE_KEY else None
    if limit is not None:
        oldest = run_date - timedelta(days=limit)
        old = [r for r in old if r.observed_at is not None and local_date_of(r.observed_at, area.timezone) >= oldest]
    if not old:
        return VariableResult(variable, "failed", None, None, 0, last_code)
    by_cell = {r.cell_id: r for r in old}
    rows = [by_cell.get(c) or Row(c, None, None, old[0].source_id) for c in area.cell_ids()]
    src = old[0].source_id
    try:
        run_id, _ = w.start_run(area.area_id, run_date, variable, src, "fallback")
    except AttemptLimit:
        return VariableResult(variable, "failed", None, None, 0, "attempt_limit")
    try:
        validate_rows(variable, rows, area.cell_ids())
        n = w.write_rows(area.area_id, run_date, variable, rows, run_id)
    except Exception as exc:
        log.error("carry-forward failed: %s", type(exc).__name__)
        w.finish_run(run_id, "failed", 0, None, "write_failed", {})
        return VariableResult(variable, "failed", src, "fallback", 0, "write_failed")
    c = _counts(rows)
    c["carried_forward"] = True
    w.finish_run(run_id, "partial", n, _data_date(rows, area.timezone), last_code, c)
    return VariableResult(variable, "partial", src, "fallback", c["cells_with_value"], last_code)


def run_ingest(area, run_date: date, w: Writer, factory: Callable = registry.build,
               sleep: Callable[[float], None] = _time.sleep) -> list[VariableResult]:
    if not w.try_lock(area.area_id, run_date):
        raise RuntimeError("another ingest for this area and date is running")
    w.ensure_region(area)
    return [ingest_variable(area, run_date, v, w, factory, sleep) for v in VARIABLES]
