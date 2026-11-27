"""Tests for the F-16 front check (backtest/front_check.py). Fields here are SYNTHETIC; the real-field numbers are in docs/."""
import math
from datetime import date, datetime, timezone

import numpy as np
import pytest

from backtest import front_check as fc
from backtest.inputs import PoliteHttp, RequestCap
from ingest import aggregate as agg

KM = agg.KM_PER_DEG


def csv_body(lats, lons, field):
    lines = ["time,latitude,longitude,analysed_sst", "UTC,degrees_north,degrees_east,degree_C"]
    for i, la in enumerate(lats):
        for j, lo in enumerate(lons):
            v = field[i, j]
            lines.append(f"2026-06-01T09:00:00Z,{la:.4f},{lo:.4f},{'NaN' if np.isnan(v) else f'{v:.5f}'}")
    return ("\n".join(lines) + "\n").encode()


def grid(n_lat=15, n_lon=15, lat0=12.18, lon0=100.68):
    return lat0 + 0.01 * np.arange(n_lat), lon0 + 0.01 * np.arange(n_lon)


# ---- gradient maths ----------------------------------------------------------------------------------------------------
def test_gradient_of_a_field_linear_in_latitude_is_the_slope_in_degrees_per_km():
    lats, lons = grid()
    field = np.tile((0.05 * (lats - lats[0]) * KM)[:, None], (1, lons.size))             # 0.05 degC per km northwards
    g = fc.gradient_baseline(lats, lons, field, 1)
    assert np.allclose(g[1:-1, 1:-1], 0.05, atol=1e-9) and np.isnan(g[0]).all() and np.isnan(g[:, -1]).all()


def test_longitude_spacing_uses_the_cosine_of_latitude():
    lats, lons = grid(lat0=60.0)                                                            # 60 N: a longitude degree is half as long
    field = np.tile((0.1 * (lons - lons[0]))[None, :], (lats.size, 1))                       # 0.1 degC per degree of longitude
    g = fc.gradient_baseline(lats, lons, field, 1)[1:-1, 1:-1]
    per_row = 0.1 / (KM * np.cos(np.radians(lats[1:-1])))
    assert np.allclose(g, per_row[:, None], rtol=1e-9) and per_row[0] > 0.1 / KM * 1.9


def test_module_baseline_with_s1_equals_the_ingest_function_on_a_noisy_field():
    lats, lons = grid()
    rng = np.random.default_rng(1)
    field = 29 + rng.normal(0, 0.1, (lats.size, lons.size))
    field[4:7, 4:7] = np.nan
    a, b = agg.sst_gradient_c_per_km(lats, lons, field), fc.gradient_baseline(lats, lons, field, 1)
    assert np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])


def test_independent_check_agrees_with_the_ingest_gradient_and_catches_a_wrong_one():
    lats, lons = grid(25, 35, lat0=12.2, lon0=100.7)
    rng = np.random.default_rng(2)
    field = 29 + np.cumsum(rng.normal(0, 0.02, (lats.size, lons.size)), axis=0) + np.cumsum(rng.normal(0, 0.02, (lats.size, lons.size)), axis=1)
    g = agg.sst_gradient_c_per_km(lats, lons, field)
    assert fc.independent_check(lats, lons, field, g)["max_rel_diff"] < 1e-4
    assert fc.independent_check(lats, lons, field, g * 1.1)["max_rel_diff"] > 0.05            # a 10% error in kilometres is seen
    assert fc.independent_check(lats, lons, field, np.full_like(g, np.nan))["checked"] == 0


def test_independent_check_distances_differ_in_the_two_directions():
    """Spacing in latitude and longitude are different lengths in km, so using one for both must be visible."""
    lats, lons = grid(25, 35, lat0=45.0, lon0=10.0)
    rng = np.random.default_rng(3)
    field = 15 + rng.normal(0, 0.2, (lats.size, lons.size))
    g = agg.sst_gradient_c_per_km(lats, lons, field)
    wrong = np.hypot(*(np.gradient(field, KM * 0.01, axis=1), np.gradient(field, KM * 0.01, axis=0)))     # no cos(lat) on longitude
    wrong[~np.isfinite(g)] = np.nan
    assert fc.independent_check(lats, lons, field, wrong)["max_rel_diff"] > 0.1


# ---- parsing ---------------------------------------------------------------------------------------------------------------
def test_parse_field_round_trip_and_refuses_a_truncated_body():
    lats, lons = grid(6, 7)
    field = np.arange(42, dtype=float).reshape(6, 7) / 10 + 28
    field[2, 3] = np.nan
    la, lo, f = fc.parse_field(csv_body(lats, lons, field))
    assert np.allclose(la, lats) and np.allclose(lo, lons) and np.allclose(f[~np.isnan(f)], field[~np.isnan(field)], atol=1e-4) and np.isnan(f[2, 3])
    body = csv_body(lats, lons, field).decode().splitlines()
    with pytest.raises(Exception):
        fc.parse_field(("\n".join(body[:-3]) + "\n").encode())                                # rectangle incomplete


# ---- distance to missing pixels ------------------------------------------------------------------------------------------------
def test_distance_to_missing_is_chebyshev_and_the_array_edge_is_not_missing():
    valid = np.ones((9, 9), bool)
    assert (fc.distance_to_missing(valid, cap=5) == 6).all()                                 # no missing pixel anywhere: capped, edge ignored
    valid[4, 4] = False
    d = fc.distance_to_missing(valid, cap=5)
    assert d[4, 4] == 0 and d[4, 5] == 1 and d[5, 5] == 1 and d[4, 6] == 2 and d[0, 0] == 4 and d[6, 6] == 2


# ---- the whole analysis on a synthetic field ------------------------------------------------------------------------------------
def test_analysis_has_no_gradient_on_the_array_edge_and_flags_coastal_cells(small_area):
    lats, lons = grid(15, 15)                                                                 # covers the 2 x 2 cells with a 2 pixel margin
    field = 29.0 + 0.0005 * np.add.outer(np.arange(15), np.arange(15)).astype(float)
    field[:, :2] = np.nan                                                                     # "land" along the west edge of the array
    st = fc.analyse_field(lats, lons, field, set(small_area.cell_ids()), small_area.bbox, 0.5)
    assert st["array_edge_pixels_with_gradient"] == 0 and st["same_as_s1_baseline"]
    assert st["independent"]["max_rel_diff"] < 1e-4
    assert st["cells"]["with_sst_and_gradient"] == 4 and st["cells"]["edge_ring"] == 4        # a 2 x 2 area is all outer ring
    assert 0 < st["valid_sst_share"] < 1 and st["by_distance_to_missing"][0]["from_px"] == 1


def test_a_gradient_spike_at_the_coast_shows_up_as_coastal_cells_in_the_top(small_area):
    lats, lons = grid(15, 15)
    rng = np.random.default_rng(4)
    field = 29.0 + rng.normal(0, 0.001, (15, 15))
    field[:, :3] = np.nan                                                                      # column 2 (lon 100.70) is the first pixel column of the west cells
    field[:, 3] = 31.0                                                                         # an artificial step next to the missing pixels
    st = fc.analyse_field(lats, lons, field, set(small_area.cell_ids()), small_area.bbox, 0.5)
    assert st["top20"]["cells"] >= 1 and st["top20"]["coastal_share_of_top"] == 1.0


# ---- the live path, with a fake fetcher ------------------------------------------------------------------------------------------
class FakeFetcher:
    def __init__(self, bodies, rows):
        self.bodies, self.rows, self._http, self._sleep = bodies, rows, None, None

    def fetch(self, area, run_date):
        for b in self.bodies:
            self._http("https://example.invalid/x", 1)
        return self.rows


def test_fetch_field_counts_requests_shares_the_counter_and_obeys_the_cap(monkeypatch, small_area):
    lats, lons = grid(6, 7)
    field = np.full((6, 7), 29.5)
    bodies = [b"time\nUTC\n2026-06-01T09:00:00Z\n", csv_body(lats, lons, field)]
    served = []

    def fake_inner(url, timeout):
        served.append(url)
        return bodies[(len(served) - 1) % 2]
    from ingest.fetchers.base import Row
    obs = datetime(2026, 6, 1, 9, tzinfo=timezone.utc)
    rows = [Row(small_area.cell_ids()[0], 29.5, obs, "erddap_mur_sst")]

    def build(source_id, area, **kw):
        f = FakeFetcher(bodies, rows)
        f._http = fake_inner
        return f
    monkeypatch.setattr(fc.registry, "build", build)
    _rows, observed, (la, lo, f), http = fc.fetch_field(small_area, date(2026, 6, 1), None, pause_s=0, max_requests=3)
    assert observed == obs and http.count == 2 and f.shape == (6, 7)
    with pytest.raises(RequestCap):                                                              # the shared counter goes on from 2; cap is 3
        fc.fetch_field(small_area, date(2026, 6, 2), http)
    assert http.count == 3 and len(served) == 3                                                  # the fourth request was never made
