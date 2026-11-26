"""Database access for the FSI job (write role). Parameterised SQL only; nothing here builds SQL from data.

job_runs only ever receives a short error_code and counts (schema.sql: no URLs, no raw text, no secrets).
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from .model import CellInputs, CellScore

_CODE = re.compile(r"[a-z0-9_]{1,64}")
_MAX_ATTEMPT = 10          # schema.sql: attempt BETWEEN 1 AND 10
SUBS = ("sst", "front", "chl", "depth", "moon", "season")


class AttemptLimit(Exception):
    pass


class RecommendationConflict(Exception):
    """A recommendation points at a cell whose score would become NULL or change. Never resolved by deleting picks."""
    def __init__(self, blocked_by: str, reason: str):
        super().__init__("recommendation_conflict")
        self.blocked_by, self.reason = blocked_by, reason     # blocked_by: precheck | db ; reason: unscored | changed | missing


def _f(x):
    return None if x is None else float(x)


class FsiStore:
    def __init__(self, conn):
        self.conn = conn            # psycopg connection, autocommit on

    def try_lock(self, area_id: str, run_date: date) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (f"fsi:{area_id}:{run_date}",))
            return bool(cur.fetchone()[0])

    def region_level(self, area_id: str) -> tuple[bool, str | None]:
        """(region row exists, its verification_level). The caller fails closed on anything unexpected."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT verification_level FROM pelago.regions WHERE region_id = %s", (area_id,))
            row = cur.fetchone()
        return (row is not None, row[0] if row else None)

    def read_cells(self, area_id: str, run_date: date) -> list[CellInputs]:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT cell_id, sst_c, sst_observed_at, sst_grad_c_per_km, chl_mg_m3, chl_observed_at, chl_product, depth_m
                   FROM pelago.grid_daily WHERE region_id = %s AND run_date = %s ORDER BY cell_id""", (area_id, run_date))
            return [CellInputs(r[0], _f(r[1]), r[2], _f(r[3]), _f(r[4]), r[5], r[6], _f(r[7])) for r in cur.fetchall()]

    # -- job_runs ---------------------------------------------------------------------------------------------
    def start_run(self, area_id: str, run_date: date):
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute("""SELECT COALESCE(max(attempt), 0) + 1 FROM pelago.job_runs
                           WHERE region_id = %s AND job_kind = 'fsi' AND run_date = %s""", (area_id, run_date))
            attempt = cur.fetchone()[0]
            if attempt > _MAX_ATTEMPT:
                raise AttemptLimit
            cur.execute("""INSERT INTO pelago.job_runs (job_kind, region_id, run_date, attempt, status)
                           VALUES ('fsi', %s, %s, %s, 'running') RETURNING run_id""", (area_id, run_date, attempt))
            return cur.fetchone()[0]

    def finish_run(self, run_id, status: str, rows_written: int | None, error_code: str | None, detail: dict[str, Any]):
        if error_code is not None and not _CODE.fullmatch(error_code):
            error_code = "error"
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE pelago.job_runs SET status = %s, finished_at = now(), rows_written = %s,
                           error_code = %s, detail = %s::jsonb WHERE run_id = %s""",
                        (status, rows_written, error_code, json.dumps(detail), run_id))

    # -- recommendations guard ----------------------------------------------------------------------------------
    def check_recommendations(self, area_id: str, run_date: date, model_version: str, scores: list[CellScore]) -> None:
        """Raises RecommendationConflict when a stored pick would end up on an unscored cell, or on a cell whose FSI or
        confidence no longer equals the copy stored with the pick. Picks are never deleted or edited here."""
        by_cell = {s.cell_id: s for s in scores}
        with self.conn.cursor() as cur:
            cur.execute("""SELECT cell_id, fsi, confidence FROM pelago.recommendations
                           WHERE region_id = %s AND run_date = %s AND model_version = %s""",
                        (area_id, run_date, model_version))
            recs = cur.fetchall()
        for cell_id, fsi, conf in recs:
            s = by_cell.get(cell_id)
            if s is None:
                raise RecommendationConflict("precheck", "missing")
            if not s.scored:
                raise RecommendationConflict("precheck", "unscored")
            if abs(float(fsi) - s.fsi) > 0.01 or conf != s.confidence:
                raise RecommendationConflict("precheck", "changed")

    # -- fsi_daily ----------------------------------------------------------------------------------------------
    def write_scores(self, area_id: str, run_date: date, model_version: str, scores: list[CellScore],
                     config_sha256: str, run_id) -> int:
        cols = ([f"s_{k}" for k in SUBS] + [f"a_{k}" for k in SUBS]
                + ["fsi", "confidence", "confidence_cap", "confidence_reasons"])
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols + ["config_sha256", "run_id"])
        sql = (f"INSERT INTO pelago.fsi_daily (region_id, run_date, model_version, cell_id, {', '.join(cols)}, "
               f"config_sha256, run_id) VALUES (%s, %s, %s, %s, {', '.join(['%s'] * len(cols))}, %s, %s) "
               f"ON CONFLICT (region_id, run_date, model_version, cell_id) DO UPDATE SET {sets}, computed_at = now()")
        rows = []
        for s in scores:
            # an unscored cell stores NULL everywhere: a partial set of sub-scores without an index would read as a score
            sc = [(_f(s.scores[k]) if s.scored else None) for k in SUBS]
            fr = [(_f(s.fresh[k]) if s.scored else None) for k in SUBS]
            rows.append((area_id, run_date, model_version, s.cell_id, *sc, *fr, s.fsi, s.confidence, s.confidence_cap,
                         list(s.confidence_reasons), config_sha256, run_id))
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.executemany(sql, rows)
        return len(rows)
