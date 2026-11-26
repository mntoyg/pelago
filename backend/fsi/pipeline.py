"""One FSI run for one area and local date: read grid_daily, score, check the stored picks, write fsi_daily, record the run.

Failure is loud and leaves fsi_daily untouched: no ingest rows, no region row, a stored recommendation that the new scores
would contradict (error code recommendation_conflict), or a database error.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

import psycopg

from .config import FsiParams
from .db import AttemptLimit, FsiStore, RecommendationConflict
from .model import effective_level, score_area

log = logging.getLogger("fsi")


@dataclass
class FsiResult:
    status: str                      # success | partial | failed
    error_code: str | None
    cells_total: int = 0
    scored: int = 0
    by_confidence: dict[str, int] = field(default_factory=dict)
    blocked_by: str | None = None


def run_fsi(area, run_date: date, store: FsiStore) -> FsiResult:
    p = FsiParams.from_area(area)
    if not store.try_lock(area.area_id, run_date):
        raise RuntimeError("another fsi run for this area and date is running")
    exists, level = store.region_level(area.area_id)
    if not exists:                       # job_runs has a foreign key to regions, so this failure cannot be recorded there
        log.error("no regions row for %s: run the ingest first", area.area_id)
        return FsiResult("failed", "no_region")
    try:
        run_id = store.start_run(area.area_id, run_date)
    except AttemptLimit:
        return FsiResult("failed", "attempt_limit")

    def fail(code: str, detail: dict | None = None, blocked_by: str | None = None) -> FsiResult:
        store.finish_run(run_id, "failed", 0, code, detail or {})
        return FsiResult("failed", code, blocked_by=blocked_by)

    cells = store.read_cells(area.area_id, run_date)
    if not cells:
        return fail("no_ingest")
    scores = score_area(cells, run_date, p, effective_level(level))
    try:
        store.check_recommendations(area.area_id, run_date, p.model_version, scores)
        n = store.write_scores(area.area_id, run_date, p.model_version, scores, p.config_sha256, run_id)
    except RecommendationConflict as exc:
        log.error("recommendation conflict (%s, %s); nothing written", exc.blocked_by, exc.reason)
        return fail("recommendation_conflict", {"blocked_by": exc.blocked_by, "reason": exc.reason}, exc.blocked_by)
    except psycopg.errors.ForeignKeyViolation:
        # the database refused it (recommendations -> fsi_daily "scored" foreign key) although the pre-check did not
        log.error("foreign key violation while writing fsi_daily; nothing written")
        return fail("recommendation_conflict", {"blocked_by": "db"}, "db")
    except Exception as exc:
        log.error("write failed: %s", type(exc).__name__)
        return fail("write_failed")
    scored = sum(1 for s in scores if s.scored)
    conf = dict(Counter(s.confidence for s in scores if s.scored))
    detail = {"cells_total": n, "cells_scored": scored, "cells_unscored": n - scored, "confidence": conf,
              "model_version": p.model_version}
    if scored == 0:
        store.finish_run(run_id, "partial", n, "no_scored_cells", detail)
        return FsiResult("partial", "no_scored_cells", n, 0, conf)
    store.finish_run(run_id, "success", n, None, detail)
    return FsiResult("success", None, n, scored, conf)
