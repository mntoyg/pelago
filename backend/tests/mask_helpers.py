"""Builders and INDEPENDENT geometry for the mask and pick tests. Nothing here imports the code under test except the cell scheme.

The distance helpers use 3D unit vectors and the spherical meridian formula, not the haversine in pick/select.py and not PostGIS.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

R_KM = 6371.0087714150598   # the sphere radius PostGIS uses; the same constant on purpose, the FORMULAS are what differ

UTC = timezone.utc
RUN = date(2026, 11, 26)
SST_T = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)
WX_T = datetime(2026, 11, 26, 0, 0, tzinfo=UTC)         # issued 00:00 UTC on RUN, well inside the 48 h limit


def _vec(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def sphere_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance from the angle between the two unit vectors (atan2 of cross and dot), no haversine."""
    a, b = _vec(lat1, lon1), _vec(lat2, lon2)
    cross = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    return R_KM * math.atan2(math.sqrt(sum(c * c for c in cross)), sum(x * y for x, y in zip(a, b)))


def km_to_meridian(lat: float, dlon_deg: float) -> float:
    """Shortest distance from a point at `lat` to a meridian dlon_deg away: sin(d/R) = cos(lat) * sin(dlon)."""
    return R_KM * math.asin(math.cos(math.radians(lat)) * math.sin(math.radians(abs(dlon_deg))))


def dlon_for_km(lat: float, km: float) -> float:
    """Inverse of km_to_meridian, in degrees of longitude."""
    return math.degrees(math.asin(math.sin(km / R_KM) / math.cos(math.radians(lat))))


def rect(x0, y0, x1, y1):
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


def write_layer(folder: Path, name: str, polygons) -> None:
    """polygons: list of GeoJSON Polygon coordinate lists (rings). Written as a FeatureCollection."""
    doc = {"type": "FeatureCollection",
           "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": p}} for p in polygons]}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(doc), encoding="utf-8")


def seed_grid(db, area, run_date=RUN, sst=lambda i, cid: 29.0, no_sst=(), wave=lambda i, cid: 0.4, wind=lambda i, cid: 15.0,
              no_wx=(), issued=WX_T):
    """200 rows in grid_daily for the real Chonburi area. sst/wave/wind are functions of (index, cell_id); `no_sst` and `no_wx`
    are sets of cell ids that get NULL. Every cell has chlorophyll and depth so the FSI differs only by SST."""
    from ingest.db import Writer
    Writer(db).ensure_region(area)
    rows = []
    for i, cid in enumerate(area.cell_ids()):
        has_sst, has_wx = cid not in no_sst, cid not in no_wx
        rows.append((area.area_id, run_date, cid,
                     sst(i, cid) if has_sst else None, SST_T if has_sst else None, "erddap_mur_sst" if has_sst else None,
                     0.01 if has_sst else None, 0.8, SST_T, "erddap_viirs_chl", "daily", 20.0, "erddap_etopo_depth",
                     wave(i, cid) if has_wx else None, wind(i, cid) if has_wx else None,
                     issued if has_wx else None, "open_meteo_marine" if has_wx else None))
    with db.cursor() as cur:
        cur.executemany("""INSERT INTO pelago.grid_daily (region_id, run_date, cell_id, sst_c, sst_observed_at, sst_source,
                           sst_grad_c_per_km, chl_mg_m3, chl_observed_at, chl_source, chl_product, depth_m, depth_source,
                           wave_window_max_m, wind_window_max_kmh, wx_issued_at, wx_source)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", rows)
    return area.cell_ids()


def cell_lon_lat(area, cid):
    from ingest.grid import cell_centre
    lat, lon = cell_centre(cid)
    return float(lat), float(lon)
