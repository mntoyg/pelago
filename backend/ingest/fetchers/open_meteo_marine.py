"""Waves and wind: Open-Meteo (Marine API `wave_height`, Forecast API `wind_speed_10m`). ROUTE A ONLY: Open-Meteo is free
for non-commercial use only (ARCHITECTURE.md A7). The registry refuses it on licence route B.

These are POINT forecasts, so (decision, backend/docs/ingest-dry-run.md section 3): ask for a lattice of points
(step lattice_step_deg, centred on blocks of cells; 50 points for Chonburi), take the maximum over the area's sea window
of its local date at each point (timezone=GMT is requested and the window is converted with zoneinfo), then give each
cell the value of the NEAREST lattice point whose whole window is present, if it is within max_snap_km; else None.
`observed_at` of a row is the retrieval time: Open-Meteo does not return the forecast issue time.
"""
from __future__ import annotations

import json
import math
import time as _time
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from .. import aggregate as agg
from ..timeutil import UTC, parse_utc, sea_window_utc
from .base import FetchError, HttpGet, Row, http_get

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def lattice(bbox, step: float) -> list[tuple[float, float]]:
    lon0, lat0, lon1, lat1 = bbox
    n_lat, n_lon = round((lat1 - lat0) / step), round((lon1 - lon0) / step)
    if n_lat < 1 or n_lon < 1 or n_lat * n_lon > 400:
        raise FetchError("bad_config")
    return [(round(lat0 + step * (i + 0.5), 4), round(lon0 + step * (j + 0.5), 4))
            for i in range(n_lat) for j in range(n_lon)]


def parse_points(body: bytes, variable: str, n_expected: int) -> list[tuple[list[datetime], list]]:
    """[(times_utc, values)] per requested point, in request order. Validates shape; never trusts the upstream."""
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FetchError("bad_shape") from exc
    if isinstance(data, dict) and n_expected == 1:
        data = [data]
    if not isinstance(data, list) or len(data) != n_expected:
        raise FetchError("bad_shape")
    out = []
    for p in data:
        try:
            if p["timezone"] != "GMT" or p["utc_offset_seconds"] != 0:
                raise FetchError("bad_shape")        # we asked for GMT; anything else would shift the sea window
            h = p["hourly"]
            times, vals = h["time"], h[variable]
        except (KeyError, TypeError) as exc:
            raise FetchError("bad_shape") from exc
        if not (isinstance(times, list) and isinstance(vals, list) and len(times) == len(vals)):
            raise FetchError("bad_shape")
        out.append(([parse_utc(t) for t in times], vals))
    return out


class OpenMeteoMarine:
    source_id = "open_meteo_marine"
    variable = "wave_wind"
    routes = ("A",)

    def __init__(self, http: HttpGet = http_get, sleep=_time.sleep, now=lambda: datetime.now(UTC)):
        self._http, self._sleep, self._now = http, sleep, now

    def _query(self, base: str, variable: str, pts, start: datetime, end: datetime, now: datetime, extra: dict, timeout: float):
        past = max(0, (now.date() - start.date()).days)
        ahead = max(1, (end.date() - now.date()).days + 1)
        if past > 92 or ahead > 16:
            raise FetchError("no_recent_data")      # outside what the API serves
        params = {"latitude": ",".join(f"{la:.4f}" for la, _ in pts), "longitude": ",".join(f"{lo:.4f}" for _, lo in pts),
                  "hourly": variable, "timezone": "GMT", "past_days": past, "forecast_days": ahead, **extra}
        return parse_points(self._http(base + "?" + urlencode(params, safe=","), timeout), variable, len(pts))

    def fetch(self, area, run_date: date) -> list[Row]:
        cfg, timeout = area.ingest["open_meteo"], area.ingest["http_timeout_s"]
        pts = lattice(area.bbox, cfg["lattice_step_deg"])
        start, end = sea_window_utc(run_date, area.timezone, *area.sea_window)
        now = self._now()
        waves = self._query(MARINE_URL, "wave_height", pts, start, end, now, {}, timeout)
        self._sleep(area.ingest["request_pause_s"])
        winds = self._query(FORECAST_URL, "wind_speed_10m", pts, start, end, now, {"wind_speed_unit": "kmh"}, timeout)
        return build_rows(area, pts, waves, winds, start, end, now, self.source_id)


def build_rows(area, pts, waves, winds, start, end, retrieved_at, source_id) -> list[Row]:
    cells = area.cell_ids()
    max_km = area.ingest["open_meteo"]["max_snap_km"]
    wave_pts = [(la, lo, agg.window_max(t, v, start, end)) for (la, lo), (t, v) in zip(pts, waves)]
    wind_pts = [(la, lo, agg.window_max(t, v, start, end)) for (la, lo), (t, v) in zip(pts, winds)]
    wave = agg.nearest_assign(cells, wave_pts, max_km)
    wind = agg.nearest_assign(cells, wind_pts, max_km)
    if all(wave[c][0] is None and wind[c][0] is None for c in cells):
        raise FetchError("empty_grid")
    rows = []
    for c in cells:
        w, v = wave[c][0], wind[c][0]
        rows.append(Row(c, w, retrieved_at if (w is not None or v is not None) else None, source_id, None,
                        {"wind_kmh": v}))
    return rows
