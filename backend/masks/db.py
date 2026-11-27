"""Database access for the mask job (write role). Parameterised SQL only. job_runs gets a short error_code and counts only."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

_CODE = re.compile(r"[a-z0-9_]{1,64}")
_MAX_ATTEMPT = 10          # schema.sql: attempt BETWEEN 1 AND 10
COLS = ("is_water", "eez_ok", "disputed_ok", "protected_ok", "closure_ok", "boat_zone_ok", "legal_status", "forecast_ok",
        "sea_state_level", "sea_reason_code", "legal_unknown_allowed", "eligible", "exclusion_codes")


class AttemptLimit(Exception):
    pass


@dataclass(frozen=True)
class CellWx:
    cell_id: int
    wave_m: float | None
    wind_kmh: float | None
    issued_at: datetime | None


def _f(x):
    return None if x is None else float(x)


class MaskStore:
    def __init__(self, conn):
        self.conn = conn            # psycopg connection, autocommit on

    def try_lock(self, area_id: str, run_date: date) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (f"mask:{area_id}:{run_date}",))
            return bool(cur.fetchone()[0])

    def region_exists(self, area_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pelago.regions WHERE region_id = %s", (area_id,))
            return cur.fetchone() is not None

    def start_run(self, area_id: str, run_date: date):
        return _start_run(self.conn, "mask", area_id, run_date)

    def finish_run(self, run_id, status: str, rows_written: int | None, error_code: str | None, detail: dict[str, Any]):
        _finish_run(self.conn, run_id, status, rows_written, error_code, detail)

    def read_cells(self, area_id: str, run_date: date) -> list[CellWx]:
        with self.conn.cursor() as cur:
            cur.execute("""SELECT cell_id, wave_window_max_m, wind_window_max_kmh, wx_issued_at FROM pelago.grid_daily
                           WHERE region_id = %s AND run_date = %s ORDER BY cell_id""", (area_id, run_date))
            return [CellWx(r[0], _f(r[1]), _f(r[2]), r[3]) for r in cur.fetchall()]

    def write_mask(self, area_id: str, run_date: date, rows: list[dict], boat_classes: list[str], clear_picks: bool) -> int:
        """Upsert all rows in ONE transaction. With clear_picks the day's picks for these boat classes are deleted first
        (the orchestrated run regenerates them in the pick step, after the mask). Without it, a mask change that would make a
        picked cell ineligible fails on the foreign key and nothing is written."""
        cols = ", ".join(COLS)
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLS)
        sql = (f"INSERT INTO pelago.cell_mask_daily (region_id, run_date, boat_class, cell_id, {cols}) "
               f"VALUES (%s, %s, %s, %s, {', '.join(['%s'] * len(COLS))}) "
               f"ON CONFLICT (region_id, run_date, boat_class, cell_id) DO UPDATE SET {sets}")
        data = [(area_id, run_date, r["boat_class"], r["cell_id"], *(r[c] for c in COLS)) for r in rows]
        with self.conn.transaction(), self.conn.cursor() as cur:
            if clear_picks:
                cur.execute("""DELETE FROM pelago.recommendations
                               WHERE region_id = %s AND run_date = %s AND boat_class = ANY(%s)""",
                            (area_id, run_date, boat_classes))
            cur.executemany(sql, data)
        return len(data)


def _start_run(conn, kind: str, area_id: str, run_date: date):
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("""SELECT COALESCE(max(attempt), 0) + 1 FROM pelago.job_runs
                       WHERE region_id = %s AND job_kind = %s AND run_date = %s""", (area_id, kind, run_date))
        attempt = cur.fetchone()[0]
        if attempt > _MAX_ATTEMPT:
            raise AttemptLimit
        cur.execute("""INSERT INTO pelago.job_runs (job_kind, region_id, run_date, attempt, status)
                       VALUES (%s, %s, %s, %s, 'running') RETURNING run_id""", (kind, area_id, run_date, attempt))
        return cur.fetchone()[0]


def _finish_run(conn, run_id, status: str, rows_written: int | None, error_code: str | None, detail: dict[str, Any]):
    if error_code is not None and not _CODE.fullmatch(error_code):
        error_code = "error"
    with conn.cursor() as cur:
        cur.execute("""UPDATE pelago.job_runs SET status = %s, finished_at = now(), rows_written = %s,
                       error_code = %s, detail = %s::jsonb WHERE run_id = %s""",
                    (status, rows_written, error_code, json.dumps(detail), run_id))
