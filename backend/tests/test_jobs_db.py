from datetime import date
from types import SimpleNamespace

import pytest

from ingest.config import load_area
from ingest.db import Writer
from ingest.pipeline import VariableResult
from tests.test_db_roundtrip import ADMIN, db  # noqa: F401 - pytest fixture
from jobs.run_daily import run_daily

pytestmark = pytest.mark.skipif(not ADMIN, reason="PELAGO_TEST_ADMIN_URL not set")
RUN = date(2026, 11, 27)


def record_job(conn, area, run_date, kind, status, *, variable=None, source_id=None, role=None,
               attempt=1, error_code=None, detail="{}"):
    conn.execute(
        """INSERT INTO pelago.job_runs (job_kind, region_id, run_date, variable, source_id, fetcher_role,
                  attempt, status, started_at, finished_at, error_code, detail)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now() - interval '1 second', now(), %s, %s::jsonb)""",
        (kind, area.area_id, run_date, variable, source_id, role, attempt, status, error_code, detail),
    )


def test_daily_runner_retries_after_failure_then_skips_a_completed_rerun(db, make_area):
    area = make_area()
    Writer(db).ensure_region(area)
    calls = {"ingest": 0, "compute": 0}

    def fail_first_ingest(a, run_date, conn):
        calls["ingest"] += 1
        ref = a.chain("sst")[0]
        record_job(conn, a, run_date, "ingest", "failed", variable="sst", source_id=ref.source_id,
                   role=ref.role, attempt=1, error_code="timeout")
        return [VariableResult("sst", "failed", ref.source_id, ref.role, 0, "timeout")]

    def successful_ingest(a, run_date, conn):
        calls["ingest"] += 1
        results = []
        for variable in ("sst", "chl", "depth", "wave_wind"):
            ref = a.chain(variable)[0]
            attempt = 2 if variable == "sst" else 1
            record_job(conn, a, run_date, "ingest", "success", variable=variable,
                       source_id=ref.source_id, role=ref.role, attempt=attempt)
            results.append(VariableResult(variable, "success", ref.source_id, ref.role, 1, None))
        return results

    def compute(a, run_date, conn, boat_classes):
        calls["compute"] += 1
        for kind in ("mask", "fsi", "pick"):
            record_job(conn, a, run_date, kind, "success")
        return SimpleNamespace(status="success", mask=SimpleNamespace(status="success", error_code=None),
                               fsi=SimpleNamespace(status="success", error_code=None),
                               pick=SimpleNamespace(status="success", error_code=None))

    first = run_daily(area, RUN, db, ingest_runner=fail_first_ingest,
                      compute_pipeline=lambda *args: pytest.fail("compute must stop after ingest failure"))
    assert first.status == "failed"
    assert first.error_code == "timeout"
    assert calls == {"ingest": 1, "compute": 0}
    assert db.execute("SELECT count(*) FROM pelago.recommendations").fetchone()[0] == 0

    recovered = run_daily(area, RUN, db, ingest_runner=successful_ingest, compute_pipeline=compute)
    assert recovered.status == "success"
    assert recovered.already_complete is False
    assert calls == {"ingest": 2, "compute": 1}
    tables = ("job_runs", "grid_daily", "fsi_daily", "cell_mask_daily", "recommendations")
    before = {table: db.execute(f"SELECT count(*) FROM pelago.{table}").fetchone()[0] for table in tables}

    repeated = run_daily(area, RUN, db, ingest_runner=successful_ingest, compute_pipeline=compute)
    after = {table: db.execute(f"SELECT count(*) FROM pelago.{table}").fetchone()[0] for table in tables}
    assert repeated.status == "success"
    assert repeated.already_complete is True
    assert before == after
    assert calls == {"ingest": 2, "compute": 1}


def test_mask_pick_hook_records_the_explicit_pre_merge_skip(db, make_area):
    from jobs.run_daily import run_mask_pick_hook

    area = make_area()
    Writer(db).ensure_region(area)
    result = run_mask_pick_hook(area, RUN, db, None)
    rows = db.execute(
        "SELECT COALESCE(variable, job_kind), status, detail->>'reason' FROM pelago.job_runs WHERE region_id=%s AND run_date=%s ORDER BY 1",
        (area.area_id, RUN),
    ).fetchall()
    assert result is None
    assert rows == [("mask", "skipped", "not_built"), ("pick", "skipped", "not_built")]


def test_daily_runner_uses_fsi_and_skip_hook_when_compute_is_not_built(db, make_area):
    area = make_area()
    Writer(db).ensure_region(area)

    def successful_ingest(a, run_date, conn):
        results = []
        for variable in ("sst", "chl", "depth", "wave_wind"):
            ref = a.chain(variable)[0]
            record_job(conn, a, run_date, "ingest", "success", variable=variable,
                       source_id=ref.source_id, role=ref.role)
            results.append(VariableResult(variable, "success", ref.source_id, ref.role, 1, None))
        return results

    def successful_fsi(a, run_date, conn):
        record_job(conn, a, run_date, "fsi", "success")
        return SimpleNamespace(status="success", error_code=None)

    completed = run_daily(area, RUN, db, ingest_runner=successful_ingest,
                          compute_pipeline=None, fsi_runner=successful_fsi)
    assert completed.status == "success"
    assert completed.hook_status == "skipped_not_built"
    before = db.execute(
        "SELECT COALESCE(variable, job_kind), status, detail->>'reason' FROM pelago.job_runs WHERE region_id=%s AND run_date=%s ORDER BY 1",
        (area.area_id, RUN),
    ).fetchall()
    assert before == [("chl", "success", None), ("depth", "success", None), ("fsi", "success", None),
                      ("mask", "skipped", "not_built"), ("pick", "skipped", "not_built"),
                      ("sst", "success", None), ("wave_wind", "success", None)]

    def unexpected(*args, **kwargs):
        pytest.fail("the pre-merge fallback must also be idempotent")

    repeated = run_daily(area, RUN, db, ingest_runner=unexpected, compute_pipeline=None, fsi_runner=unexpected)
    after = db.execute(
        "SELECT COALESCE(variable, job_kind), status, detail->>'reason' FROM pelago.job_runs WHERE region_id=%s AND run_date=%s ORDER BY 1",
        (area.area_id, RUN),
    ).fetchall()
    assert repeated.already_complete is True
    assert before == after
