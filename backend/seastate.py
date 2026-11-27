"""Sea state of one cell for one boat class from the stored wave and wind window maxima (A5 filter 6). Pure.

Thresholds are the area config's `boat_classes.<class>` values (starting values, not tuned). A NaN, infinite, negative or
non-numeric value is treated as MISSING, never as calm: a missing forecast is yellow with `forecast_missing` and the cell is not
recommended (API_CONTRACT 4.4 rule 2). A red reading is kept even when the other value is missing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

REASONS = ("calm", "wave_caution", "wind_caution", "wave_wind_caution", "wave_danger", "wind_danger", "wave_wind_danger",
           "forecast_missing", "forecast_stale")


@dataclass(frozen=True)
class Thresholds:
    wave_yellow_m: float
    wave_red_m: float
    wind_yellow_kmh: float
    wind_red_kmh: float

    @classmethod
    def from_class(cls, bc: dict) -> "Thresholds":
        t = cls(*(bc[k] for k in ("wave_yellow_m", "wave_red_m", "wind_yellow_kmh", "wind_red_kmh")))
        for v in (t.wave_yellow_m, t.wave_red_m, t.wind_yellow_kmh, t.wind_red_kmh):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise ValueError("boat class thresholds must be finite numbers greater than 0")
        if t.wave_yellow_m > t.wave_red_m or t.wind_yellow_kmh > t.wind_red_kmh:
            raise ValueError("yellow threshold above red threshold")
        return t


@dataclass(frozen=True)
class SeaState:
    level: str            # green | yellow | red
    reason_code: str
    forecast_ok: bool


def _num(v):
    """float, or None when the value is missing, a bool, NaN, infinite or negative."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):        # None, strings and other types are missing, never coerced
        return None
    f = float(v)
    return f if math.isfinite(f) and f >= 0 else None


def sea_window_end(run_date: date, window_local: tuple[str, str], tz: str) -> datetime:
    h, m = (int(x) for x in window_local[1].split(":"))
    return datetime.combine(run_date, time(h, m), tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def classify(wave_m, wind_kmh, issued_at: datetime | None, ref_time: datetime, th: Thresholds,
             max_age_hours: float) -> SeaState:
    wave, wind = _num(wave_m), _num(wind_kmh)
    wave_red = wave is not None and wave >= th.wave_red_m
    wind_red = wind is not None and wind >= th.wind_red_kmh
    if wave_red or wind_red:             # danger is never softened by a missing partner value
        code = "wave_wind_danger" if wave_red and wind_red else "wave_danger" if wave_red else "wind_danger"
        return SeaState("red", code, wave is not None and wind is not None)
    if wave is None or wind is None:
        return SeaState("yellow", "forecast_missing", False)
    if issued_at is None or issued_at.tzinfo is None:
        return SeaState("yellow", "forecast_stale", False)          # no usable issue time: age unknown
    age_h = (ref_time - issued_at).total_seconds() / 3600.0
    if age_h > max_age_hours:
        return SeaState("yellow", "forecast_stale", False)
    wave_y, wind_y = wave >= th.wave_yellow_m, wind >= th.wind_yellow_kmh
    if wave_y and wind_y:
        return SeaState("yellow", "wave_wind_caution", True)
    if wave_y:
        return SeaState("yellow", "wave_caution", True)
    if wind_y:
        return SeaState("yellow", "wind_caution", True)
    return SeaState("green", "calm", True)
