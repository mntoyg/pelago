"""Land / EEZ evaluation by PostGIS on SYNTHETIC polygons, with the expected answers computed independently (spherical formulas in
mask_helpers). Real PostGIS needed: PELAGO_TEST_ADMIN_URL of a throwaway server, PELAGO_REQUIRE_DB=1 to make a missing one a failure."""
import json
import os
from decimal import Decimal

import pytest

from masks import geo
from tests.mask_helpers import dlon_for_km, km_to_meridian, rect
from tests.test_db_roundtrip import ADMIN, db  # noqa: F401  (db is a pytest fixture)

pytestmark = pytest.mark.skipif(not ADMIN and not os.environ.get("PELAGO_REQUIRE_DB"), reason="PELAGO_TEST_ADMIN_URL not set")


def gj(coords):
    return json.dumps({"type": "Polygon", "coordinates": coords})


def cell(i, lat, lon):
    return (i, Decimal(str(lat)), Decimal(str(lon)))


# World used below (all degrees): land east of lon 101.10; national waters (EEZ + internal waters) from lon 100.80 to the coast,
# lat 12.0..13.5; the western edge at lon 100.80 is a BORDER, the eastern edge (101.098, 200 m short of the coast) is COAST.
LAND = [gj(rect(101.10, 11.5, 102.0, 14.0))]
WATER = [gj(rect(100.80, 12.0, 101.098, 12.8)), gj(rect(100.80, 12.8, 101.098, 13.5))]     # two parts that share the edge lat 12.8
BUF = 5000.0


def ev(db, cells, land=LAND, water=WATER, buf=BUF):
    return geo.evaluate(db, cells, land, water, buf)


def test_land_cell_is_not_water_and_sea_cell_is(db):
    r = ev(db, [cell(1, 12.5, 101.15), cell(2, 12.5, 101.00), cell(3, 12.5, 101.10)])
    assert r[1][0] is False and r[2][0] is True
    assert r[3][0] is False                                  # a centre exactly on the coastline counts as land (conservative)


def test_distance_to_a_border_4_8_km_is_refused_and_5_2_km_is_accepted(db):
    lat = 12.5
    near = 100.80 + dlon_for_km(lat, 4.8)
    far = 100.80 + dlon_for_km(lat, 5.2)
    assert km_to_meridian(lat, near - 100.80) == pytest.approx(4.8, abs=1e-6)       # the independent formula says what we placed
    r = ev(db, [cell(1, lat, round(near, 6)), cell(2, lat, round(far, 6)), cell(3, lat, 100.75), cell(4, lat, 100.95)])
    assert r[1][1] is False                                  # inside the polygon but 4.8 km from the border
    assert r[2][1] is True                                   # 5.2 km
    assert r[3][1] is False                                  # outside the waters (west of the border)
    assert r[4][1] is True                                   # well inside


def test_a_different_buffer_changes_the_answer_the_buffer_is_a_parameter(db):
    lat, lon = 12.5, round(100.80 + dlon_for_km(12.5, 4.8), 6)
    assert ev(db, [cell(1, lat, lon)], buf=4000.0)[1][1] is True
    assert ev(db, [cell(1, lat, lon)], buf=6000.0)[1][1] is False


def test_the_coast_is_not_a_border_even_inside_five_kilometres(db):
    # 1.1 km west of the coast and 200 m east of the water polygon's own eastern edge (the gap between the two coastlines)
    r = ev(db, [cell(1, 12.5, 101.09), cell(2, 12.5, 101.099), cell(3, 12.5, 101.0)])
    assert r[1][1] is True and r[2][1] is True and r[3][1] is True


def test_two_water_parts_that_share_an_edge_are_one_water_body(db):
    r = ev(db, [cell(1, 12.8, 100.95), cell(2, 12.79, 100.95), cell(3, 12.81, 100.95)])
    assert all(r[i][1] is True for i in (1, 2, 3))           # no border along the shared edge lat 12.8


def test_the_end_of_the_waters_north_and_south_is_a_border_too(db):
    lat_n = 13.5 - 0.03                                       # about 3.3 km south of the northern edge
    r = ev(db, [cell(1, lat_n, 100.95), cell(2, 13.5 - 0.06, 100.95), cell(3, 13.6, 100.95)])
    assert r[1][1] is False and r[2][1] is True and r[3][1] is False


def test_a_small_hole_is_an_island_whose_edge_is_coast_and_whose_inside_is_not_water(db):
    hole = rect(100.95, 12.45, 100.97, 12.47)                 # about 2 x 2 km, far below the hole-size limit
    water = [gj([rect(100.80, 12.0, 101.098, 12.8)[0], hole[0]])]
    r = ev(db, [cell(1, 12.46, 100.96), cell(2, 12.46, 100.99), cell(3, 12.5, 100.95)], water=water)
    assert r[1][1] is False                                   # inside the hole: not in the waters
    assert r[2][1] is True and r[3][1] is True               # a cell next to the island is not "at the border"


def test_a_large_hole_is_a_foreign_pocket_and_its_edge_is_a_border(db):
    big = rect(100.85, 12.1, 101.05, 12.7)                    # about 22 x 66 km = ~1400 km2, above the 500 km2 limit
    water = [gj([rect(100.80, 12.0, 101.098, 12.8)[0], big[0]])]
    r = ev(db, [cell(1, 12.4, 100.825), cell(2, 12.4, 100.80 + 0.001), cell(3, 12.4, 100.95)], water=water)
    assert r[1][1] is False                                   # 2.7 km from the pocket's edge (and 2.7 km from the outer border)
    assert r[3][1] is False                                   # inside the pocket: not in the waters


def test_missing_layers_give_unknown_never_true(db):
    c = [cell(1, 12.5, 101.0)]
    assert ev(db, c, land=None) == {1: (None, None)}                       # no land: nothing is known
    assert ev(db, c, water=None) == {1: (True, None)}                     # land known, EEZ not: eez_ok is unknown
    assert ev(db, c, land=[], water=[]) == {1: (None, None)}              # empty lists count as not loaded
    assert ev(db, [], land=LAND, water=WATER) == {}


def test_bad_inputs_are_refused_before_sql(db):
    for bad in ([(1, 12.5, 101.0)], [(1, Decimal("NaN"), Decimal("101"))], [(True, Decimal("12.5"), Decimal("101"))],
                [("1", Decimal("12.5"), Decimal("101"))]):
        with pytest.raises(ValueError):
            ev(db, bad)
    for buf in (0, -5, float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            ev(db, [cell(1, 12.5, 101.0)], buf=buf)


def test_an_invalid_self_crossing_polygon_is_repaired_not_trusted_blindly(db):
    bow = gj([[[100.8, 12.0], [101.098, 12.8], [101.098, 12.0], [100.8, 12.8], [100.8, 12.0]]])      # a bow-tie
    r = ev(db, [cell(1, 12.4, 100.85), cell(2, 12.4, 101.05), cell(3, 12.7, 100.95)], water=[bow])
    assert r[1][1] in (True, False) and r[2][1] in (True, False)         # no exception; PostGIS made it valid (answer not asserted)
    assert r[3][1] is False                                              # the crossing point itself is on a border
