"""Database writer for the ingest job (write role). Parameterised SQL only; nothing here builds SQL from data.

job_runs only ever receives a short error_code and counts (schema.sql: no URLs, no raw upstream text).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from .fetchers.base import Row

# variable -> (grid_daily columns written by that variable)
COLUMNS = {
    "sst": ("sst_c", "sst_observed_at", "sst_source", "sst_grad_c_per_km"),
    "chl": ("chl_mg_m3", "chl_observed_at", "chl_source", "chl_product"),
    "depth": ("depth_m", "depth_source"),
    "wave_wind": ("wave_window_max_m", "wind_window_max_kmh", "wx_issued_at", "wx_source"),
}
_CODE = re.compile(r"[a-z0-9_]{1,64}")
_MAX_ATTEMPT = 10   # schema.sql: attempt BETWEEN 1 AND 10


class AttemptLimit(Exception):
    pass


def row_values(variable: str, r: Row) -> tuple:
    """Row -> the column values of COLUMNS[variable]. No value means every column of the group is NULL."""
    if variable == "sst":
        if r.value is None:
            return (None, None, None, None)
        return (r.value, r.observed_at, r.source_id, r.extra.get("grad_c_per_km"))
    if variable == "chl":
        if r.value is None:
            return (None, None, None, None)
        return (r.value, r.observed_at, r.source_id, r.product)
    if variable == "depth":
        return (None, None) if r.value is None else (r.value, r.source_id)
    if variable == "wave_wind":
        wind = r.extra.get("wind_kmh")
        if r.value is None and wind is None:
            return (None, None, None, None)
        return (r.value, wind, r.observed_at, r.source_id)
    raise ValueError("unknown variable")


class Writer:
    def __init__(self, conn):
        self.conn = conn            # psycopg connection, autocommit on

    # -- locking ---------------------------------------------------------------------------------------------
    def try_lock(self, area_id: str, run_date: date) -> bool:
        """One ingest per area and date at a time (session-level advisory lock, freed when the connection closes)."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (f"ingest:{area_id}:{run_date}",))
            return bool(cur.fetchone()[0])

    # -- region ----------------------------------------------------------------------------------------------
    def ensure_region(self, area) -> None:
        lon0, lat0, lon1, lat1 = area.bbox
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO pelago.regions (region_id, country_code, timezone, min_lon, min_lat, max_lon, max_lat, config_sha256)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (region_id) DO UPDATE SET country_code = EXCLUDED.country_code, timezone = EXCLUDED.timezone,
                     min_lon = EXCLUDED.min_lon, min_lat = EXCLUDED.min_lat, max_lon = EXCLUDED.max_lon,
                     max_lat = EXCLUDED.max_lat, config_sha256 = EXCLUDED.config_sha256, updated_at = now()""",
                (area.area_id, area.country_code, area.timezone, lon0, lat0, lon1, lat1, area.sha256))

    # -- job_runs --------------------------------------------------------------------------------------------
    def start_run(self, area_id: str, run_date: date, variable: str, source_id: str, role: str) -> tuple[Any, int]:
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute(
                """SELECT COALESCE(max(attempt), 0) + 1 FROM pelago.job_runs
                   WHERE region_id = %s AND job_kind = 'ingest' AND run_date = %s AND variable = %s AND source_id = %s""",
                (area_id, run_date, variable, source_id))
            attempt = cur.fetchone()[0]
            if attempt > _MAX_ATTEMPT:
                raise AttemptLimit
            cur.execute(
                """INSERT INTO pelago.job_runs (job_kind, region_id, run_date, variable, source_id, fetcher_role, attempt, status)
                   VALUES ('ingest', %s, %s, %s, %s, %s, %s, 'running') RETURNING run_id""",
                (area_id, run_date, variable, source_id, role, attempt))
            return cur.fetchone()[0], attempt

    def finish_run(self, run_id, status: str, rows_written: int | None, data_date: date | None,
                   error_code: str | None, detail: dict[str, Any]) -> None:
        if error_code is not None and not _CODE.fullmatch(error_code):
            error_code = "error"
        with self.conn.cursor() as cur:
            cur.execute(
                """UPDATE pelago.job_runs SET status = %s, finished_at = now(), rows_written = %s, data_date = %s,
                          error_code = %s, detail = %s::jsonb WHERE run_id = %s""",
                (status, rows_written, data_date, error_code, json.dumps(detail), run_id))

    # -- grid_daily ------------------------------------------------------------------------------------------
    def write_rows(self, area_id: str, run_date: date, variable: str, rows: list[Row], run_id) -> int:
        cols = COLUMNS[variable]
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols)
        sql = (f"INSERT INTO pelago.grid_daily (region_id, run_date, cell_id, {', '.join(cols)}, ingest_run_id) "
               f"VALUES (%s, %s, %s, {', '.join(['%s'] * len(cols))}, %s) "
               f"ON CONFLICT (region_id, run_date, cell_id) DO UPDATE SET {sets}, "
               f"ingest_run_id = EXCLUDED.ingest_run_id, ingested_at = now()")
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.executemany(sql, [(area_id, run_date, r.cell_id, *row_values(variable, r), run_id) for r in rows])
        return len(rows)

    def latest_before(self, area_id: str, run_date: date, variable: str) -> list[Row]:
        """Newest earlier values per cell (for the carry-forward fallback). Only sst, chl and depth qualify."""
        if variable == "sst":
            sql = ("SELECT DISTINCT ON (cell_id) cell_id, sst_c, sst_observed_at, sst_source, NULL::text, sst_grad_c_per_km "
                   "FROM pelago.grid_daily WHERE region_id = %s AND run_date < %s AND sst_c IS NOT NULL "
                   "ORDER BY cell_id, run_date DESC")
        elif variable == "chl":
            sql = ("SELECT DISTINCT ON (cell_id) cell_id, chl_mg_m3, chl_observed_at, chl_source, chl_product, NULL::real "
                   "FROM pelago.grid_daily WHERE region_id = %s AND run_date < %s AND chl_mg_m3 IS NOT NULL "
                   "ORDER BY cell_id, run_date DESC")
        elif variable == "depth":
            sql = ("SELECT DISTINCT ON (cell_id) cell_id, depth_m, NULL::timestamptz, depth_source, NULL::text, NULL::real "
                   "FROM pelago.grid_daily WHERE region_id = %s AND run_date < %s AND depth_m IS NOT NULL "
                   "ORDER BY cell_id, run_date DESC")
        else:
            return []        # a wave/wind window maximum belongs to ONE date; it is never carried to another
        with self.conn.cursor() as cur:
            cur.execute(sql, (area_id, run_date))
            out = []
            for cid, v, t, src, prod, g in cur.fetchall():
                extra = {"grad_c_per_km": float(g)} if g is not None else {}
                out.append(Row(cid, float(v), t, src, prod, extra))
            return out
