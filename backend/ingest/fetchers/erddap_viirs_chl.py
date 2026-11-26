"""Chlorophyll-a: VIIRS S-NPP near-real-time daily via NOAA ERDDAP, dataset nesdisVHNchlaDaily, variable chlor_a (mg m^-3).

MEASURED 2026-11-26: axes time, altitude (one value 0.0), latitude (DESCENDING, so ranges are written high:low),
longitude; 0.0375 degree pixels; NaN where cloudy; newest time was 11 days old. Per cell: the newest day inside the
look-back window (max_age_days.chl.max) on which the cell has at least one valid pixel; that day is its observed_at.
"""
from __future__ import annotations

import time as _time
from collections import defaultdict
from datetime import date

from .. import aggregate as agg
from . import erddap
from .base import FetchError, HttpGet, Row, http_get
from ..timeutil import parse_utc


class ErddapViirsChl:
    source_id = "erddap_viirs_chl"
    variable = "chl"
    routes = ("A", "B")
    dataset = "nesdisVHNchlaDaily"

    def __init__(self, http: HttpGet = http_get, sleep=_time.sleep):
        self._http, self._sleep = http, sleep

    def fetch(self, area, run_date: date) -> list[Row]:
        timeout = area.ingest["http_timeout_s"]
        times = erddap.pick_times(self._http, self.dataset, run_date, area.timezone, area.max_age_days["chl"]["max"], timeout)
        if not times:
            raise FetchError("no_recent_data")
        self._sleep(area.ingest["request_pause_s"])
        lon0, lat0, lon1, lat1 = area.bbox
        t0, t1 = erddap.iso_z(times[0]), erddap.iso_z(times[-1])
        tail = f"[({lat1}):1:({lat0})][({lon0}):1:({lon1})]"
        try:
            body = self._http(erddap.url(self.dataset, f"chlor_a[({t0}):1:({t1})][0:1:0]{tail}"), timeout)
        except FetchError as exc:
            if exc.code not in ("http_400", "http_404"):
                raise
            # some chlorophyll grids have no altitude axis (the prototype retries the same way)
            self._sleep(area.ingest["request_pause_s"])
            body = self._http(erddap.url(self.dataset, f"chlor_a[({t0}):1:({t1})]{tail}"), timeout)
        return build_rows(area, body, self.source_id, set(times))


def build_rows(area, body: bytes, source_id: str, allowed_times: set | None = None) -> list[Row]:
    recs = erddap.parse_csv(body, ("time", "latitude", "longitude", "chlor_a"))
    if not recs:
        raise FetchError("empty_grid")
    cells = set(area.cell_ids())
    by_day: dict[str, list] = defaultdict(list)
    for r in recs:
        by_day[r["time"]].append((float(r["latitude"]), float(r["longitude"]), erddap.num(r["chlor_a"])))
    newest: dict[int, tuple[float, object]] = {}
    for day in sorted(by_day):                       # oldest first, so a newer day overwrites an older one
        t = parse_utc(day)
        if allowed_times is not None and t not in allowed_times:
            continue
        for cid, (mean, _n, _tot) in agg.block_mean(by_day[day], cells).items():
            newest[cid] = (mean, t)
    if not newest:
        raise FetchError("empty_grid")
    return [Row(cid, newest[cid][0], newest[cid][1], source_id, "daily") if cid in newest
            else Row(cid, None, None, source_id, None) for cid in area.cell_ids()]
