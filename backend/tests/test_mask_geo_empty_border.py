"""F-27: national waters with NO border at all (every edge of the waters is coast) count as inside the EEZ.

masks/geo.py _EEZ_SQL has the branch `WHEN ST_IsEmpty(border.geom) THEN TRUE`. The other mask tests all have a real border, so the
branch was never reached. Here the waters are a lake-like rectangle completely enclosed by land: its whole boundary lies within
COAST_TOLERANCE_M of land, so border = boundary minus coast is empty. Real PostGIS on SYNTHETIC polygons (same rules as
test_mask_geo_db.py: PELAGO_TEST_ADMIN_URL of a throwaway server, PELAGO_REQUIRE_DB=1 turns a missing one into a failure).
"""
import json
import os
from decimal import Decimal

import pytest

from masks import geo
from tests.mask_helpers import rect
from tests.test_db_roundtrip import ADMIN, db  # noqa: F401  (db is a pytest fixture)

pytestmark = pytest.mark.skipif(not ADMIN and not os.environ.get("PELAGO_REQUIRE_DB"), reason="PELAGO_TEST_ADMIN_URL not set")


def gj(coords):
    return json.dumps({"type": "Polygon", "coordinates": coords})


# Land: a ring (outer 99.9..100.3 x 11.9..12.3, hole 100.0..100.1 x 12.0..12.1). Waters: exactly the hole. Nothing else.
LAND = [gj([rect(99.9, 11.9, 100.3, 12.3)[0], rect(100.0, 12.0, 100.1, 12.1)[0]])]
WATER = [gj(rect(100.0, 12.0, 100.1, 12.1))]
OPEN_LAND = [gj(rect(100.1, 11.5, 100.6, 12.6))]          # land only to the east: the western edge of the waters is a real border


def cell(i, lat, lon):
    return (i, Decimal(str(lat)), Decimal(str(lon)))


def test_precondition_the_whole_boundary_of_the_waters_is_coast(db):
    """Independent of _EEZ_SQL: the 2 km coast buffer of the land covers the entire boundary, so the border must be empty."""
    covered = db.execute(
        """SELECT extensions.ST_Covers(
                     extensions.ST_Buffer(extensions.ST_Union(extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(l), 4326))::extensions.geography, %s)::extensions.geometry,
                     extensions.ST_Boundary(extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s), 4326)))
           FROM unnest(%s::text[]) AS l""", (geo.COAST_TOLERANCE_M, WATER[0], LAND)).fetchone()[0]
    assert covered is True


def test_waters_without_any_border_count_as_inside_the_eez(db):
    r = geo.evaluate(db, [cell(1, 12.05, 100.05), cell(2, 12.0501, 100.0501)], LAND, WATER, 5000.0)
    assert r[1][1] is True and r[2][1] is True              # even 5 km "buffer" cannot refuse a cell when there is no border to be near
    assert r[1][0] is True                                   # the centre is water (inside the hole), so the cell is an ordinary sea cell


def test_a_cell_outside_the_waters_is_still_refused_when_the_border_is_empty(db):
    # centre 11 km west of the land ring: neither in the waters nor within the 2 km coast tolerance of land -> FALSE (first branch).
    # (A centre ON the land ring is inside the national-waters-plus-coast area and gives True here; is_water is what removes it.)
    r = geo.evaluate(db, [cell(1, 12.05, 99.8)], LAND, WATER, 5000.0)
    assert r[1][1] is False
    assert geo.evaluate(db, [cell(1, 12.2, 100.05)], LAND, WATER, 5000.0)[1] == (False, True)     # land centre: not water, eez flag True


def test_the_same_cell_with_a_real_border_is_refused_near_it(db):
    """Control: with land only to the east the western edge is a border, and a centre 1 km from it is refused. So the True above
    comes from the empty-border branch, not from a buffer that never refuses."""
    r = geo.evaluate(db, [cell(1, 12.05, 100.009)], OPEN_LAND, WATER, 5000.0)
    assert r[1][1] is False
