"""Unit tests (no database): layer file loading, the land builder, the EEZ fetch checks. All input here is synthetic."""
import json
import struct

import pytest

from masks import build_land, fetch_eez
from masks.layers import LayerError, load_layers, read_layer_file
from tests.mask_helpers import rect, write_layer

BBOX = (100.7, 12.2, 101.2, 13.2)
SQUARE = rect(100.0, 12.0, 101.5, 13.5)


def layer_dir(tmp_path, **files):
    d = tmp_path / "layers"
    for name, polys in files.items():
        write_layer(d / "th-chonburi-coast", name + ".geojson", polys)
    return d


def test_good_files_load_with_hashes_and_all_three_layers(tmp_path):
    d = layer_dir(tmp_path, land=[SQUARE], eez=[SQUARE], internal_waters=[SQUARE])
    L = load_layers("th-chonburi-coast", BBOX, d)
    assert L.problems == {} and set(L.sha256) == {"land", "eez", "internal_waters"}
    assert L.land and L.eez and len(L.eez) == 2          # eez = EEZ + internal waters together


def test_missing_files_are_absent_layers_with_a_code_not_an_exception(tmp_path):
    L = load_layers("th-chonburi-coast", BBOX, layer_dir(tmp_path, land=[SQUARE], eez=[SQUARE]))
    assert L.problems == {"internal_waters": "missing"} and L.eez is None and L.land


def _file(tmp_path, text):
    p = tmp_path / "x.geojson"
    p.write_text(text, encoding="utf-8")
    return p


@pytest.mark.parametrize("name,text,code", [
    ("not json", "{nope", "not_json"),
    ("nan literal", '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":'
                    '[[[NaN,1],[2,1],[2,2],[NaN,1]]]}}]}', "not_json"),
    ("infinity literal", '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":'
                         '[[[Infinity,1],[2,1],[2,2],[Infinity,1]]]}}]}', "not_json"),
    ("empty collection", '{"type":"FeatureCollection","features":[]}', "bad_geometry"),
    ("point feature", '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[1,2]}}]}',
     "bad_geometry"),
    ("unclosed ring", json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {
        "type": "Polygon", "coordinates": [[[100, 12], [101, 12], [101, 13], [100, 13]]]}}]}), "bad_geometry"),
    ("lat out of range", json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {
        "type": "Polygon", "coordinates": [[[100, 12], [101, 12], [101, 95], [100, 12]]]}}]}), "bad_geometry"),
    ("no feature list", '{"type":"FeatureCollection"}', "bad_geometry"),
    ("far away", json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {
        "type": "Polygon", "coordinates": rect(10, 10, 11, 11)}}]}), "no_overlap"),
])
def test_bad_layer_files_are_refused_with_a_short_code(tmp_path, name, text, code):
    with pytest.raises(LayerError) as e:
        read_layer_file(_file(tmp_path, text), BBOX)
    assert e.value.code == code, name


def test_bytes_that_are_not_utf8_and_oversized_files_are_refused(tmp_path, monkeypatch):
    p = tmp_path / "b.geojson"
    p.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(LayerError) as e:
        read_layer_file(p, BBOX)
    assert e.value.code == "not_json"
    monkeypatch.setattr("masks.layers.MAX_FILE_BYTES", 10)
    q = _file(tmp_path, json.dumps({"type": "FeatureCollection", "features": []}))
    with pytest.raises(LayerError) as e:
        read_layer_file(q, BBOX)
    assert e.value.code == "too_large"


def test_a_symlinked_layer_file_is_refused(tmp_path):
    real = _file(tmp_path, json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {
        "type": "Polygon", "coordinates": SQUARE}}]}))
    link = tmp_path / "link.geojson"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need a privilege on this machine")
    with pytest.raises(LayerError) as e:
        read_layer_file(link, BBOX)
    assert e.value.code == "missing"


@pytest.mark.parametrize("bad", ["../x", "th-chonburi-coast/../..", "TH-CHONBURI", "", "a/b", "th-"])
def test_area_id_cannot_walk_out_of_the_layers_folder(tmp_path, bad):
    with pytest.raises(LayerError):
        load_layers(bad, BBOX, tmp_path)


# ---- build_land -----------------------------------------------------------------------------------------------------------
def shp(rings_per_record, shape_type=5):
    """A minimal polygon shapefile .shp body. Each record is a list of rings; each ring a list of (x, y), closed."""
    recs = b""
    for i, rings in enumerate(rings_per_record, start=1):
        pts = [p for r in rings for p in r]
        parts, off = [], 0
        for r in rings:
            parts.append(off)
            off += len(r)
        body = struct.pack("<i4d2i", shape_type, min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts),
                           max(p[1] for p in pts), len(parts), len(pts))
        body += struct.pack(f"<{len(parts)}i", *parts) + b"".join(struct.pack("<2d", *p) for p in pts)
        recs += struct.pack(">2i", i, len(body) // 2) + body
    header = struct.pack(">i5ii", 9994, 0, 0, 0, 0, 0, (100 + len(recs)) // 2) + struct.pack("<2i8d", 1000, shape_type, *([0.0] * 8))
    return header + recs


def clockwise(x0, y0, x1, y1):
    return [(x0, y0), (x0, y1), (x1, y1), (x1, y0), (x0, y0)]


def test_shapefile_round_trip_and_clip_to_the_window():
    data = shp([[clockwise(100.0, 12.0, 102.0, 14.0)], [clockwise(10.0, 10.0, 11.0, 11.0)]])
    recs = list(build_land.read_polygons(data))
    assert len(recs) == 2
    coords = build_land.clipped_multipolygon(recs, (100.2, 11.7, 101.7, 13.7))
    assert len(coords) == 1                                           # the far polygon is dropped
    xs = [p[0] for p in coords[0][0]]
    ys = [p[1] for p in coords[0][0]]
    assert (min(xs), max(xs), min(ys), max(ys)) == (100.2, 101.7, 12.0, 13.7)     # the big polygon is cut to the window (its south edge is already inside)


def test_a_hole_is_kept_inside_its_polygon():
    outer, hole = clockwise(100.0, 12.0, 102.0, 14.0), list(reversed(clockwise(100.9, 12.9, 101.0, 13.0)))
    coords = build_land.clipped_multipolygon(list(build_land.read_polygons(shp([[outer, hole]]))), (100.2, 11.7, 101.7, 13.7))
    assert len(coords) == 1 and len(coords[0]) == 2


@pytest.mark.parametrize("mutate,why", [
    (lambda b: b[:60], "truncated header"),
    (lambda b: b[:-8], "length does not match"),
    (lambda b: b[:24] + struct.pack(">i", len(b) // 2 + 4) + b[28:], "header declares a different length than the file has"),
    (lambda b: b"\x00\x00\x27\x0b" + b[4:], "wrong file code"),
    (lambda b: b[:32] + struct.pack("<i", 3) + b[36:], "polyline type"),
])
def test_corrupt_shapefiles_are_refused(mutate, why):
    good = shp([[clockwise(100.0, 12.0, 101.0, 13.0)]])
    with pytest.raises(build_land.ShapefileError):
        list(build_land.read_polygons(mutate(good)))


def test_nan_and_out_of_range_coordinates_in_a_shapefile_are_refused():
    nan_ring = [(100.0, 12.0), (float("nan"), 13.0), (101.0, 13.0), (100.0, 12.0)]
    with pytest.raises(build_land.ShapefileError):
        list(build_land.read_polygons(shp([[nan_ring]])))
    far = [(100.0, 12.0), (100.0, 95.0), (101.0, 13.0), (100.0, 12.0)]
    with pytest.raises(build_land.ShapefileError):
        list(build_land.read_polygons(shp([[far]])))


def test_builder_refuses_to_write_an_empty_layer(tmp_path):
    f = tmp_path / "l.shp"
    f.write_bytes(shp([[clockwise(10.0, 10.0, 11.0, 11.0)]]))
    with pytest.raises(build_land.ShapefileError):
        build_land.build(f, BBOX, 0.5, tmp_path / "o.geojson")
    assert not (tmp_path / "o.geojson").exists()


# ---- fetch_eez --------------------------------------------------------------------------------------------------------------
def test_wfs_request_is_latitude_first_and_goes_only_to_the_provider_host():
    url = fetch_eez.request_url("eez", (100.45, 11.95, 101.45, 13.45))
    assert url.startswith("https://geo.vliz.be/geoserver/MarineRegions/wfs?")
    assert "bbox=11.95,100.45,13.45,101.45,urn:ogc:def:crs:EPSG::4326" in url and "typeNames=MarineRegions:eez" in url


def test_fetched_collections_are_checked_before_anything_is_written():
    good = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": SQUARE}}]}
    assert fetch_eez.check_collection(good) == 5
    for bad in ({}, {"type": "FeatureCollection", "features": []},
                {"type": "FeatureCollection", "features": [{"geometry": None}]},
                {"type": "FeatureCollection", "features": [{"geometry": {"type": "Polygon",
                                                                         "coordinates": [[[0, 0], [1, 0], [1, float("nan")], [0, 0]]]}}]}):
        with pytest.raises(ValueError):
            fetch_eez.check_collection(bad)
