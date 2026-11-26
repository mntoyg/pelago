"""FSI v1 scoring: pure functions, no database, no clock, no network (ARCHITECTURE.md A4, API_CONTRACT.md 4.5 and 4.6).

    FSI = 100 * sum(w_i * a_i * S_i) / sum(w_i * a_i)        over the inputs that have a score S_i and a_i > 0

Rules this module enforces (each one has a test that goes red when the guard is removed, see docs/fsi-mutation-log.md):
  * no SST (missing, invalid, expired, future-dated) = no score: fsi is None, never 0;
  * a missing, invalid or expired input gets weight 0 and a reason code; it is never scored as 0;
  * confidence is low unless every data input is present and fresh, and never "high" while the area is not verified.
Every weight and threshold comes from FsiParams (the area config). All values are untuned demo values.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable

from ingest.timeutil import local_date_of, local_day_end_utc

from .config import CHL_8DAY_FRESH_DAYS, SUBSCORES, FsiParams
from .moon import moon_for_local_date

CAP_CODE = "no_verified_catch_logs"
VERIFIED_LEVELS = ("beta", "confirmed")
PLACEHOLDERS = ("moon", "season")     # one rule for every fishery / a flat constant: not learned, not evidence


@dataclass(frozen=True)
class CellInputs:
    """One grid_daily row. None = no observation (never 0)."""
    cell_id: int
    sst_c: float | None = None
    sst_observed_at: datetime | None = None
    sst_grad_c_per_km: float | None = None
    chl_mg_m3: float | None = None
    chl_observed_at: datetime | None = None
    chl_product: str | None = None
    depth_m: float | None = None


@dataclass(frozen=True)
class InputState:
    """Result of vetting one raw input. status: ok | stale | missing | invalid | expired."""
    status: str
    value: float | None = None
    age_days: int | None = None
    freshness: float = 0.0     # a_i, 0 when the input is not used

    @property
    def used(self) -> bool:
        return self.status in ("ok", "stale") and self.freshness > 0


@dataclass(frozen=True)
class CellScore:
    cell_id: int
    scores: dict[str, float | None]        # S_i per sub-score, None = not computed
    fresh: dict[str, float | None]         # a_i per sub-score, None where scores is None
    fsi: float | None
    confidence: str | None
    confidence_cap: str | None
    confidence_reasons: tuple[str, ...]
    states: dict[str, InputState] = field(default_factory=dict)    # sst, front, chl, depth (for the explanation)
    front_note: str | None = None

    @property
    def scored(self) -> bool:
        return self.fsi is not None


def finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def freshness(age_days: int, p: FsiParams) -> float:
    """a = exp(-max(0, age - grace) / decay); the same shape as the browser's freshness(), parameters from config."""
    return math.exp(-max(0.0, age_days - p.grace_days) / p.decay_days)


def _age_state(value, observed_at, run_date: date, p: FsiParams, fresh_days: int, max_days: int,
               lo: float, hi: float, positive_only: bool = False) -> InputState:
    if value is None and observed_at is None:
        return InputState("missing")
    if value is None or observed_at is None:
        return InputState("invalid")                       # a value and its time travel together (schema CHECK)
    if not finite(value) or not lo <= value <= hi or (positive_only and value <= 0):
        return InputState("invalid")
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
        return InputState("invalid")
    # PM decision B: "in the future" is measured against the END of the local run_date in UTC (the cut-off ingest uses in
    # pick_times), not against the wall clock, so a back-test cannot use data from after the date it pretends to be.
    if observed_at >= local_day_end_utc(run_date, p.timezone):
        return InputState("invalid")
    age = max(0, (run_date - local_date_of(observed_at, p.timezone)).days)
    if age > max_days:
        return InputState("expired", value, age, 0.0)
    return InputState("ok" if age <= fresh_days else "stale", float(value), age, freshness(age, p))


def vet_sst(c: CellInputs, run_date: date, p: FsiParams) -> InputState:
    return _age_state(c.sst_c, c.sst_observed_at, run_date, p, p.sst_fresh_days, p.sst_max_days, -2.0, 40.0)


def vet_front(c: CellInputs, sst: InputState) -> InputState:
    """The gradient comes from the same SST field, so it shares the SST's age and is unusable when the SST is."""
    g = c.sst_grad_c_per_km
    if g is None:
        return InputState("missing")
    if not finite(g) or not 0 <= g <= 100:
        return InputState("invalid")
    if not sst.used:
        return InputState("missing" if sst.status in ("missing", "expired") else "invalid")
    return InputState(sst.status, float(g), sst.age_days, sst.freshness)


def vet_chl(c: CellInputs, run_date: date, p: FsiParams) -> InputState:
    # chlorophyll of 0 or less cannot be a real satellite value (log10 is undefined): invalid, not "a very poor score"
    return _age_state(c.chl_mg_m3, c.chl_observed_at, run_date, p, p.chl_fresh_days, p.chl_max_days, 0.0, 1000.0,
                      positive_only=True)


def vet_depth(c: CellInputs) -> InputState:
    d = c.depth_m
    if d is None:
        return InputState("missing")
    if not finite(d) or not 0 <= d <= 12000:
        return InputState("invalid")
    return InputState("ok", float(d), None, 1.0)           # a static grid: no age, a_depth = 1


def s_sst(v: float, p: FsiParams) -> float:
    return math.exp(-0.5 * ((v - p.sst_c) / p.sst_sigma_c) ** 2)


def s_chl(v: float, p: FsiParams) -> float:
    if v > p.bloom_mg_m3:
        return 0.0                                          # a bloom means low oxygen: cut to zero (A4)
    return math.exp(-0.5 * ((math.log10(v) - p.log10_chl) / p.log10_chl_sigma) ** 2)


def s_depth(v: float, p: FsiParams) -> float:
    up = v / p.depth_ramp_up_m
    down = (p.depth_zero_at_m - v) / (p.depth_zero_at_m - p.depth_full_to_m)
    return min(1.0, max(0.0, min(up, down)))


def s_moon(illumination: float, p: FsiParams) -> float:
    return 1.0 - p.moon_illum_penalty * illumination


def front_percentiles(cells: Iterable[CellInputs], run_date: date, p: FsiParams) -> dict[int, float]:
    """S_front = mid-rank percentile of the SST gradient among the area's cells for this date. PM decision A: only cells
    that are water by the ETOPO proxy (depth_m NOT NULL) with a usable SST and gradient take part, until a real land
    mask exists. Fewer than front.min_cells such cells = no percentile for anyone (a rank in a handful of cells means
    nothing)."""
    pop: dict[int, float] = {}
    for c in cells:
        if vet_depth(c).status != "ok":
            continue
        sst = vet_sst(c, run_date, p)
        front = vet_front(c, sst)
        if front.used:
            pop[c.cell_id] = front.value
    if len(pop) < p.front_min_cells:
        return {}
    vals = sorted(pop.values())
    out = {}
    for cid, v in pop.items():
        less = bisect.bisect_left(vals, v)
        equal = bisect.bisect_right(vals, v) - less
        out[cid] = (less + 0.5 * equal) / len(vals)
    return out


def effective_level(level: str | None) -> str:
    """Fail closed: anything that is not exactly beta or confirmed is treated as trial."""
    return level if level in VERIFIED_LEVELS else "trial"


def _confidence(states: dict[str, InputState], chl_product: str | None, verified: bool, p: FsiParams
                ) -> tuple[str, str | None, list[str]]:
    chl_limit = CHL_8DAY_FRESH_DAYS if chl_product == "8day" else p.chl_fresh_days
    reasons: list[str] = []
    for k in ("sst", "front", "chl", "depth"):
        st = states[k]
        if st.status == "invalid":
            reasons.append(f"{k}_invalid")
        elif st.status in ("missing", "expired"):
            reasons.append(f"{k}_missing")
        elif k == "chl" and st.used and st.age_days > chl_limit:
            reasons.append("chl_stale")                     # an 8-day composite is fresh up to 8 days, a daily one to 3
        elif k != "chl" and st.status == "stale":
            reasons.append(f"{k}_stale")
    chl_late = states["chl"].used and states["chl"].age_days > chl_limit
    sst_late = states["sst"].used and states["sst"].age_days > p.sst_fresh_days
    all_present = all(states[k].used for k in ("sst", "front", "chl", "depth"))
    meets = all_present and not sst_late and not chl_late
    cap = None if verified else CAP_CODE
    if not meets:
        return "low", cap, reasons
    if verified:
        return "high", cap, reasons
    return "medium", cap, reasons + [CAP_CODE]


def score_cell(c: CellInputs, run_date: date, p: FsiParams, front_pct: dict[int, float], moon: dict[str, float],
               verification_level: str | None) -> CellScore:
    sst = vet_sst(c, run_date, p)
    front = vet_front(c, sst)
    chl = vet_chl(c, run_date, p)
    depth = vet_depth(c)
    states = {"sst": sst, "front": front, "chl": chl, "depth": depth}
    pct = front_pct.get(c.cell_id)
    if front.used and pct is None:
        note = "front_unranked"          # not in the percentile population (no water proxy, or too few cells)
        front = InputState("missing")
        states["front"] = front
    else:
        note = None

    # "No SST = no score" (S p.7): nothing else is reported for such a cell, and the reason says why.
    if not sst.used:
        reason = "sst_invalid" if sst.status == "invalid" else "sst_missing"
        empty = {k: None for k in SUBSCORES}
        return CellScore(c.cell_id, dict(empty), dict(empty), None, None, None, (reason,), states, note)

    scores: dict[str, float | None] = {
        "sst": s_sst(sst.value, p),
        "front": pct if front.used else None,
        "chl": s_chl(chl.value, p) if chl.used else None,
        "depth": s_depth(depth.value, p) if depth.used else None,
        "moon": s_moon(moon["illumination"], p),
        "season": p.season_flat,
    }
    fresh: dict[str, float | None] = {
        "sst": sst.freshness, "front": front.freshness if front.used else None,
        "chl": chl.freshness if chl.used else None, "depth": depth.freshness if depth.used else None,
        "moon": 1.0, "season": 1.0}
    num = den = 0.0
    for k in SUBSCORES:
        if scores[k] is not None and fresh[k]:
            num += p.weights[k] * fresh[k] * scores[k]
            den += p.weights[k] * fresh[k]
    if not den > 0:       # cannot happen with a validated config (weights.sst > 0); never divide by zero or invent 0
        empty = {k: None for k in SUBSCORES}
        return CellScore(c.cell_id, dict(empty), dict(empty), None, None, None, ("sst_missing",), states, note)
    fsi = min(100.0, max(0.0, round(100.0 * num / den, 3)))
    conf, cap, reasons = _confidence(states, c.chl_product, effective_level(verification_level) in VERIFIED_LEVELS, p)
    return CellScore(c.cell_id, scores, fresh, fsi, conf, cap, tuple(reasons), states, note)


def score_area(cells: list[CellInputs], run_date: date, p: FsiParams, verification_level: str | None
               ) -> list[CellScore]:
    """Scores every cell of one area and date. Order of the result follows the order of `cells`."""
    pct = front_percentiles(cells, run_date, p)
    moon = moon_for_local_date(run_date, p.timezone)
    return [score_cell(c, run_date, p, pct, moon, verification_level) for c in cells]


def fsi_display(v: float | None) -> int | None:
    """Rounds half up like the browser's Math.round (Python's round() is banker's rounding)."""
    return None if v is None else math.floor(v + 0.5)
