"""SST: NASA JPL MUR via NOAA ERDDAP, dataset jplMURSST41, variable analysed_sst (degree_C, 0.01 degree).

Axis order is time, latitude (ascending), longitude (MEASURED 2026-11-26, backend/docs/ingest-dry-run.md). Per cell:
mean of the valid 0.01 degree pixels (all 25 pixels, not a strided sample) when at least min_valid_fraction of them
are valid, plus the mean SST gradient (the front input) computed from the full-resolution field.
"""
from __future__ import annotations

import time as _time
from datetime import date

import numpy as np

from .. import aggregate as agg
from .base import FetchError, Fetcher, HttpGet, Row, http_get
from . import erddap

DATASET = "jplMURSST41"
RES = 0.01


class ErddapMurSst:
    source_id = "erddap_mur_sst"
    variable = "sst"
    routes = ("A", "B")

    def __init__(self, http: HttpGet = http_get, sleep=_time.sleep):
        self._http, self._sleep = http, sleep

    def fetch(self, area, run_date: date) -> list[Row]:
        timeout = area.ingest["http_timeout_s"]
        times = erddap.pick_times(self._http, DATASET, run_date, area.timezone, area.max_age_days["sst"]["max"], timeout)
        if not times:
            raise FetchError("no_recent_data")
        t = times[-1]
        self._sleep(area.ingest["request_pause_s"])
        lon0, lat0, lon1, lat1 = area.bbox
        m = area.ingest["margin_pixels"] * RES
        q = (f"analysed_sst[({erddap.iso_z(t)})][({lat0 - m:.2f}):1:({lat1 + m:.2f})][({lon0 - m:.2f}):1:({lon1 + m:.2f})]")
        body = self._http(erddap.url(DATASET, q), timeout)
        return build_rows(area, t, body, self.source_id)


def build_rows(area, observed_at, body: bytes, source_id: str) -> list[Row]:
    recs = erddap.parse_csv(body, ("latitude", "longitude", "analysed_sst"))
    if not recs:
        raise FetchError("empty_grid")
    lat = np.array([float(r["latitude"]) for r in recs])
    lon = np.array([float(r["longitude"]) for r in recs])
    val = np.array([np.nan if (v := erddap.num(r["analysed_sst"])) is None else v for r in recs])
    lats, lons = np.unique(np.round(lat, 4)), np.unique(np.round(lon, 4))
    if lats.size * lons.size != val.size or lats.size < 3 or lons.size < 3:
        raise FetchError("bad_shape")                       # not a full rectangle: truncated or reordered response
    if not (np.allclose(np.diff(lats), np.diff(lats).mean(), atol=1e-6) and np.allclose(np.diff(lons), np.diff(lons).mean(), atol=1e-6)):
        raise FetchError("bad_shape")
    field = np.full((lats.size, lons.size), np.nan)
    field[np.searchsorted(lats, np.round(lat, 4)), np.searchsorted(lons, np.round(lon, 4))] = val
    if not np.isfinite(field).any():
        raise FetchError("empty_grid")
    grad = agg.sst_gradient_c_per_km(lats, lons, field)
    cells = set(area.cell_ids())
    la_g, lo_g = np.meshgrid(lats, lons, indexing="ij")
    flat = list(zip(la_g.ravel().tolist(), lo_g.ravel().tolist()))
    sst = agg.block_mean(((a, b, v) for (a, b), v in zip(flat, field.ravel().tolist())), cells,
                         area.ingest["min_valid_fraction"]["sst"])
    gr = agg.block_mean(((a, b, v) for (a, b), v in zip(flat, grad.ravel().tolist())), cells)
    rows = []
    for cid in area.cell_ids():
        if cid in sst:
            g = gr.get(cid)
            rows.append(Row(cid, sst[cid][0], observed_at, source_id, None, {"grad_c_per_km": g[0] if g else None}))
        else:
            rows.append(Row(cid, None, None, source_id, None, {"grad_c_per_km": None}))
    return rows
