"""Unit tests (no database) for the spacing and ranking rule of the pick step."""
import math

import pytest

from ingest.grid import cell_centre, cell_id
from pick.select import MAX_PICKS, Candidate, haversine_km, pick
from tests.mask_helpers import sphere_km

BBOX = (100.7, 12.2, 101.2, 13.2)


def cand(lat, lon, fsi, cid=None):
    return Candidate(cid if cid is not None else cell_id(lat, lon), lat, lon, fsi)


def grid(rows, cols, fsi=lambda r, c: 50.0):
    """A block of real cell centres, row r (south to north) and column c (west to east) from the south-west corner."""
    out = []
    for r in range(rows):
        for c in range(cols):
            lat, lon = 12.225 + 0.05 * r, 100.725 + 0.05 * c
            out.append(cand(round(lat, 4), round(lon, 4), fsi(r, c)))
    return out


def test_distance_agrees_with_an_independent_calculation():
    pts = [(12.225, 100.725), (12.275, 100.725), (12.225, 100.775), (13.175, 101.175), (12.7, 100.9), (12.3, 101.1)]
    for a in pts:
        for b in pts:
            assert haversine_km(*a, *b) == pytest.approx(sphere_km(*a, *b), rel=1e-9, abs=1e-9)


def test_spacing_exactly_at_just_below_and_just_above_the_limit():
    a, b = cand(12.225, 100.725, 90.0), cand(12.225, 100.825, 80.0)           # two cells two columns apart (about 10.9 km)
    d = haversine_km(a.lat, a.lon, b.lat, b.lon)
    assert d == pytest.approx(sphere_km(a.lat, a.lon, b.lat, b.lon), rel=1e-12) and 10.5 < d < 11.5
    assert len(pick([a, b], BBOX, d)[0]) == 2                  # exactly at the limit: allowed ("at least")
    assert len(pick([a, b], BBOX, d * (1 + 1e-9))[0]) == 1     # a hair below the needed distance: the second is refused
    assert len(pick([a, b], BBOX, d * (1 - 1e-9))[0]) == 2     # a hair above: allowed
    assert [c.cell_id for c in pick([a, b], BBOX, d * 1.5)[0]] == [a.cell_id]


def test_spacing_is_in_kilometres_not_cell_steps():
    # one cell apart is about 5.4 to 5.6 km: below 10 km, above 5 km (design risk R3: the old 5 km rule did nothing)
    a, b, c = cand(12.225, 100.725, 90.0), cand(12.225, 100.775, 80.0), cand(12.275, 100.725, 70.0)
    assert len(pick([a, b, c], BBOX, 5.0)[0]) == 3
    assert [x.cell_id for x in pick([a, b, c], BBOX, 10.0)[0]] == [a.cell_id]
    # two cells diagonal (one step in each axis) are about 7.8 km apart: still too close for 10 km
    d = cand(12.275, 100.775, 60.0)
    assert [x.cell_id for x in pick([a, d], BBOX, 10.0)[0]] == [a.cell_id]


def test_every_pair_in_the_result_respects_the_spacing_on_a_full_grid():
    cells = grid(20, 10, fsi=lambda r, c: 50 + (r * 7 + c * 3) % 40)
    chosen, dropped = pick(cells, BBOX, 10.0)
    assert dropped == 0 and 3 <= len(chosen) <= MAX_PICKS
    for i, x in enumerate(chosen):
        for y in chosen[i + 1:]:
            assert sphere_km(x.lat, x.lon, y.lat, y.lon) >= 10.0
    assert [c.fsi for c in chosen] == sorted((c.fsi for c in chosen), reverse=True)
    assert chosen[0].fsi == max(c.fsi for c in cells)


def test_at_most_five_even_with_hundreds_of_spread_out_candidates():
    assert len(pick(grid(20, 10), BBOX, 10.0)[0]) == 5
    with pytest.raises(ValueError):
        pick(grid(2, 2), BBOX, 10.0, limit=6)
    with pytest.raises(ValueError):
        pick(grid(2, 2), BBOX, 10.0, limit=0)


def test_fewer_than_three_eligible_cells_returns_what_exists_never_pads():
    cells = grid(1, 3)
    assert pick([], BBOX, 10.0) == ([], 0)                                    # empty area
    assert len(pick(cells[:1], BBOX, 10.0)[0]) == 1
    assert len(pick(cells[:2], BBOX, 10.0)[0]) == 1                           # neighbours are about 5.4 km apart
    assert len(pick(cells[:2], BBOX, 5.0)[0]) == 2
    assert len(pick(cells, BBOX, 1.0)[0]) == 3
    assert len(pick(cells, BBOX, 10.0)[0]) == 2                               # three cells in a row, the middle is too close


def test_ties_go_to_the_lower_cell_id_and_duplicates_are_ignored():
    a, b = cand(12.225, 100.725, 80.0), cand(13.175, 101.175, 80.0)
    assert [c.cell_id for c in pick([b, a], BBOX, 10.0)[0]] == sorted([a.cell_id, b.cell_id])
    assert len(pick([a, a, a], BBOX, 10.0)[0]) == 1


def test_the_same_cell_id_twice_with_different_coordinates_is_picked_once():
    a, b = Candidate(7, 12.225, 100.725, 80.0), Candidate(7, 13.175, 101.175, 70.0)      # conflicting rows for one cell id
    assert [c.cell_id for c in pick([a, b], BBOX, 10.0)[0]] == [7]


@pytest.mark.parametrize("bad", [
    Candidate(1, math.nan, 100.9, 50.0), Candidate(2, 12.5, math.nan, 50.0), Candidate(3, 12.5, 100.9, math.nan),
    Candidate(4, math.inf, 100.9, 50.0), Candidate(5, 12.5, -math.inf, 50.0), Candidate(6, 12.5, 100.9, math.inf),
    Candidate(7, 12.5, 100.9, -0.1), Candidate(8, 12.5, 100.9, 100.1), Candidate(9, 91.0, 100.9, 50.0),
    Candidate(10, 12.5, 181.0, 50.0),
    Candidate(11, 12.1, 100.9, 50.0), Candidate(12, 12.5, 100.69, 50.0), Candidate(13, 13.21, 100.9, 50.0),
    Candidate(14, 12.5, 101.21, 50.0),                                            # outside the area bbox
    Candidate(True, 12.5, 100.9, 50.0), Candidate(15, True, 100.9, 50.0), Candidate(16, 12.5, 100.9, "50"),
])
def test_invalid_or_out_of_bbox_candidates_are_dropped_and_counted_never_picked(bad):
    good = cand(12.225, 100.725, 40.0)
    chosen, dropped = pick([bad, good], BBOX, 10.0)
    assert [c.cell_id for c in chosen] == [good.cell_id] and dropped == 1


def test_the_bbox_edge_cell_centres_are_inside():
    lo, hi = cand(12.225, 100.725, 50.0), cand(13.175, 101.175, 50.0)
    assert len(pick([lo, hi], BBOX, 10.0)[0]) == 2


@pytest.mark.parametrize("bad", [0, -1, math.nan, math.inf, True, None, "10"])
def test_bad_spacing_values_are_refused(bad):
    with pytest.raises(ValueError):
        pick(grid(1, 1), BBOX, bad)


def test_cell_centres_used_in_tests_are_real_cell_centres():
    lat, lon = cell_centre(cell_id(12.225, 100.725))
    assert (float(lat), float(lon)) == (12.225, 100.725)
