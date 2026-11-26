"""Unit tests (no database) for the eligibility decision and the sea state."""
import math
from datetime import datetime, timedelta, timezone

import pytest

from legal import LEGAL_FLAGS, LegalError, decide, legal_status
from seastate import Thresholds, classify

UTC = timezone.utc
TH = Thresholds(1.0, 1.5, 20, 30)               # the 'small' class of the Chonburi config
REF = datetime(2026, 11, 26, 7, 0, tzinfo=UTC)  # end of the sea window 14:00 local
FRESH = REF - timedelta(hours=7)


def flags(**over):
    f = {k: None for k in LEGAL_FLAGS}
    f.update(over)
    return f


def ok(**over):
    kw = dict(is_water=True, flags=flags(eez_ok=True), sea_level="green", forecast_ok=True, forecast_code="calm",
              unknown_allowed=True)
    kw.update(over)
    return decide(**kw)


# ---- legal.decide ---------------------------------------------------------------------------------------------------------
def test_trial_policy_allows_unknown_layers_and_labels_them():
    d = ok()
    assert d.eligible and d.legal_status == "incomplete" and d.exclusion_codes == ()


def test_withhold_policy_refuses_unknown_layers():
    d = ok(unknown_allowed=False)
    assert not d.eligible and "legal_incomplete" in d.exclusion_codes


def test_complete_legal_status_needs_every_layer_checked():
    full = flags(**{k: True for k in LEGAL_FLAGS})
    assert legal_status(full) == "complete" and ok(flags=full, unknown_allowed=False).eligible
    assert legal_status({**full, "closure_ok": None}) == "incomplete"


@pytest.mark.parametrize("name,code", [("eez_ok", "outside_eez"), ("disputed_ok", "disputed_area"),
                                       ("protected_ok", "protected_zone"), ("closure_ok", "closed_season"),
                                       ("boat_zone_ok", "boat_class_zone")])
def test_any_forbidden_flag_blocks_even_under_the_trial_policy(name, code):
    d = ok(flags=flags(**{**{k: True for k in LEGAL_FLAGS}, name: False}))
    assert not d.eligible and code in d.exclusion_codes


def test_unknown_eez_is_never_recommended_even_when_other_layers_unknown_are_allowed():
    d = ok(flags=flags(eez_ok=None))
    assert not d.eligible and "eez_unknown" in d.exclusion_codes


def test_land_unknown_land_red_and_forecast_each_block():
    assert not ok(is_water=False).eligible and "land" in ok(is_water=False).exclusion_codes
    assert not ok(is_water=None).eligible and "land_unknown" in ok(is_water=None).exclusion_codes
    assert not ok(sea_level="red").eligible and "red_sea" in ok(sea_level="red").exclusion_codes
    d = ok(forecast_ok=False, forecast_code="forecast_missing", sea_level="yellow")
    assert not d.eligible and "no_forecast" in d.exclusion_codes
    d = ok(forecast_ok=False, forecast_code="forecast_stale", sea_level="yellow")
    assert not d.eligible and "stale_forecast" in d.exclusion_codes


@pytest.mark.parametrize("bad", [1, 0, "yes", math.nan, "", [True]])
def test_flags_are_strictly_tri_state(bad):
    with pytest.raises(LegalError):
        ok(flags=flags(eez_ok=bad))
    with pytest.raises(LegalError):
        ok(flags=flags(eez_ok=True, disputed_ok=bad))


def test_other_inputs_are_strict_too():
    for kw in ({"is_water": 1}, {"forecast_ok": None}, {"unknown_allowed": "label"}, {"sea_level": "orange"}):
        with pytest.raises(LegalError):
            ok(**kw)
    with pytest.raises(LegalError):
        decide(True, {"eez_ok": True}, "green", True, "calm", True)       # flags missing


# ---- seastate.classify ----------------------------------------------------------------------------------------------------
def cl(wave, wind, issued=FRESH, hours=48):
    return classify(wave, wind, issued, REF, TH, hours)


@pytest.mark.parametrize("wave,wind,level,code", [
    (0.99, 19.9, "green", "calm"), (1.0, 10, "yellow", "wave_caution"), (0.5, 20, "yellow", "wind_caution"),
    (1.0, 20, "yellow", "wave_wind_caution"), (1.5, 10, "red", "wave_danger"), (0.5, 30, "red", "wind_danger"),
    (1.5, 30, "red", "wave_wind_danger"), (1.49, 29.9, "yellow", "wave_wind_caution"), (0, 0, "green", "calm")])
def test_thresholds_are_inclusive(wave, wind, level, code):
    s = cl(wave, wind)
    assert (s.level, s.reason_code) == (level, code)
    assert s.forecast_ok is True


@pytest.mark.parametrize("wave,wind", [(None, 10), (0.4, None), (None, None), (math.nan, 10), (0.4, math.inf), (-1, 10),
                                       ("1.0", 10), (True, 10)])
def test_missing_nan_negative_or_non_numeric_is_never_calm(wave, wind):
    s = cl(wave, wind)
    assert (s.level, s.reason_code, s.forecast_ok) == ("yellow", "forecast_missing", False)


def test_danger_is_kept_when_the_other_value_is_missing():
    assert cl(1.6, None).level == "red" and cl(None, 31).level == "red"
    assert cl(1.6, math.nan).level == "red"


def test_stale_and_untimed_forecasts():
    assert cl(0.4, 10, issued=REF - timedelta(hours=48)).forecast_ok is True        # exactly at the limit
    s = cl(0.4, 10, issued=REF - timedelta(hours=48, seconds=1))
    assert (s.level, s.reason_code, s.forecast_ok) == ("yellow", "forecast_stale", False)
    assert cl(0.4, 10, issued=None).reason_code == "forecast_stale"
    assert cl(0.4, 10, issued=datetime(2026, 11, 26, 0, 0)).reason_code == "forecast_stale"          # naive timestamp
    assert cl(0.4, 10, issued=REF + timedelta(hours=3)).forecast_ok is True       # issued after the reference: age <= 0


def test_thresholds_are_validated():
    bc = {"wave_yellow_m": 1.0, "wave_red_m": 1.5, "wind_yellow_kmh": 20, "wind_red_kmh": 30}
    assert Thresholds.from_class(bc) == TH
    for bad in ({"wave_yellow_m": math.nan}, {"wave_red_m": 0.5}, {"wind_red_kmh": True}, {"wind_yellow_kmh": 0},
                {"wave_yellow_m": "1"}):
        with pytest.raises(ValueError):
            Thresholds.from_class({**bc, **bad})
