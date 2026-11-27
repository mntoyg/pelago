"""Database access for the pick job (write role). Parameterised SQL only."""
from __future__ import annotations

from datetime import date

from ingest.grid import cell_centre
from masks.db import AttemptLimit, _finish_run, _start_run          # noqa: F401  (AttemptLimit is re-exported)
from .select import Candidate


class PickStore:
    def __init__(self, conn):
        self.conn = conn            # psycopg connection, autocommit on

    def try_lock(self, area_id: str, run_date: date) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (f"pick:{area_id}:{run_date}",))
            return bool(cur.fetchone()[0])

    def region_exists(self, area_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pelago.regions WHERE region_id = %s", (area_id,))
            return cur.fetchone() is not None

    def start_run(self, area_id: str, run_date: date):
        return _start_run(self.conn, "pick", area_id, run_date)

    def finish_run(self, run_id, status, rows_written, error_code, detail):
        _finish_run(self.conn, run_id, status, rows_written, error_code, detail)

    def candidates(self, area_id: str, run_date: date, boat_class: str, model_version: str):
        """Eligible mask rows that also have a score. Returns (Candidate list, {cell_id: (confidence, legal_status)})."""
        with self.conn.cursor() as cur:
            cur.execute("""SELECT m.cell_id, f.fsi, f.confidence, m.legal_status
                           FROM pelago.cell_mask_daily m
                           JOIN pelago.fsi_daily f ON f.region_id = m.region_id AND f.run_date = m.run_date
                                AND f.model_version = %s AND f.cell_id = m.cell_id
                           WHERE m.region_id = %s AND m.run_date = %s AND m.boat_class = %s
                             AND m.eligible AND f.scored
                           ORDER BY m.cell_id""", (model_version, area_id, run_date, boat_class))
            rows = cur.fetchall()
        cands, meta = [], {}
        for cid, fsi, conf, legal in rows:
            lat, lon = cell_centre(cid)
            cands.append(Candidate(cid, float(lat), float(lon), float(fsi)))
            meta[cid] = (conf, legal)
        return cands, meta

    def write_picks(self, area_id: str, run_date: date, boat_class: str, model_version: str, picks, meta, run_id) -> int:
        """Replace this date's picks for the boat class in one transaction (idempotent). The foreign keys to an eligible
        mask row and to a scored cell are the database's own refusal if anything here were wrong."""
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute("""DELETE FROM pelago.recommendations
                           WHERE region_id = %s AND run_date = %s AND boat_class = %s AND model_version = %s""",
                        (area_id, run_date, boat_class, model_version))
            for rank, c in enumerate(picks, start=1):
                legal = meta[c.cell_id][1]
                cur.execute("""INSERT INTO pelago.recommendations (region_id, run_date, boat_class, model_version, pick_rank,
                                   cell_id, fsi, confidence, legal_status, run_id)
                               SELECT %s, %s, %s, %s, %s, %s, f.fsi, f.confidence, %s, %s
                               FROM pelago.fsi_daily f WHERE f.region_id = %s AND f.run_date = %s AND f.model_version = %s
                                    AND f.cell_id = %s""",
                            (area_id, run_date, boat_class, model_version, rank, c.cell_id, legal, run_id,
                             area_id, run_date, model_version, c.cell_id))
        return len(picks)
