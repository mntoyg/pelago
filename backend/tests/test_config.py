import hashlib
import json

import pytest

from ingest.config import CONFIG_DIR, ConfigError, load_area


def test_real_config_loads_and_hash_is_of_the_file_bytes():
    a = load_area("th-chonburi-coast")
    assert a.sha256 == hashlib.sha256((CONFIG_DIR / "th-chonburi-coast.json").read_bytes()).hexdigest()
    assert a.raw["fsi"]["min_spacing_km"] == 10 and a.licence_route == "A" and a.timezone == "Asia/Bangkok"
    assert a.sea_window == ("04:00", "14:00") and len(a.cell_ids()) == 200 and a.retries == 3
    assert set(a.raw["boat_classes"]) == {"small", "medium"}


@pytest.mark.parametrize("area_id", ["../x", "th-chonburi-coast/../../x", "TH-X", "th", "th-chonburi-coast.json", ""])
def test_area_id_cannot_walk_the_file_system(area_id):
    with pytest.raises(ConfigError):
        load_area(area_id)


def write(tmp_path, raw):
    (tmp_path / "th-chonburi-coast.json").write_text(json.dumps(raw), encoding="utf-8")
    return load_area("th-chonburi-coast", tmp_path)


@pytest.fixture
def raw():
    return json.loads((CONFIG_DIR / "th-chonburi-coast.json").read_text(encoding="utf-8"))


def test_unknown_key_and_bad_values_are_refused(tmp_path, raw):
    for mutate in (lambda r: r.update(typo=1), lambda r: r.update(timezone="Mars/Base"), lambda r: r.update(licence_route="C"),
                   lambda r: r.update(bbox=[100.71, 12.2, 101.2, 13.2]), lambda r: r["sources"].pop("depth"),
                   lambda r: r["ingest"]["min_valid_fraction"].update(sst=0), lambda r: r["schedule"].update(retries=0),
                   lambda r: r["sources"]["sst"][0].update(role="fallback")):
        r = json.loads(json.dumps(raw))
        mutate(r)
        with pytest.raises(ConfigError):
            write(tmp_path, r)


@pytest.mark.parametrize("text", ["https://user:pw@host/x", "my_api_key", "Bearer abc", "token=xyz", "password1"])
def test_a_secret_in_the_config_is_refused(tmp_path, raw, text):
    raw["name"] = text
    with pytest.raises(ConfigError):
        write(tmp_path, raw)


def test_traversal_to_an_existing_config_outside_the_directory_is_refused(tmp_path, raw):
    (tmp_path / "areas").mkdir()
    (tmp_path / "outside.json").write_text(json.dumps(raw), encoding="utf-8")          # a VALID config one level up
    with pytest.raises(ConfigError):
        load_area("../outside", tmp_path / "areas")
