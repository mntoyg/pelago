"""Daily compute order for one area and local date: mask -> fsi -> pick, each step with its own job_runs row.

* The mask runs first and, in the same transaction that writes it, deletes the date's old picks for these boat classes (a pick
  may only exist for a mask row that is eligible, so old picks cannot survive a new mask). If a later step fails the date has NO
  picks rather than stale ones; the failure is visible in job_runs.
* A step that fails stops the run; the steps after it get a job_runs row with status 'skipped' and the reason in detail.
* FSI 'partial' (no scored cell) is not a failure: the pick step then stores no spots and says so.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import psycopg

from fsi.db import FsiStore
from fsi.pipeline import run_fsi
from ingest.config import AreaConfig
from masks.db import MaskStore
from masks.pipeline import run_mask
from pick.db import PickStore
from pick.pipeline import run_pick

log = logging.getLogger("compute")


@dataclass
class ComputeResult:
    mask: object
    fsi: object | None
    pick: object | None

    @property
    def status(self) -> str:
        steps = [s for s in (self.mask, self.fsi, self.pick) if s is not None]
        if len(steps) < 3 or any(s.status == "failed" for s in steps):
            return "failed"
        return "success" if all(s.status == "success" for s in steps) else "partial"


def _skipped(conn, kind: str, area_id: str, run_date: date, reason: str) -> None:
    """A job_runs row for a step that did not run. Best effort: the foreign key to regions may be what made the run fail."""
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("""SELECT COALESCE(max(attempt), 0) + 1 FROM pelago.job_runs
                           WHERE region_id = %s AND job_kind = %s AND run_date = %s""", (area_id, kind, run_date))
            attempt = cur.fetchone()[0]
            if attempt > 10:
                return
            cur.execute("""INSERT INTO pelago.job_runs (job_kind, region_id, run_date, attempt, status, finished_at, detail)
                           VALUES (%s, %s, %s, %s, 'skipped', now(), %s::jsonb)""",
                        (kind, area_id, run_date, attempt, json.dumps({"reason": reason})))
    except psycopg.Error as exc:
        log.warning("could not record skipped %s: %s", kind, type(exc).__name__)


def run_compute(area: AreaConfig, run_date: date, conn, boat_classes=("small",), layers_dir: Path | None = None) -> ComputeResult:
    mask = run_mask(area, run_date, MaskStore(conn), boat_classes, layers_dir, clear_picks=True)
    if mask.status == "failed":
        for kind in ("fsi", "pick"):
            _skipped(conn, kind, area.area_id, run_date, "mask_failed")
        return ComputeResult(mask, None, None)
    fsi = run_fsi(area, run_date, FsiStore(conn))
    if fsi.status == "failed":
        _skipped(conn, "pick", area.area_id, run_date, "fsi_failed")
        return ComputeResult(mask, fsi, None)
    return ComputeResult(mask, fsi, run_pick(area, run_date, PickStore(conn), boat_classes))
