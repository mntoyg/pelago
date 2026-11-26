"""Fetchers against synthetic upstream responses (no network). Real shapes were measured on 2026-11-26."""
import json
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest
import requests

from ingest.fetchers import erddap, erddap_etopo_depth, erddap_mur_sst, erddap_viirs_chl, open_meteo_marine, registry
from ingest.fetchers.base import FetchError, http_get
from ingest.grid import cell_id
from tests.helpers import erddap_csv

UTC = timezone.utc
A = cell_id(12.225, 100.725)
B = cell_id(12.225, 100.775)
C = cell_id(12.275, 100.725)
D = cell_id(12.275, 100.775)


def mur_csv(fn, lat_range=(12.18, 12.32), lon_range=(100.68, 100.82)):
    rows = []
    for i in range(round((lat_range[1] - lat_range[0]) / 0.01) + 1):
        for j in range(round((lon_range[1] - lon_range[0]) / 0.01) + 1):
            la, lo = round(lat_range[0] + 0.01 * i, 2), round(lon_range[0] + 0.01 * j, 2)
            rows.append(("2026-11-24T09:00:00Z", la, lo, fn(la, lo)))
    return erddap_csv(["time", "latitude", "longitude", "analysed_sst"], ["UTC", "degrees_north", "degrees_east", "degree_C"], rows)


T = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)


def test_mur_block_mean_gradient_and_missing(small_area):
    # latitude gradient of 10 C per degree; the whole cell C (lat 12.25..12.30, lon 100.70..100.75) is land (NaN)
    def f(la, lo):
        return None if (12.25 <= la < 12.30 and 100.70 <= lo < 100.75) else 30 + 10 * (la - 12.2)
    rows = {r.cell_id: r for r in erddap_mur_sst.build_rows(small_area, T, mur_csv(f), "erddap_mur_sst")}
    assert set(rows) == {A, B, C, D}
    assert rows[C].value is None and rows[C].observed_at is None and rows[C].extra["grad_c_per_km"] is None
    assert rows[A].value == pytest.approx(30.2, abs=1e-9) and rows[A].observed_at == T
    assert rows[A].extra["grad_c_per_km"] == pytest.approx(10 / 111.195, rel=1e-6)


def test_mur_half_land_cell_below_the_fraction_is_missing(small_area):
    land = lambda la, lo: None if (12.20 <= la < 12.25 and 100.70 <= lo < 100.75 and (round(la * 100) % 2 == 0 or lo > 100.72)) else 30.0
    rows = {r.cell_id: r for r in erddap_mur_sst.build_rows(small_area, T, mur_csv(land), "erddap_mur_sst")}
    assert rows[A].value is None           # fewer than half of its 25 pixels are valid


def test_mur_all_nan_is_an_empty_grid_not_zeros(small_area):
    with pytest.raises(FetchError) as e:
        erddap_mur_sst.build_rows(small_area, T, mur_csv(lambda la, lo: None), "erddap_mur_sst")
    assert e.value.code == "empty_grid"


def test_mur_truncated_or_reordered_response_is_bad_shape(small_area):
    body = mur_csv(lambda la, lo: 30.0)
    with pytest.raises(FetchError) as e:
        erddap_mur_sst.build_rows(small_area, T, b"\n".join(body.split(b"\n")[:-8]) + b"\n", "erddap_mur_sst")
    assert e.value.code == "bad_shape"
    with pytest.raises(FetchError):
        erddap_mur_sst.build_rows(small_area, T, b"<html>error page</html>", "erddap_mur_sst")


def chl_csv(days):
    rows = []
    for day, fn in days:
        for la in (12.21, 12.2475, 12.285):
            for lo in (100.71, 100.7475, 100.785):
                rows.append((day, 0.0, la, lo, fn(la, lo)))
    return erddap_csv(["time", "altitude", "latitude", "longitude", "chlor_a"], ["UTC", "m", "degrees_north", "degrees_east", "mg m^-3"], rows)


def test_chl_takes_the_newest_valid_day_per_cell(small_area):
    old = lambda la, lo: 0.5
    new = lambda la, lo: 0.9 if la < 12.25 and lo < 100.75 else None        # only cell A is clear on the newest day
    body = chl_csv([("2026-11-20T12:00:00Z", old), ("2026-11-24T12:00:00Z", new)])
    rows = {r.cell_id: r for r in erddap_viirs_chl.build_rows(small_area, body, "erddap_viirs_chl")}
    assert rows[A].value == pytest.approx(0.9) and rows[A].observed_at == datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    assert rows[B].value == pytest.approx(0.5) and rows[B].observed_at == datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    assert rows[A].product == "daily"


def test_chl_cell_without_any_valid_day_is_none_and_all_cloud_is_empty_grid(small_area):
    body = chl_csv([("2026-11-24T12:00:00Z", lambda la, lo: 0.7 if la < 12.25 and lo < 100.75 else None)])
    rows = {r.cell_id: r for r in erddap_viirs_chl.build_rows(small_area, body, "erddap_viirs_chl")}
    assert rows[D].value is None and rows[D].observed_at is None and rows[D].product is None
    with pytest.raises(FetchError) as e:
        erddap_viirs_chl.build_rows(small_area, chl_csv([("2026-11-24T12:00:00Z", lambda la, lo: None)]), "x")
    assert e.value.code == "empty_grid"


def test_chl_days_outside_the_allowed_window_are_ignored(small_area):
    body = chl_csv([("2026-11-24T12:00:00Z", lambda la, lo: 0.9)])
    with pytest.raises(FetchError):
        erddap_viirs_chl.build_rows(small_area, body, "x", allowed_times=set())


def test_depth_is_minus_mean_z_and_land_is_none(small_area):
    rows_in = []
    for la in np.arange(12.2021, 12.3, 0.00417):
        for lo in np.arange(100.7021, 100.8, 0.00417):
            z = -10.0 if la < 12.25 else 5.0                    # cells A, B sea 10 m; C, D land
            rows_in.append((round(float(la), 6), round(float(lo), 6), z))
    body = erddap_csv(["latitude", "longitude", "z"], ["degrees_north", "degrees_east", ""], rows_in)
    rows = {r.cell_id: r for r in erddap_etopo_depth.build_rows(small_area, body, "erddap_etopo_depth")}
    assert rows[A].value == pytest.approx(10.0) and rows[A].observed_at is None
    assert rows[C].value is None


def test_pick_times_by_local_date_and_lookback():
    tz = "Asia/Bangkok"
    axis = erddap_csv(["time"], ["UTC"], [(f"2026-11-{d}T12:00:00Z",) for d in (10, 11, 12, 15, 16)])
    http = lambda url, timeout: axis
    # run date 26 Nov, lookback 10 days -> local dates 16..26 only: the 15 Nov observation (11 days old) is out
    got = erddap.pick_times(http, "d", date(2026, 11, 26), tz, 10, 5)
    assert [t.day for t in got] == [16]
    # an observation made after the end of the local run date must never be used for that date
    assert erddap.pick_times(http, "d", date(2026, 11, 12), tz, 10, 5)[-1].day == 12


def test_pick_times_old_run_date_asks_by_value_and_404_means_no_data():
    calls = []
    def http(url, timeout):
        calls.append(url)
        if len(calls) == 1:
            return erddap_csv(["time"], ["UTC"], [("2026-11-20T09:00:00Z",), ("2026-11-24T09:00:00Z",)])
        raise FetchError("http_404")
    assert erddap.pick_times(http, "d", date(2026, 1, 5), "Asia/Bangkok", 5, 5) == []
    assert len(calls) == 2


# ---------------------------------------------------------------- Open-Meteo

def om_payload(pts, wave_fn, tz="GMT", offset=0, key="wave_height"):
    times = [(datetime(2026, 11, 25, 18, 0) + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(16)]
    out = []
    for i, (la, lo) in enumerate(pts):
        out.append({"latitude": la, "longitude": lo, "timezone": tz, "utc_offset_seconds": offset,
                    "hourly": {"time": times, key: [wave_fn(i, h) for h in range(16)]}})
    return json.dumps(out).encode()


WIN = (datetime(2026, 11, 25, 21, 0, tzinfo=UTC), datetime(2026, 11, 26, 7, 0, tzinfo=UTC))


def test_open_meteo_lattice_for_chonburi_has_50_points_at_x05_centres():
    cfg = {"lattice_step_deg": 0.1}
    pts = open_meteo_marine.lattice((100.7, 12.2, 101.2, 13.2), cfg["lattice_step_deg"])
    assert len(pts) == 50 and pts[0] == (12.25, 100.75) and pts[-1] == (13.15, 101.15)


def test_open_meteo_window_max_and_nearest_neighbour(small_area):
    pts = [(12.25, 100.75)]                                              # one lattice point serves all four cells
    wave = open_meteo_marine.parse_points(om_payload(pts, lambda i, h: 0.3 + (1.7 if h == 9 else 0)), "wave_height", 1)
    wind = open_meteo_marine.parse_points(om_payload(pts, lambda i, h: 12.0 + (30 if h == 15 else 0), key="wind_speed_10m"), "wind_speed_10m", 1)
    rows = open_meteo_marine.build_rows(small_area, pts, wave, wind, *WIN, T, "open_meteo_marine")
    assert {r.cell_id for r in rows} == {A, B, C, D}
    # hour index 9 is 03:00Z of 26 Nov, inside the window (21:00Z..07:00Z); index 15 is 09:00Z, outside it
    assert all(r.value == pytest.approx(2.0) and r.extra["wind_kmh"] == 12.0 for r in rows)
    assert all(r.observed_at == T for r in rows)


def test_open_meteo_missing_hour_or_far_point_gives_none_not_zero(small_area):
    pts = [(12.25, 100.75)]
    wave = open_meteo_marine.parse_points(om_payload(pts, lambda i, h: None if h == 8 else 0.4), "wave_height", 1)
    wind = open_meteo_marine.parse_points(om_payload(pts, lambda i, h: 15.0, key="wind_speed_10m"), "wind_speed_10m", 1)
    rows = open_meteo_marine.build_rows(small_area, pts, wave, wind, *WIN, T, "s")
    assert all(r.value is None and r.extra["wind_kmh"] == 15.0 for r in rows)
    # a lattice point more than max_snap_km (15 km) from every cell gives nothing: all cells None -> empty_grid
    ok_wave = open_meteo_marine.parse_points(om_payload([(13.15, 101.15)], lambda i, h: 0.4), "wave_height", 1)
    ok_wind = open_meteo_marine.parse_points(om_payload([(13.15, 101.15)], lambda i, h: 15.0, key="wind_speed_10m"), "wind_speed_10m", 1)
    with pytest.raises(FetchError) as e:
        open_meteo_marine.build_rows(small_area, [(13.15, 101.15)], ok_wave, ok_wind, *WIN, T, "s")
    assert e.value.code == "empty_grid"


def test_open_meteo_nothing_at_all_is_an_empty_grid(small_area):
    pts = [(12.25, 100.75)]
    nothing = open_meteo_marine.parse_points(om_payload(pts, lambda i, h: None), "wave_height", 1)
    nothing_w = open_meteo_marine.parse_points(om_payload(pts, lambda i, h: None, key="wind_speed_10m"), "wind_speed_10m", 1)
    with pytest.raises(FetchError) as e:
        open_meteo_marine.build_rows(small_area, pts, nothing, nothing_w, *WIN, T, "s")
    assert e.value.code == "empty_grid"


def test_open_meteo_response_not_in_gmt_is_refused():
    pts = [(12.25, 100.75)]
    with pytest.raises(FetchError) as e:
        open_meteo_marine.parse_points(om_payload(pts, lambda i, h: 0.3, tz="Asia/Bangkok", offset=25200), "wave_height", 1)
    assert e.value.code == "bad_shape"


@pytest.mark.parametrize("body", [b"not json", b"{}", b"[]", json.dumps([{"timezone": "GMT"}]).encode()])
def test_open_meteo_malformed_payload_is_bad_shape(body):
    with pytest.raises(FetchError) as e:
        open_meteo_marine.parse_points(body, "wave_height", 1)
    assert e.value.code == "bad_shape"


def test_open_meteo_wrong_number_of_points_is_bad_shape():
    body = om_payload([(12.25, 100.75)], lambda i, h: 0.3)
    with pytest.raises(FetchError):
        open_meteo_marine.parse_points(body, "wave_height", 2)


# ---------------------------------------------------------------- registry and HTTP

def test_open_meteo_is_refused_on_licence_route_b(make_area):
    b = make_area(mutate=lambda raw: raw.update(licence_route="B"))
    with pytest.raises(FetchError) as e:
        registry.build("open_meteo_marine", b)
    assert e.value.code == "route_not_allowed"
    registry.build("erddap_mur_sst", b)                                # ERDDAP sources stay allowed on route B
    registry.build("open_meteo_marine", make_area())                   # and it works on route A


def test_unknown_source_is_refused(small_area):
    with pytest.raises(FetchError) as e:
        registry.build("not_a_source", small_area)
    assert e.value.code == "unknown_source"


def test_http_errors_become_short_codes_without_url_or_text(monkeypatch):
    secret_url = "https://user:pa55w0rd@example.test/path?token=SECRET123"
    def boom(*a, **k):
        raise requests.ConnectionError(f"HTTPSConnectionPool: {secret_url} failed")
    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(FetchError) as e:
        http_get("https://example.test/x", 1)
    assert e.value.code == "network_error" and "SECRET123" not in str(e.value) and "pa55w0rd" not in repr(e.value)
    monkeypatch.setattr(requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.Timeout("slow " + secret_url)))
    with pytest.raises(FetchError) as e2:
        http_get("https://example.test/x", 1)
    assert e2.value.code == "timeout"
    with pytest.raises(FetchError) as e3:
        http_get("http://example.test/x", 1)                            # plain http is refused
    assert e3.value.code == "bad_url"


def test_fetch_error_code_is_sanitised():
    assert FetchError("https://host/?token=abc").code == "error"
    assert FetchError("http_503").code == "http_503" and FetchError("http_503").retryable
    assert not FetchError("empty_grid").retryable
