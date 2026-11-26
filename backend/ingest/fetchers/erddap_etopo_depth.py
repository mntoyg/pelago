"""Depth: NOAA NCEI ETOPO 2022 15 arc-second via ERDDAP, dataset ETOPO_2022_v1_15s, variable z (m, positive UP).

MEASURED 2026-11-26: axes latitude, longitude (no time axis), 0.004167 degree, no NaN inside the Chonburi bbox. Per cell:
depth = minus the block mean of z when that mean is below 0 (sea), else None (a land cell has no depth; it is not 0).
The grid is static, so observed_at is None.
"""
from __future__ import annotations

import time as _time
from datetime import date

from .. import aggregate as agg
from . import erddap
from .base import FetchError, HttpGet, Row, http_get

DATASET = "ETOPO_2022_v1_15s"


class ErddapEtopoDepth:
    source_id = "erddap_etopo_depth"
    variable = "depth"
    routes = ("A", "B")

    def __init__(self, http: HttpGet = http_get, sleep=_time.sleep):
        self._http, self._sleep = http, sleep

    def fetch(self, area, run_date: date) -> list[Row]:
        lon0, lat0, lon1, lat1 = area.bbox
        body = self._http(erddap.url(DATASET, f"z[({lat0}):1:({lat1})][({lon0}):1:({lon1})]"), area.ingest["http_timeout_s"])
        return build_rows(area, body, self.source_id)


def build_rows(area, body: bytes, source_id: str) -> list[Row]:
    recs = erddap.parse_csv(body, ("latitude", "longitude", "z"))
    if not recs:
        raise FetchError("empty_grid")
    means = agg.block_mean(((float(r["latitude"]), float(r["longitude"]), erddap.num(r["z"])) for r in recs),
                           set(area.cell_ids()))
    if not means:
        raise FetchError("empty_grid")
    rows = []
    for cid in area.cell_ids():
        z = means[cid][0] if cid in means else None
        rows.append(Row(cid, -z, None, source_id) if z is not None and z < 0 else Row(cid, None, None, source_id))
    return rows
