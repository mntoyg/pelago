"""FSI job against a THROWAWAY PostgreSQL/PostGIS (same rules as test_db_roundtrip.py: PELAGO_TEST_ADMIN_URL of a disposable
server; PELAGO_REQUIRE_DB=1 turns a missing variable into a failure). The database URL is never printed."""
import os
from datetime import datetime, timezone

import psycopg
import pytest

from fsi.db import FsiStore
from fsi.pipeline import run_fsi
from ingest.config import load_area
from ingest.db import Writer
from tests.test_db_roundtrip import ADMIN, db, one  # noqa: F401  (db is a pytest fixture)

pytestmark = pytest.mark.skipif(not ADMIN and not os.environ.get("PELAGO_REQUIRE_DB"), reason="PELAGO_TEST_ADMIN_URL not set")
UTC = timezone.utc
from tests.fsi_helpers import RUN  # noqa: E402

SST_T = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)       # 16:00 local on 25 Nov: age 1 day on RUN
CHL_T = datetime(2026, 11, 25, 5, 0, tzinfo=UTC)


@pytest.fixture
def area():
    return load_area("th-chonburi-coast")


def seed(db, area, chl_everywhere=False, level="trial"):
    """200 cells: cell index i has SST except every 17th, chlorophyll on every 10th (or all), depth except every 13th."""
    Writer(db).ensure_region(area)
    db.execute("UPDATE pelago.regions SET verification_level = %s WHERE region_id = %s", (level, area.area_id))
    rows = []
    for i, cid in enumerate(area.cell_ids()):
        has_sst, has_chl, has_depth = i % 17 != 0, chl_everywhere or i % 10 == 0, i % 13 != 0
        rows.append((area.area_id, RUN, cid,
                     29 + (i % 7) * 0.2 if has_sst else None, SST_T if has_sst else None, "erddap_mur_sst" if has_sst else None,
                     0.001 * (i + 1) if has_sst else None,
                     0.8 if has_chl else None, CHL_T if has_chl else None, "erddap_viirs_chl" if has_chl else None,
                     "daily" if has_chl else None, 30.0 if has_depth else None, "erddap_etopo_depth" if has_depth else None))
    with db.cursor() as cur:
        cur.executemany("""INSERT INTO pelago.grid_daily (region_id, run_date, cell_id, sst_c, sst_observed_at, sst_source,
                           sst_grad_c_per_km, chl_mg_m3, chl_observed_at, chl_source, chl_product, depth_m, depth_source)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", rows)
    return area.cell_ids()


def run(db, area):
    return run_fsi(area, RUN, FsiStore(db))


def test_run_writes_scores_nulls_and_the_cap(db, area):
    cells = seed(db, area)
    r = run(db, area)
    assert (r.status, r.error_code, r.cells_total) == ("success", None, 200)
    assert one(db, "SELECT count(*) FROM pelago.fsi_daily") == 200
    no_sst = cells[0]                                              # i = 0: no SST, no depth, has chlorophyll
    assert db.execute("""SELECT fsi, s_sst, s_chl, a_chl, confidence, confidence_cap, confidence_reasons
                         FROM pelago.fsi_daily WHERE cell_id = %s""", (no_sst,)).fetchone() == (None, None, None, None, None, None, ["sst_missing"])
    assert one(db, "SELECT count(*) FROM pelago.fsi_daily WHERE fsi = 0 OR s_sst = 0 OR s_chl = 0 OR s_front = 0") == 0
    assert one(db, "SELECT count(*) FROM pelago.fsi_daily WHERE fsi IS NULL") == len([i for i in range(200) if i % 17 == 0])
    assert one(db, "SELECT count(*) FROM pelago.fsi_daily WHERE fsi IS NOT NULL AND confidence_cap IS DISTINCT FROM 'no_verified_catch_logs'") == 0
    assert one(db, "SELECT count(*) FROM pelago.fsi_daily WHERE confidence = 'high'") == 0
    assert one(db, "SELECT DISTINCT config_sha256 FROM pelago.fsi_daily") == area.sha256
    # chlorophyll on every 10th cell only: the cells with all four inputs are medium, the rest low (chl_missing)
    assert one(db, "SELECT count(*) FROM pelago.fsi_daily WHERE confidence = 'low' AND 'chl_missing' = ANY(confidence_reasons)") > 100
    assert db.execute("SELECT status, error_code, rows_written FROM pelago.job_runs WHERE job_kind = 'fsi'").fetchall() == [("success", None, 200)]


def test_sub_scores_of_a_cell_without_depth_say_so(db, area):
    cells = seed(db, area)
    cid = cells[13]                                                # i = 13: SST yes, depth NULL (land proxy)
    row = db.execute("SELECT fsi, s_depth, a_depth, s_front, confidence, confidence_reasons FROM pelago.fsi_daily WHERE cell_id = %s",
                     (cid,)).fetchone() if run(db, area) else None
    assert row[0] is not None and row[1] is None and row[2] is None and row[3] is None      # scored, depth and front missing
    assert row[4] == "low" and "depth_missing" in row[5] and "front_missing" in row[5]


def test_rerun_is_idempotent_and_counts_attempts(db, area):
    seed(db, area)
    run(db, area)
    first = db.execute("SELECT cell_id, fsi, confidence FROM pelago.fsi_daily ORDER BY cell_id").fetchall()
    assert run(db, area).status == "success"
    assert db.execute("SELECT cell_id, fsi, confidence FROM pelago.fsi_daily ORDER BY cell_id").fetchall() == first
    assert db.execute("SELECT attempt, status FROM pelago.job_runs WHERE job_kind = 'fsi' ORDER BY attempt").fetchall() == [(1, "success"), (2, "success")]


def test_a_verified_area_can_reach_high_when_every_input_is_present(db, area):
    seed(db, area, chl_everywhere=True, level="beta")
    run(db, area)
    assert one(db, "SELECT count(*) FROM pelago.fsi_daily WHERE confidence = 'high'") > 100
    assert one(db, "SELECT count(*) FROM pelago.fsi_daily WHERE confidence = 'high' AND confidence_cap IS NOT NULL") == 0
    seed_trial = one(db, "SELECT count(*) FROM pelago.fsi_daily WHERE fsi IS NOT NULL")
    assert seed_trial > 150


def test_no_region_and_no_ingest_fail_without_writing_scores(db, area):
    r = run(db, area)
    assert (r.status, r.error_code) == ("failed", "no_region")
    Writer(db).ensure_region(area)
    r = run(db, area)
    assert (r.status, r.error_code) == ("failed", "no_ingest")
    assert one(db, "SELECT count(*) FROM pelago.fsi_daily") == 0
    # without a regions row there is nowhere to record the first failure (job_runs has a foreign key to regions)
    assert db.execute("SELECT status, error_code FROM pelago.job_runs ORDER BY attempt").fetchall() == [("failed", "no_ingest")]


# ---- recommendations ---------------------------------------------------------------------------------------------------
def pick(db, area, cell_id):
    """Store one pick on cell_id (needs an eligible mask row and a scored fsi_daily row)."""
    db.execute("""INSERT INTO pelago.cell_mask_daily (region_id, run_date, boat_class, cell_id, is_water, eez_ok, legal_status,
                  forecast_ok, sea_state_level, sea_reason_code, legal_unknown_allowed, eligible)
                  VALUES (%s, %s, 'small', %s, true, true, 'incomplete', true, 'green', 'calm', true, true)""", (area.area_id, RUN, cell_id))
    db.execute("""INSERT INTO pelago.recommendations (region_id, run_date, boat_class, model_version, pick_rank, cell_id, fsi,
                  confidence, legal_status) SELECT region_id, run_date, 'small', model_version, 1, cell_id, fsi, confidence, 'incomplete'
                  FROM pelago.fsi_daily WHERE region_id = %s AND run_date = %s AND cell_id = %s""", (area.area_id, RUN, cell_id))


def test_postgres_itself_blocks_unscoring_a_picked_cell(db, area):
    """MEASURED question from the PM: does the `scored` foreign key really stop it? Raw SQL, no application guard."""
    cells = seed(db, area)
    run(db, area)
    target = cells[10]                                              # i = 10: SST, chlorophyll, depth: scored
    pick(db, area, target)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("""UPDATE pelago.fsi_daily SET fsi = NULL, s_sst = NULL, confidence = NULL, confidence_cap = NULL
                      WHERE cell_id = %s""", (target,))
    assert one(db, "SELECT fsi IS NOT NULL FROM pelago.fsi_daily WHERE cell_id = %s", target)


def test_losing_the_sst_of_a_picked_cell_fails_the_run_and_keeps_everything(db, area):
    cells = seed(db, area)
    run(db, area)
    target = cells[10]
    pick(db, area, target)
    before = db.execute("SELECT cell_id, fsi, computed_at FROM pelago.fsi_daily ORDER BY cell_id").fetchall()
    db.execute("UPDATE pelago.grid_daily SET sst_c = NULL, sst_observed_at = NULL, sst_source = NULL, sst_grad_c_per_km = NULL WHERE cell_id = %s", (target,))
    r = run(db, area)
    assert (r.status, r.error_code, r.blocked_by) == ("failed", "recommendation_conflict", "precheck")
    assert db.execute("SELECT cell_id, fsi, computed_at FROM pelago.fsi_daily ORDER BY cell_id").fetchall() == before
    assert one(db, "SELECT count(*) FROM pelago.recommendations") == 1
    assert db.execute("SELECT status, error_code, detail->>'reason' FROM pelago.job_runs WHERE job_kind = 'fsi' ORDER BY attempt DESC LIMIT 1").fetchone() \
        == ("failed", "recommendation_conflict", "unscored")


def test_the_database_backstop_maps_to_the_same_error_when_the_precheck_is_bypassed(db, area, monkeypatch):
    cells = seed(db, area)
    run(db, area)
    target = cells[10]
    pick(db, area, target)
    db.execute("UPDATE pelago.grid_daily SET sst_c = NULL, sst_observed_at = NULL, sst_source = NULL, sst_grad_c_per_km = NULL WHERE cell_id = %s", (target,))
    monkeypatch.setattr(FsiStore, "check_recommendations", lambda *a, **k: None)
    r = run(db, area)
    assert (r.status, r.error_code, r.blocked_by) == ("failed", "recommendation_conflict", "db")
    assert one(db, "SELECT fsi IS NOT NULL FROM pelago.fsi_daily WHERE cell_id = %s", target)


def test_a_changed_score_under_a_stored_pick_is_also_a_conflict(db, area):
    cells = seed(db, area)
    run(db, area)
    target = cells[10]
    pick(db, area, target)
    db.execute("UPDATE pelago.grid_daily SET sst_c = 24.0 WHERE cell_id = %s", (target,))      # the score falls a lot
    r = run(db, area)
    assert (r.error_code, r.blocked_by) == ("recommendation_conflict", "precheck")
    assert db.execute("SELECT detail->>'reason' FROM pelago.job_runs WHERE job_kind = 'fsi' ORDER BY attempt DESC LIMIT 1").fetchone()[0] == "changed"


# ---- command line ------------------------------------------------------------------------------------------------------
def test_cli_prints_counts_only(db, area, monkeypatch, capsys):
    seed(db, area)
    from fsi import run as cli
    info = psycopg.conninfo.conninfo_to_dict(ADMIN)
    info["dbname"] = db.info.dbname
    dsn = psycopg.conninfo.make_conninfo(**info)
    monkeypatch.setenv("DATABASE_URL_INGEST", dsn)
    assert cli.main(["--area", "th-chonburi-coast", "--date", "2026-11-26"]) == 0
    out = capsys.readouterr()
    assert "status=success" in out.out and "cells=200" in out.out
    assert dsn not in out.out + out.err and info["password"] not in out.out + out.err
    monkeypatch.delenv("DATABASE_URL_INGEST")
    assert cli.main(["--area", "th-chonburi-coast", "--date", "2026-11-26"]) == 2
