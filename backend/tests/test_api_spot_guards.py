import copy
import pytest

from api.main import _filter_spots
from ingest.config import load_area


@pytest.fixture
def area():
    return load_area("th-chonburi-coast")


def spot(**overrides):
    row = {
        "lat": 12.225, "lon": 100.725, "fsi": 70.0, "sst_c": 29.0,
        "eligible": True, "is_water": True, "eez_ok": True,
        "disputed_ok": True, "protected_ok": None, "closure_ok": None, "boat_zone_ok": None,
        "forecast_ok": True, "sea_state_level": "green", "mask_legal_status": "incomplete",
        "confidence": "medium", "wx_source": "open_meteo_marine",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize("override", [
    {"fsi": None},
    {"sst_c": None},
    {"eligible": False},
    {"is_water": False},
    {"eez_ok": False},
    {"disputed_ok": False},
    {"protected_ok": False},
    {"closure_ok": False},
    {"boat_zone_ok": False},
    {"forecast_ok": False},
    {"sea_state_level": "red"},
    {"confidence": "high"},
])
def test_api_never_returns_unscored_forbidden_red_or_trial_high_rows(area, override):
    assert _filter_spots([spot(**override)], area, "trial", 5) == []


def test_withhold_policy_hides_incomplete_legal_rows(area):
    changed = copy.deepcopy(area)
    changed.raw["legal"]["incomplete_policy"] = "withhold"
    assert _filter_spots([spot()], changed, "trial", 5) == []


def test_route_b_never_serves_open_meteo_rows(area):
    area.raw["licence_route"] = "B"
    assert _filter_spots([spot()], area, "beta", 5) == []


def test_api_rechecks_spacing_instead_of_trusting_pick_rows(area):
    first = spot()
    adjacent = spot(lat=12.275)
    selected = _filter_spots([first, adjacent], area, "trial", 5)
    assert selected == [first]
