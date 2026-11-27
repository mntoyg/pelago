"""The legal / eligibility decision for one cell. Pure: no database, clock or network.

Tri-state legal flags (schema.sql cell_mask_daily): True = checked and allowed, False = checked and forbidden, None = unknown
(layer not loaded, no data). Unknown is NOT recommended, except under the explicit trial policy `label`, where the cell is
still never forbidden and carries legal_status 'incomplete'. This module repeats the rule of the database CHECK on
cell_mask_daily on purpose (two independent guards); keep the two in step.
"""
from __future__ import annotations

from dataclasses import dataclass

LEGAL_FLAGS = ("eez_ok", "disputed_ok", "protected_ok", "closure_ok", "boat_zone_ok")
POLICIES = ("label", "withhold")
# exclusion code for a flag that is False / None
_FALSE_CODE = {"eez_ok": "outside_eez", "disputed_ok": "disputed_area", "protected_ok": "protected_zone",
               "closure_ok": "closed_season", "boat_zone_ok": "boat_class_zone"}
_NONE_CODE = {"eez_ok": "eez_unknown"}


class LegalError(ValueError):
    pass


@dataclass(frozen=True)
class Decision:
    legal_status: str                 # 'complete' | 'incomplete'
    eligible: bool
    exclusion_codes: tuple[str, ...]


def check_flag(name: str, value) -> None:
    """A flag is exactly True, False or None. 1, 0, 'yes', NaN and numpy bools are refused, never coerced."""
    if value is not True and value is not False and value is not None:
        raise LegalError(f"{name} must be True, False or None, got {type(value).__name__}")


def legal_status(flags: dict) -> str:
    """'complete' only when every legal layer was actually checked (no flag is None)."""
    return "complete" if all(flags[k] is not None for k in LEGAL_FLAGS) else "incomplete"


def decide(is_water, flags: dict, sea_level: str, forecast_ok, forecast_code: str, unknown_allowed) -> Decision:
    """Eligibility of one cell for one boat class.

    eligible  <=>  water, inside the EEZ buffer (flag True), no other flag False, sea state not red, a usable forecast, and
                   (every legal layer checked, or the area's trial policy allows unknown layers).
    """
    if is_water is not True and is_water is not False and is_water is not None:
        raise LegalError("is_water must be True, False or None")      # None: land layer not loaded, so not known to be water
    if forecast_ok is not True and forecast_ok is not False:
        raise LegalError("forecast_ok must be a bool")
    if unknown_allowed is not True and unknown_allowed is not False:
        raise LegalError("unknown_allowed must be a bool")
    if sea_level not in ("green", "yellow", "red"):
        raise LegalError("bad sea_level")
    for k in LEGAL_FLAGS:
        if k not in flags:
            raise LegalError(f"missing flag {k}")
        check_flag(k, flags[k])
    status = legal_status(flags)
    codes: list[str] = []
    if is_water is None:
        codes.append("land_unknown")
    elif not is_water:
        codes.append("land")
    for k in LEGAL_FLAGS:
        if flags[k] is False:
            codes.append(_FALSE_CODE[k])
        elif flags[k] is None and k in _NONE_CODE:
            codes.append(_NONE_CODE[k])
    if sea_level == "red":
        codes.append("red_sea")
    if not forecast_ok:
        codes.append("stale_forecast" if forecast_code == "forecast_stale" else "no_forecast")
    if status == "incomplete" and not unknown_allowed:
        codes.append("legal_incomplete")
    eligible = (is_water is True and flags["eez_ok"] is True
                and all(flags[k] is not False for k in LEGAL_FLAGS)
                and sea_level != "red" and forecast_ok is True
                and (status == "complete" or unknown_allowed is True))
    return Decision(status, eligible, tuple(dict.fromkeys(codes)))
