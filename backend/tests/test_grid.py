"""pelago-cell-v1 in Python must equal pelago.cell_id() in db/schema.sql (same vectors, same rounding)."""
from decimal import Decimal
from fractions import Fraction

import pytest

from ingest.grid import CoordinateError, cell_centre, cell_id, cells_in_bbox

# vectors copied from the comment block in backend/db/schema.sql (the SQL function passes them in db/tests/schema_test.sql)
VECTORS = [
    (12.306, 100.924, 14736818, (Decimal("12.3250"), Decimal("100.9250"))),
    (12.3, 100.7, 14736814, (Decimal("12.3250"), Decimal("100.7250"))),        # exactly on an edge
    (12.2999, 100.7, 14729614, (Decimal("12.2750"), Decimal("100.7250"))),     # just below the edge: previous row
    (0, 0, 12963600, (Decimal("0.0250"), Decimal("0.0250"))),
    (-0.0001, -0.0001, 12956399, (Decimal("-0.0250"), Decimal("-0.0250"))),
    (-90, -180, 0, None),
    (89.9999, 179.9999, 25919999, None),
]


@pytest.mark.parametrize("lat,lon,expected,centre", VECTORS)
def test_vectors(lat, lon, expected, centre):
    assert cell_id(lat, lon) == expected
    if centre:
        assert cell_centre(expected) == centre


def test_edge_float_is_not_misplaced():
    # (12.3 + 90) / 0.05 = 2045.9999999999998 in binary floating point: a float floor() would give row 2045, not 2046
    assert (12.3 + 90) / 0.05 < 2046
    assert cell_id(12.3, 100.7) // 7200 == 2046


@pytest.mark.parametrize("lat,lon", [(90, 0), (0, 180), (-90.0001, 0), (0, -180.0001), (float("nan"), 0), (0, float("inf")),
                                     (float("-inf"), 0), (True, 0), ("abc", 0), (None, 0)])
def test_out_of_range_or_not_a_number_is_rejected(lat, lon):
    with pytest.raises(CoordinateError):
        cell_id(lat, lon)


def test_decimal_and_string_inputs_agree_with_float():
    assert cell_id("12.3", "100.7") == cell_id(Decimal("12.3"), Decimal("100.7")) == cell_id(12.3, 100.7)


def test_matches_an_independent_exact_rational_implementation_on_edges():
    def exact(lat, lon):          # Fractions, no floats: floor((x + offset) / 0.05) with x rounded half away to 4 decimals
        def r(x):
            v = Fraction(str(x)) * 10000
            return int(v + Fraction(1, 2)) if v >= 0 else -int(-v + Fraction(1, 2))
        return ((r(lat) + 900000) // 500) * 7200 + (r(lon) + 1800000) // 500
    for i in range(0, 3000):
        lat, lon = round(i * 0.01, 2), round(100 + i * 0.01, 2)      # many of these are exactly on a 0.05 edge
        assert cell_id(lat, lon) == exact(lat, lon)


def test_bbox_cells_chonburi():
    cells = cells_in_bbox(100.7, 12.2, 101.2, 13.2)
    assert len(cells) == 200 and len(set(cells)) == 200
    assert cells[0] == cell_id(12.225, 100.725) and cells[-1] == cell_id(13.175, 101.175)
    assert cell_centre(cells[0]) == (Decimal("12.2250"), Decimal("100.7250"))


def test_bbox_off_grid_or_empty_is_rejected():
    for bad in ((100.71, 12.2, 101.2, 13.2), (100.7, 12.2, 100.7, 13.2), (101.2, 12.2, 100.7, 13.2)):
        with pytest.raises(CoordinateError):
            cells_in_bbox(*bad)
