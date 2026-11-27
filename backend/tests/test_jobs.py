from datetime import date
from types import SimpleNamespace

from ingest.config import load_area

from jobs.run_daily import run_daily


def result(status, error_code=None):
    return SimpleNamespace(status=status, error_code=error_code)


def test_daily_runner_stops_before_compute_after_ingest_failure(monkeypatch):
    import jobs.run_daily as runner

    monkeypatch.setattr(runner, "_already_completed", lambda *args, **kwargs: False)
    calls = []

    def ingest(area, run_date, conn):
        return [result("success"), result("failed", "timeout")]

    def compute(*args, **kwargs):
        calls.append("compute")
        raise AssertionError("compute must not run after an ingest failure")

    daily = run_daily(load_area("th-chonburi-coast"), date(2026, 11, 27), object(),
                      ingest_runner=ingest, compute_pipeline=compute)
    assert daily.status == "failed"
    assert daily.error_code == "timeout"
    assert calls == []


def test_daily_runner_skips_all_steps_when_date_is_already_complete(monkeypatch):
    import jobs.run_daily as runner

    monkeypatch.setattr(runner, "_already_completed", lambda *args, **kwargs: "partial")
    calls = []

    def unexpected(*args, **kwargs):
        calls.append("called")
        raise AssertionError("a completed date must be read-only on rerun")

    daily = run_daily(load_area("th-chonburi-coast"), date(2026, 11, 27), object(),
                      ingest_runner=unexpected, compute_pipeline=unexpected)
    assert daily.status == "partial"
    assert daily.already_complete is True
    assert calls == []


def test_daily_runner_reports_failed_compute_and_keeps_its_error_code(monkeypatch):
    import jobs.run_daily as runner

    monkeypatch.setattr(runner, "_already_completed", lambda *args, **kwargs: False)

    def ingest(area, run_date, conn):
        return [result("success")]

    compute_result = SimpleNamespace(status="failed", mask=result("failed", "mask_failed"), fsi=None, pick=None)
    daily = run_daily(load_area("th-chonburi-coast"), date(2026, 11, 27), object(),
                      ingest_runner=ingest, compute_pipeline=lambda *args, **kwargs: compute_result)
    assert daily.status == "failed"
    assert daily.error_code == "mask_failed"


def test_default_runner_resolves_and_calls_the_merged_compute_pipeline(monkeypatch):
    import jobs.run_daily as runner

    monkeypatch.setattr(runner, "_already_completed", lambda *args, **kwargs: None)
    calls = []

    def ingest(area, run_date, conn):
        return [result("success")]

    def merged_pipeline(area, run_date, conn, boat_classes):
        calls.append((area.area_id, run_date, boat_classes))
        return SimpleNamespace(status="success", mask=result("success"), fsi=result("success"), pick=result("success"))

    monkeypatch.setattr(runner, "_load_compute_pipeline", lambda: merged_pipeline)
    daily = run_daily(load_area("th-chonburi-coast"), date(2026, 11, 27), object(), ingest_runner=ingest)
    assert daily.status == "success"
    assert daily.hook_status == "ran"
    assert calls == [("th-chonburi-coast", date(2026, 11, 27), ("small",))]


def test_compute_resolver_points_to_the_pipeline_merged_on_main():
    from compute.pipeline import run_compute
    from jobs.run_daily import _load_compute_pipeline

    assert _load_compute_pipeline() is run_compute


def test_cli_module_is_importable_from_repository_root():
    import os
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.pop("DATABASE_URL_INGEST", None)
    process = subprocess.run(
        [sys.executable, "-m", "backend.jobs.run_daily", "--area", "th-chonburi-coast", "--date", "2026-11-27"],
        cwd=project_root, env=env, capture_output=True, text=True, timeout=15,
    )
    assert process.returncode == 2
    assert "DATABASE_URL_INGEST is not set" in process.stderr
    assert "Traceback" not in process.stderr
