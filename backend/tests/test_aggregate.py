from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from ingest import aggregate as agg
from ingest.grid import cell_id

UTC = timezone.utc
CELL = cell_id(12.225, 100.725)          # covers lat 12.20..12.25, lon 100.70..100.75
NEXT_ROW = cell_id(12.275, 100.725)


def pixels(vals):
    """25 pixels of the 0.01 degree grid inside CELL, with the given values (list of 25)."""
    out, k = [], 0
    for i in range(5):
        for j in range(5):
            out.append((round(12.20 + 0.01 * i, 2), round(100.70 + 0.01 * j, 2), vals[k]))
            k += 1
    return out


def test_all_missing_gives_no_result_never_zero():
    for v in (None, float("nan"), float("inf"), float("-inf")):
        assert agg.block_mean(pixels([v] * 25), {CELL}) == {}


def test_partial_cell_mean_uses_valid_pixels_only():
    r = agg.block_mean(pixels([30.0] * 10 + [None] * 15), {CELL})
    assert r[CELL] == (30.0, 10, 25)


def test_min_valid_fraction_is_enforced_at_the_boundary():
    assert CELL not in agg.block_mean(pixels([30.0] * 12 + [None] * 13), {CELL}, min_valid_fraction=0.5)   # 12/25 = 0.48
    assert CELL in agg.block_mean(pixels([30.0] * 13 + [None] * 12), {CELL}, min_valid_fraction=0.5)       # 13/25 = 0.52


def test_nan_infinity_bool_and_text_never_enter_the_mean():
    vals = [30.0] * 20 + [float("nan"), float("inf"), float("-inf"), True, "31"]
    r = agg.block_mean(pixels(vals), {CELL})
    assert r[CELL][0] == 30.0 and r[CELL][1] == 20


def test_pixel_on_the_cell_edge_goes_to_the_cell_above_it():
    # lat 12.3 is the boundary between the rows of 12.275 and 12.325; float arithmetic would put it in the lower one
    r = agg.block_mean([(12.3, 100.7, 5.0)], {NEXT_ROW, cell_id(12.325, 100.725)})
    assert list(r) == [cell_id(12.325, 100.725)]


def test_pixels_outside_the_requested_cells_are_ignored():
    assert agg.block_mean([(40.0, 10.0, 1.0), (91.0, 0.0, 1.0)], {CELL}) == {}


def test_gradient_of_a_linear_field_and_missing_neighbours():
    lats = np.round(np.arange(12.18, 12.33, 0.01), 4)
    lons = np.round(np.arange(100.68, 100.83, 0.01), 4)
    f = 30 + 10 * (lats[:, None] - 12.2) + 0 * lons[None, :]            # 10 deg C per degree of latitude, none in longitude
    g = agg.sst_gradient_c_per_km(lats, lons, f)
    assert g[5, 5] == pytest.approx(10 / agg.KM_PER_DEG, rel=1e-9)
    assert np.isnan(g[0, :]).all() and np.isnan(g[:, 0]).all()           # array edge: no neighbours, no value
    f2 = f.copy()
    f2[5, 6] = np.nan                                                    # one missing neighbour kills that pixel's gradient
    g2 = agg.sst_gradient_c_per_km(lats, lons, f2)
    assert np.isnan(g2[5, 5]) and not np.isnan(g2[8, 8])
    assert np.isnan(agg.sst_gradient_c_per_km(lats[:2], lons, f[:2])).all()


def hours(start, n):
    return [start + timedelta(hours=i) for i in range(n)]


def test_window_max_only_inside_the_inclusive_window():
    start = datetime(2026, 11, 25, 21, 0, tzinfo=UTC)
    end = datetime(2026, 11, 26, 7, 0, tzinfo=UTC)
    t = hours(datetime(2026, 11, 25, 18, 0, tzinfo=UTC), 16)               # 18:00Z .. 09:00Z
    v = [9.0, 9.0, 9.0] + [1.0] * 11 + [9.0, 9.0]                          # spikes before 21:00Z and after 07:00Z
    assert agg.window_max(t, v, start, end) == 1.0
    v[3 + 10] = 2.5                                                         # the 07:00Z hour (last of the window) counts
    assert agg.window_max(t, v, start, end) == 2.5


def test_window_max_needs_every_hour_present_and_finite():
    start = datetime(2026, 11, 25, 21, 0, tzinfo=UTC)
    end = datetime(2026, 11, 26, 7, 0, tzinfo=UTC)
    t = hours(start, 11)
    for bad in (None, float("nan"), float("inf"), "x"):
        v = [1.0] * 11
        v[4] = bad
        assert agg.window_max(t, v, start, end) is None
    assert agg.window_max(t[:-1], [1.0] * 10, start, end) is None          # window not fully covered by the response
    assert agg.window_max([], [], start, end) is None


def test_nearest_assign_snaps_within_range_and_leaves_none_beyond():
    pts = [(12.225, 100.725, 0.4), (12.275, 100.725, None), (12.225, 101.20, 9.0)]
    r = agg.nearest_assign([CELL, NEXT_ROW], pts, max_km=15)
    assert r[CELL][0] == 0.4
    assert r[NEXT_ROW][0] == 0.4                                            # the None point is skipped, next valid one used
    far = agg.nearest_assign([CELL], [(12.225, 100.725 + 0.3, 1.0)], max_km=15)   # about 32 km away
    assert far[CELL][0] is None
    assert agg.nearest_assign([CELL], [], 15)[CELL][0] is None
    assert agg.nearest_assign([CELL], [(12.2, 100.7, float("nan"))], 15)[CELL][0] is None
