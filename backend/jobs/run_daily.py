"""Run one area-local daily cycle: ingest, then compute (mask -> FSI -> pick)."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fsi.db import FsiStore
from fsi.pipeline import FsiResult, run_fsi
from ingest.config import AreaConfig, ConfigError, load_area
from ingest.db import Writer
from ingest.pipeline import VariableResult, run_ingest
from ingest.run import parse_date

log = logging.getLogger("jobs.daily")
_AUTO = object()
_ERROR_CODE = re.compile(r"^[a-z0-9_]{1,64}$")
_INGEST_VARIABLES = ("sst", "chl", "depth", "wave_wind")
_COMPUTE_KINDS = ("mask", "fsi", "pick")


@dataclass(frozen=True)
class DailyResult:
    status: str
    ingest: tuple[VariableResult, ...] = ()
    fsi: FsiResult | None = None
    compute: object | None = None
    already_complete: bool = False
    error_code: str | None = None
    hook_status: str = "not_run"


def _safe_error_code(value: object) -> str:
    text = str(value or "internal_error")
    return text if _ERROR_CODE.fullmatch(text) else "internal_error"


def _load_compute_pipeline() -> Callable | None:
    """Return the merged mask -> FSI -> pick pipeline, or None when that module is not present."""
    try:
        from compute.pipeline import run_compute
    except ModuleNotFoundError as exc:
        if exc.name == "compute":
            return None
        raise
    return run_compute


def _latest_ingest_rows(conn, area_id: str, run_date: date):
    return conn.execute(
        """SELECT DISTINCT ON (variable) variable, status, finished_at
           FROM pelago.job_runs
           WHERE region_id = %s AND run_date = %s AND job_kind = 'ingest'
           ORDER BY variable, started_at DESC, attempt DESC, source_id DESC""",
        (area_id, run_date),
    ).fetchall()


def _latest_compute_rows(conn, area_id: str, run_date: date):
    return conn.execute(
        """SELECT DISTINCT ON (job_kind) job_kind, status, finished_at, detail
           FROM pelago.job_runs
           WHERE region_id = %s AND run_date = %s AND job_kind IN ('mask', 'fsi', 'pick')
           ORDER BY job_kind, started_at DESC, attempt DESC""",
        (area_id, run_date),
    ).fetchall()


def _already_completed(conn, area: AreaConfig, run_date: date, compute_enabled: bool) -> str | None:
    """Return the previous complete status; failures or newer ingest data allow a retry."""
    region = conn.execute(
        "SELECT config_sha256 FROM pelago.regions WHERE region_id = %s", (area.area_id,)
    ).fetchone()
    if not region or region[0] != area.sha256:
        return None

    ingest_rows = _latest_ingest_rows(conn, area.area_id, run_date)
    if len(ingest_rows) != len(_INGEST_VARIABLES):
        return None
    if any(row[1] not in ("success", "partial") or row[2] is None for row in ingest_rows):
        return None
    latest_ingest_finish = max(row[2] for row in ingest_rows)

    compute_rows = {row[0]: row for row in _latest_compute_rows(conn, area.area_id, run_date)}
    if set(compute_rows) != set(_COMPUTE_KINDS):
        return None
    if any(row[2] is None or row[2] < latest_ingest_finish for row in compute_rows.values()):
        return None

    if compute_enabled:
        if any(compute_rows[kind][1] not in ("success", "partial") for kind in _COMPUTE_KINDS):
            return None
        statuses = [row[1] for row in compute_rows.values()]
    else:
        if compute_rows["mask"][1] != "skipped" or compute_rows["pick"][1] != "skipped":
            return None
        if compute_rows["mask"][3].get("reason") != "not_built" or compute_rows["pick"][3].get("reason") != "not_built":
            return None
        if compute_rows["fsi"][1] not in ("success", "partial"):
            return None
        statuses = [compute_rows["fsi"][1]]

    if any(row[1] == "partial" for row in ingest_rows) or "partial" in statuses:
        return "partial"
    return "success"


def _record_skipped(conn, kind: str, area_id: str, run_date: date, reason: str) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """SELECT COALESCE(max(attempt), 0) + 1 FROM pelago.job_runs
               WHERE region_id = %s AND job_kind = %s AND run_date = %s""",
            (area_id, kind, run_date),
        )
        attempt = cur.fetchone()[0]
        if attempt > 10:
            return
        cur.execute(
            """INSERT INTO pelago.job_runs (job_kind, region_id, run_date, attempt, status, finished_at, detail)
               VALUES (%s, %s, %s, %s, 'skipped', now(), %s::jsonb)""",
            (kind, area_id, run_date, attempt, json.dumps({"reason": reason})),
        )


def run_mask_pick_hook(area: AreaConfig, run_date: date, conn, compute_pipeline: Callable | None,
                       *, skip_reason: str = "not_built"):
    """Run the merged compute pipeline or record the explicit pre-merge skip path."""
    if compute_pipeline is not None:
        return compute_pipeline(area, run_date, conn, ("small",))
    for kind in ("mask", "pick"):
        _record_skipped(conn, kind, area.area_id, run_date, skip_reason)
    return None


def _failed_result(code: str, *, ingest=(), fsi=None, compute=None, hook_status="not_run") -> DailyResult:
    return DailyResult("failed", tuple(ingest), fsi, compute, error_code=_safe_error_code(code), hook_status=hook_status)


def run_daily(area: AreaConfig, run_date: date, conn, *, ingest_runner: Callable | None = None,
              compute_pipeline=_AUTO, fsi_runner: Callable | None = None) -> DailyResult:
    """Run ingest then FSI/compute; return success, partial, or failed without exposing exception text."""
    ingest_runner = ingest_runner or (lambda a, d, c: run_ingest(a, d, Writer(c)))
    fsi_runner = fsi_runner or (lambda a, d, c: run_fsi(a, d, FsiStore(c)))
    if compute_pipeline is _AUTO:
        compute_pipeline = _load_compute_pipeline()

    try:
        completed = _already_completed(conn, area, run_date, compute_pipeline is not None)
    except Exception as exc:
        log.error("completion check failed: %s", type(exc).__name__)
        return _failed_result("state_check_failed")
    if completed:
        return DailyResult(completed, already_complete=True, hook_status="already_complete")

    try:
        ingest_results = tuple(ingest_runner(area, run_date, conn))
    except Exception as exc:
        log.error("ingest stage failed: %s", type(exc).__name__)
        return _failed_result("ingest_failed")
    failed_ingest = next((item for item in ingest_results if item.status == "failed"), None)
    if failed_ingest:
        return _failed_result(failed_ingest.error_code, ingest=ingest_results)

    if compute_pipeline is not None:
        try:
            computed = run_mask_pick_hook(area, run_date, conn, compute_pipeline)
        except Exception as exc:
            log.error("compute stage failed: %s", type(exc).__name__)
            return _failed_result("compute_failed", ingest=ingest_results, hook_status="failed")
        if getattr(computed, "status", "failed") == "failed":
            failed_step = next(
                (getattr(computed, kind) for kind in _COMPUTE_KINDS
                 if getattr(computed, kind, None) is not None and getattr(computed, kind).status == "failed"),
                None,
            )
            return _failed_result(getattr(failed_step, "error_code", None) or "compute_failed",
                                  ingest=ingest_results, compute=computed, hook_status="ran")
        statuses = [getattr(computed, kind).status for kind in _COMPUTE_KINDS if getattr(computed, kind, None) is not None]
        status = "partial" if any(item.status == "partial" for item in ingest_results) or "partial" in statuses else "success"
        return DailyResult(status, ingest_results, compute=computed, hook_status="ran")

    try:
        fsi_result = fsi_runner(area, run_date, conn)
    except Exception as exc:
        log.error("FSI stage failed: %s", type(exc).__name__)
        _record_skipped(conn, "mask", area.area_id, run_date, "fsi_failed")
        _record_skipped(conn, "pick", area.area_id, run_date, "fsi_failed")
        return _failed_result("fsi_failed", ingest=ingest_results, hook_status="skipped")
    if fsi_result.status == "failed":
        run_mask_pick_hook(area, run_date, conn, None, skip_reason="fsi_failed")
        return _failed_result(fsi_result.error_code or "fsi_failed", ingest=ingest_results,
                              fsi=fsi_result, hook_status="skipped")
    run_mask_pick_hook(area, run_date, conn, None)
    status = "partial" if fsi_result.status == "partial" or any(item.status == "partial" for item in ingest_results) else "success"
    return DailyResult(status, ingest_results, fsi=fsi_result, hook_status="skipped_not_built")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backend.jobs.run_daily")
    parser.add_argument("--area", required=True)
    parser.add_argument("--date", default="today", help="area-local calendar date, or 'today'")
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(levelname)s %(name)s: %(message)s")
    try:
        area = load_area(args.area)
        run_date = parse_date(args.date, area.timezone)
    except (ConfigError, SystemExit):
        print("invalid area or date", file=sys.stderr)
        return 2

    dsn = os.environ.get("DATABASE_URL_INGEST")
    if not dsn:
        print("DATABASE_URL_INGEST is not set", file=sys.stderr)
        return 2
    try:
        import psycopg
        with psycopg.connect(dsn, autocommit=True) as conn:
            result = run_daily(area, run_date, conn)
    except Exception as exc:
        print(f"daily job failed ({type(exc).__name__})", file=sys.stderr)
        return 1

    print(f"area={area.area_id} run_date={run_date} status={result.status} already_complete={str(result.already_complete).lower()}")
    for item in result.ingest:
        print(f"  ingest {item.variable}: {item.status} error={_safe_error_code(item.error_code) if item.error_code else 'none'}")
    if result.compute is not None:
        for kind in _COMPUTE_KINDS:
            step = getattr(result.compute, kind, None)
            if step is not None:
                print(f"  {kind}: {step.status} error={_safe_error_code(getattr(step, 'error_code', None)) if getattr(step, 'error_code', None) else 'none'}")
    elif result.fsi is not None:
        print(f"  fsi: {result.fsi.status} error={_safe_error_code(result.fsi.error_code) if result.fsi.error_code else 'none'}")
        print("  mask/pick: skipped (not built)")
    if result.error_code:
        print(f"error={result.error_code}", file=sys.stderr)
    return 0 if result.status in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
