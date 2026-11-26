"""One mask run for one area and local date: read the ingested wave/wind, evaluate land and EEZ per cell, decide eligibility per
boat class, upsert cell_mask_daily, record the run.

Failure is loud and leaves cell_mask_daily untouched: bad config, no region row, no ingest rows, a database error, or a
recommendation that the new mask would contradict (recommendation_conflict). A layer that is configured as loaded but cannot be
used makes the run 'partial': its flags are NULL, so nothing depends on it being right.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import psycopg

from ingest.config import AreaConfig, ConfigError
from ingest.grid import cell_centre
from legal import POLICIES, LegalError, decide
from seastate import Thresholds, classify, sea_window_end
from . import geo
from .db import AttemptLimit, CellWx, MaskStore
from .layers import LayerError, load_layers

log = logging.getLogger("mask")
LAND_LAYER = "land"
EEZ_PREFIX = "eez_buffer_"
# Only `land` and `eez_buffer_*` can be evaluated; any other name listed as loaded in the config is refused (a claim without a check).


@dataclass(frozen=True)
class MaskParams:
    policy: str
    buffer_m: float
    loaded: tuple[str, ...]
    thresholds: dict[str, Thresholds]
    window: tuple[str, str]
    timezone: str
    max_forecast_hours: float

    @classmethod
    def from_area(cls, area: AreaConfig, boat_classes) -> "MaskParams":
        legal = area.raw.get("legal")
        if not isinstance(legal, dict):
            raise ConfigError("legal block missing")
        policy = legal.get("incomplete_policy")
        if policy not in POLICIES:
            raise ConfigError("legal.incomplete_policy must be 'label' or 'withhold'")
        km = legal.get("eez_buffer_km")
        if isinstance(km, bool) or not isinstance(km, (int, float)) or not math.isfinite(km) or not 0 < km <= 200:
            raise ConfigError("legal.eez_buffer_km must be a number in (0, 200]")
        loaded = legal.get("layers_loaded")
        if not isinstance(loaded, list) or not all(isinstance(x, str) for x in loaded):
            raise ConfigError("legal.layers_loaded must be a list of names")
        for name in loaded:
            if name != LAND_LAYER and not name.startswith(EEZ_PREFIX):
                raise ConfigError("legal.layers_loaded names a layer this build cannot evaluate")
        th = {}
        for bc in boat_classes:
            try:
                th[bc] = Thresholds.from_class(area.raw["boat_classes"][bc])
            except (KeyError, TypeError, ValueError) as exc:
                raise ConfigError(f"boat class {bc!r}: missing or invalid thresholds") from exc
        hours = area.raw["max_age_days"]["wave_wind_hours"]["max"]
        if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not math.isfinite(hours) or hours <= 0:
            raise ConfigError("max_age_days.wave_wind_hours.max must be greater than 0")
        return cls(policy, float(km) * 1000.0, tuple(loaded), th, area.sea_window, area.timezone, float(hours))


@dataclass
class MaskResult:
    status: str                       # success | partial | failed
    error_code: str | None
    cells_total: int = 0
    eligible: dict[str, int] = field(default_factory=dict)
    layers_missing: list[str] = field(default_factory=list)


def run_mask(area: AreaConfig, run_date: date, store: MaskStore, boat_classes=("small",), layers_dir: Path | None = None,
             clear_picks: bool = False) -> MaskResult:
    boat_classes = list(boat_classes)
    if not boat_classes or len(set(boat_classes)) != len(boat_classes):
        raise ConfigError("boat_classes must be a non-empty list without duplicates")
    p = MaskParams.from_area(area, boat_classes)
    if not store.try_lock(area.area_id, run_date):
        raise RuntimeError("another mask run for this area and date is running")
    if not store.region_exists(area.area_id):
        log.error("no regions row for %s: run the ingest first", area.area_id)
        return MaskResult("failed", "no_region")
    try:
        run_id = store.start_run(area.area_id, run_date)
    except AttemptLimit:
        return MaskResult("failed", "attempt_limit")

    def fail(code: str, detail: dict | None = None) -> MaskResult:
        store.finish_run(run_id, "failed", 0, code, detail or {})
        return MaskResult("failed", code)

    cells = store.read_cells(area.area_id, run_date)
    if not cells:
        return fail("no_ingest")
    try:
        layers = load_layers(area.area_id, area.bbox, layers_dir)
    except LayerError as exc:
        return fail(exc.code)
    want_land = LAND_LAYER in p.loaded
    want_eez = any(n.startswith(EEZ_PREFIX) for n in p.loaded)
    land = layers.land if want_land else None
    water = layers.eez if (want_eez and land is not None) else None      # the EEZ test needs land to tell coast from border
    missing = sorted(set(([LAND_LAYER] if want_land and land is None else [])
                         + (["eez"] if want_eez and water is None else [])))
    try:
        flags = geo.evaluate(store.conn, [(c.cell_id, *cell_centre(c.cell_id)) for c in cells], land, water, p.buffer_m)
    except Exception as exc:
        log.error("geometry evaluation failed: %s", type(exc).__name__)
        return fail("geo_failed")
    ref = sea_window_end(run_date, p.window, p.timezone)
    unknown_allowed = p.policy == "label"
    rows, eligible = [], {bc: 0 for bc in boat_classes}
    try:
        for bc in boat_classes:
            for c in cells:
                is_water, eez_ok = flags[c.cell_id]
                sea = classify(c.wave_m, c.wind_kmh, c.issued_at, ref, p.thresholds[bc], p.max_forecast_hours)
                fl = {"eez_ok": eez_ok, "disputed_ok": None, "protected_ok": None, "closure_ok": None, "boat_zone_ok": None}
                d = decide(is_water, fl, sea.level, sea.forecast_ok, sea.reason_code, unknown_allowed)
                eligible[bc] += d.eligible
                rows.append({"boat_class": bc, "cell_id": c.cell_id, "is_water": is_water is True, **fl,
                             "legal_status": d.legal_status, "forecast_ok": sea.forecast_ok, "sea_state_level": sea.level,
                             "sea_reason_code": sea.reason_code, "legal_unknown_allowed": unknown_allowed,
                             "eligible": d.eligible, "exclusion_codes": list(d.exclusion_codes)})
    except LegalError as exc:
        log.error("legal decision failed: %s", exc)
        return fail("bad_decision")
    try:
        n = store.write_mask(area.area_id, run_date, rows, boat_classes, clear_picks)
    except psycopg.errors.ForeignKeyViolation:
        log.error("a stored recommendation would become ineligible; nothing written")
        return fail("recommendation_conflict")
    except Exception as exc:
        log.error("write failed: %s", type(exc).__name__)
        return fail("write_failed")
    detail = {"cells_total": len(cells), "rows": n, "eligible": eligible, "boat_classes": boat_classes,
              "layers_loaded": sorted(k for k in layers.sha256 if k in ("land", "eez", "internal_waters")),
              "layers_missing": missing, "layer_problems": layers.problems, "layer_sha256": layers.sha256,
              "legal_policy": p.policy, "eez_buffer_m": p.buffer_m}
    if missing:
        store.finish_run(run_id, "partial", n, "layer_not_loaded", detail)
        return MaskResult("partial", "layer_not_loaded", len(cells), eligible, missing)
    store.finish_run(run_id, "success", n, None, detail)
    return MaskResult("success", None, len(cells), eligible, [])
