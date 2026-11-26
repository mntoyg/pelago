"""One pick run for one area and local date: for each boat class choose the spots from eligible, scored cells and store them.

Needs the mask and FSI rows of the same date. With fewer than MIN_PICKS spots the run is 'partial' (error_code few_picks, or
no_picks when there are none): fewer than three honest spots are stored, the list is never padded with cells that are not eligible.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import psycopg

from fsi.config import FsiParams
from ingest.config import AreaConfig, ConfigError
from .db import AttemptLimit, PickStore
from .select import MAX_PICKS, MIN_PICKS, pick

log = logging.getLogger("pick")


@dataclass
class PickResult:
    status: str                        # success | partial | failed
    error_code: str | None
    picks: dict[str, int] = field(default_factory=dict)       # boat class -> number of spots stored


def run_pick(area: AreaConfig, run_date: date, store: PickStore, boat_classes=("small",)) -> PickResult:
    boat_classes = list(boat_classes)
    if not boat_classes or len(set(boat_classes)) != len(boat_classes):
        raise ConfigError("boat_classes must be a non-empty list without duplicates")
    model_version = FsiParams.from_area(area).model_version
    spacing = area.raw["fsi"]["min_spacing_km"]            # validated by validate_fsi: finite number > 0
    if not store.try_lock(area.area_id, run_date):
        raise RuntimeError("another pick run for this area and date is running")
    if not store.region_exists(area.area_id):
        return PickResult("failed", "no_region")
    try:
        run_id = store.start_run(area.area_id, run_date)
    except AttemptLimit:
        return PickResult("failed", "attempt_limit")
    counts, dropped, shortfall = {}, 0, False
    try:
        for bc in boat_classes:
            cands, meta = store.candidates(area.area_id, run_date, bc, model_version)
            chosen, bad = pick(cands, area.bbox, spacing, MAX_PICKS)
            dropped += bad
            counts[bc] = store.write_picks(area.area_id, run_date, bc, model_version, chosen, meta, run_id)
            shortfall = shortfall or counts[bc] < MIN_PICKS
    except psycopg.errors.ForeignKeyViolation:
        log.error("foreign key violation while writing recommendations; nothing written for the failing class")
        store.finish_run(run_id, "failed", 0, "write_failed", {"picks": counts})
        return PickResult("failed", "write_failed", counts)
    except Exception as exc:
        log.error("pick failed: %s", type(exc).__name__)
        store.finish_run(run_id, "failed", 0, "write_failed", {"picks": counts})
        return PickResult("failed", "write_failed", counts)
    total = sum(counts.values())
    detail = {"picks": counts, "dropped_invalid": dropped, "min_spacing_km": spacing, "model_version": model_version}
    if shortfall:
        code = "no_picks" if total == 0 else "few_picks"
        store.finish_run(run_id, "partial", total, code, detail)
        return PickResult("partial", code, counts)
    store.finish_run(run_id, "success", total, None, detail)
    return PickResult("success", None, counts)
