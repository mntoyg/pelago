"""Strict validation of the whole fsi block (ingest.config.validate_fsi) and FsiParams. Every case must raise ConfigError
for ITS OWN reason: the match= text is the specific cause, so another guard refusing the same input cannot satisfy it."""
import copy
import json
import math

import pytest

from fsi.config import FsiParams
from ingest.config import CONFIG_DIR, ConfigError, load_area, validate_fsi


def raw():
    return json.loads((CONFIG_DIR / "th-chonburi-coast.json").read_text(encoding="utf-8"))


def fsi_with(mutate):
    r = raw()["fsi"]
    mutate(r)
    return r


def test_real_config_is_valid_and_params_load():
    a = load_area("th-chonburi-coast")
    p = FsiParams.from_area(a)
    assert p.model_version == "fsi-v1.0.0" and p.weights["sst"] == 0.20 and p.front_min_cells == 20
    assert p.sst_fresh_days == 2 and p.chl_max_days == 10 and p.config_sha256 == a.sha256


@pytest.mark.parametrize("name,mutate,match", [
    ("unknown top key", lambda f: f.update(extra=1), "exactly the keys"),
    ("missing block", lambda f: f.pop("front"), "exactly the keys"),
    ("bad version", lambda f: f.update(model_version="v1"), "model_version"),
    ("unknown weight key", lambda f: f["weights"].update(tide=1), "fsi.weights must have exactly"),
    ("missing weight key", lambda f: f["weights"].pop("moon"), "fsi.weights must have exactly"),
    ("negative weight", lambda f: f["weights"].update(chl=-0.1), "fsi.weights.chl"),
    ("nan weight", lambda f: f["weights"].update(chl=math.nan), "fsi.weights.chl"),
    ("inf weight", lambda f: f["weights"].update(chl=math.inf), "fsi.weights.chl"),
    ("bool weight", lambda f: f["weights"].update(chl=True), "fsi.weights.chl"),
    ("string weight", lambda f: f["weights"].update(chl="0.2"), "fsi.weights.chl"),
    ("huge weight", lambda f: f["weights"].update(chl=1e9), "fsi.weights.chl"),
    ("weights sum to zero", lambda f: f["weights"].update({k: 0 for k in f["weights"]}), "must not sum to 0"),
    ("sigma zero", lambda f: f["targets"].update(sst_sigma_c=0), "sigmas and the bloom"),
    ("unknown target", lambda f: f["targets"].update(x=1), "fsi.targets must have exactly"),
    ("depth order", lambda f: f["depth"].update(full_to_m=300), "ramp_up_m <= full_to_m < zero_at_m"),
    ("front.min_cells fraction", lambda f: f["front"].update(min_cells=2.5), "integer >= 1"),
    ("moon penalty > 1", lambda f: f["moon"].update(illum_penalty=1.5), "illum_penalty"),
    ("season flat < 0", lambda f: f["season"].update(flat=-1), "season.flat"),
    ("decay zero", lambda f: f["freshness"].update(decay_days=0), "decay_days > 0"),
    ("spacing nan", lambda f: f.update(min_spacing_km=math.nan), "min_spacing_km"),
])
def test_validate_fsi_refuses(name, mutate, match):
    with pytest.raises(ConfigError, match=match):
        validate_fsi(fsi_with(mutate))


def test_fsi_block_is_checked_by_the_area_loader(tmp_path):
    r = raw()
    r["fsi"]["weights"]["chl"] = -1
    (tmp_path / "th-chonburi-coast.json").write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(ConfigError, match="fsi.weights.chl"):
        load_area("th-chonburi-coast", tmp_path)


def test_sst_weight_zero_is_refused_by_params():
    r = raw()
    r["fsi"]["weights"]["sst"] = 0
    with pytest.raises(ConfigError, match="fsi.weights.sst must be greater than 0"):
        FsiParams.from_raw(r, "0" * 64)


@pytest.mark.parametrize("bad", [{"fresh": 6, "max": 5}, {"fresh": -1, "max": 5}, {"fresh": 2}, {"fresh": True, "max": 5},
                                 {"fresh": 2, "max": 5.5}])
def test_age_limits_are_checked(bad):
    r = raw()
    r["max_age_days"]["sst"] = bad
    with pytest.raises(ConfigError, match="max_age_days.sst"):
        FsiParams.from_raw(r, "0" * 64)
