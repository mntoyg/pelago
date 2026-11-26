"""Round trip into a THROWAWAY PostgreSQL/PostGIS (never a shared or real database).

Set PELAGO_TEST_ADMIN_URL to a superuser URL of a disposable server (for example a postgis/postgis:16-3.7 container bound to
127.0.0.1). Each test run creates its own database TEMPLATE template0, applies backend/db/schema.sql, and drops it again.
Without the variable these tests are skipped; set PELAGO_REQUIRE_DB=1 to make a missing variable a failure instead.
The URL is never printed.
"""
import os
import re
import secrets
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from ingest import pipeline
from ingest.db import Writer
from ingest.fetchers.base import FetchError, Row
from ingest.grid import cell_id
from tests.helpers import ok_rows
from tests.test_pipeline import FakeSource, factory_for

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
ADMIN = os.environ.get("PELAGO_TEST_ADMIN_URL")
UTC = timezone.utc
RUN = date(2026, 11, 26)

pytestmark = pytest.mark.skipif(not ADMIN and not os.environ.get("PELAGO_REQUIRE_DB"), reason="PELAGO_TEST_ADMIN_URL not set")


@pytest.fixture
def db():
    assert ADMIN, "PELAGO_REQUIRE_DB is set but PELAGO_TEST_ADMIN_URL is not"
    name = "pelago_ingest_t_" + secrets.token_hex(4)
    with psycopg.connect(ADMIN, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
    try:
        info = psycopg.conninfo.conninfo_to_dict(ADMIN)
        info["dbname"] = name
        conn = psycopg.connect(**info, autocommit=True)
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        yield conn
        conn.close()
    finally:
        with psycopg.connect(ADMIN, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def one(conn, q, *a):
    return conn.execute(q, a).fetchone()[0]


def full_sources(area, **override):
    t = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
    cells = area.cell_ids()
    sst = [Row(c, 29.5 + i * 0.01, t, "erddap_mur_sst", None, {"grad_c_per_km": 0.02}) for i, c in enumerate(cells)]
    sst[0] = Row(cells[0], None, None, "erddap_mur_sst", None, {"grad_c_per_km": None})          # a cell with no SST
    chl = [Row(c, 0.6, t, "erddap_viirs_chl", "daily") for c in cells]
    chl[1] = Row(cells[1], None, None, "erddap_viirs_chl")
    depth = [Row(c, 12.5, None, "erddap_etopo_depth") for c in cells]
    depth[2] = Row(cells[2], None, None, "erddap_etopo_depth")                                  # land: no depth, NOT 0
    ww = [Row(c, 0.4, datetime(2026, 11, 26, 7, 0, tzinfo=UTC), "open_meteo_marine", None, {"wind_kmh": 18.0}) for c in cells]
    ww[3] = Row(cells[3], 0.4, ww[3].observed_at, "open_meteo_marine", None, {"wind_kmh": None})  # wind missing, wave present
    srcs = {"erddap_mur_sst": FakeSource("erddap_mur_sst", [sst]), "erddap_viirs_chl": FakeSource("erddap_viirs_chl", [chl]),
            "erddap_etopo_depth": FakeSource("erddap_etopo_depth", [depth]), "open_meteo_marine": FakeSource("open_meteo_marine", [ww])}
    srcs.update(override)
    return srcs


def test_round_trip_writes_the_grid_with_nulls_not_zeros(db, make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    c = area.cell_ids()
    out = pipeline.run_ingest(area, RUN, Writer(db), factory_for(full_sources(area)), sleep=lambda s: None)
    assert [r.status for r in out] == ["success"] * 4
    assert one(db, "SELECT count(*) FROM pelago.grid_daily") == 4
    assert one(db, "SELECT sst_c IS NULL AND sst_observed_at IS NULL AND sst_source IS NULL FROM pelago.grid_daily WHERE cell_id=%s", c[0])
    assert one(db, "SELECT count(*) FROM pelago.grid_daily WHERE sst_c = 0 OR chl_mg_m3 = 0 OR depth_m = 0 OR wave_window_max_m = 0") == 0
    assert one(db, "SELECT depth_m IS NULL FROM pelago.grid_daily WHERE cell_id=%s", c[2])
    assert one(db, "SELECT wind_window_max_kmh IS NULL AND wave_window_max_m IS NOT NULL FROM pelago.grid_daily WHERE cell_id=%s", c[3])
    assert one(db, "SELECT sst_observed_at FROM pelago.grid_daily WHERE cell_id=%s", c[1]) == datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
    assert one(db, "SELECT chl_product FROM pelago.grid_daily WHERE cell_id=%s", c[0]) == "daily"
    assert one(db, "SELECT config_sha256 FROM pelago.regions") == area.sha256 and one(db, "SELECT run_date FROM pelago.grid_daily LIMIT 1") == RUN


def test_python_cell_ids_equal_the_sql_function(db, make_area):
    area = make_area()                                              # all 200 Chonburi cells
    pipeline.run_ingest(area, RUN, Writer(db), factory_for({
        "erddap_mur_sst": FakeSource("a", [ok_rows(area, "sst", 29.0, source="erddap_mur_sst", extra={"grad_c_per_km": 0.1})]),
        "erddap_viirs_chl": FakeSource("b", [ok_rows(area, "chl", 0.5, source="erddap_viirs_chl")]),
        "erddap_etopo_depth": FakeSource("c", [ok_rows(area, "depth", 9.0, t=None, source="erddap_etopo_depth")]),
        "open_meteo_marine": FakeSource("d", [ok_rows(area, "wave_wind", 0.3, source="open_meteo_marine", extra={"wind_kmh": 9.0})])}),
        sleep=lambda s: None)
    assert one(db, "SELECT count(*) FROM pelago.grid_daily") == 200
    # grid_daily.lat/lon are GENERATED from the cell id by SQL; feeding them back through pelago.cell_id() must return the id
    assert one(db, "SELECT count(*) FROM pelago.grid_daily WHERE pelago.cell_id(lat, lon) <> cell_id") == 0
    for lat, lon in [(12.306, 100.924), (12.3, 100.7), (12.2999, 100.7), (0, 0), (-0.0001, -0.0001), (-90, -180), (89.9999, 179.9999)]:
        assert one(db, "SELECT pelago.cell_id(%s::numeric, %s::numeric)", lat, lon) == cell_id(lat, lon)


def test_job_runs_hold_only_codes_and_counts_and_reruns_get_a_new_attempt(db, make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    leak = RuntimeError("https://u:pw@host.example/?token=SECRETTOKEN")
    srcs = full_sources(area, erddap_mur_sst=FakeSource("a", [leak]))
    out = pipeline.run_ingest(area, RUN, Writer(db), factory_for(srcs), sleep=lambda s: None)
    assert out[0].status == "failed"
    dump = str(db.execute("SELECT to_jsonb(j) FROM pelago.job_runs j").fetchall())
    for needle in ("SECRETTOKEN", "pw@", "://", "host.example"):
        assert needle not in dump
    assert one(db, "SELECT error_code FROM pelago.job_runs WHERE variable='sst'") == "internal_error"
    pipeline.run_ingest(area, RUN, Writer(db), factory_for(full_sources(area)), sleep=lambda s: None)    # same date again
    assert one(db, "SELECT max(attempt) FROM pelago.job_runs WHERE variable='sst'") == 2
    assert one(db, "SELECT count(*) FROM pelago.grid_daily") == 4                                          # upsert, no duplicates
    assert one(db, "SELECT count(*) FROM pelago.job_runs WHERE status = 'running'") == 0


def test_carry_forward_reads_yesterday_from_the_database(db, make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    w = Writer(db)
    pipeline.run_ingest(area, date(2026, 11, 25), w, factory_for(full_sources(area)), sleep=lambda s: None)
    down = {"erddap_mur_sst": FakeSource("a", [FetchError("timeout")]), "erddap_viirs_chl": FakeSource("b", [FetchError("timeout")]),
            "erddap_viirs_n20_chl": FakeSource("b2", [FetchError("timeout")]), "erddap_etopo_depth": FakeSource("c", [FetchError("timeout")]),
            "open_meteo_marine": FakeSource("d", [FetchError("timeout")])}
    out = pipeline.run_ingest(area, RUN, w, factory_for(down), sleep=lambda s: None)
    assert [r.status for r in out] == ["partial", "partial", "partial", "failed"]
    # carried SST keeps its ORIGINAL observation time (24 Nov), so its age shows as 2 days at the new run date
    assert one(db, "SELECT sst_observed_at FROM pelago.grid_daily WHERE run_date=%s AND sst_c IS NOT NULL LIMIT 1", RUN) \
        == datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
    assert one(db, "SELECT count(*) FROM pelago.grid_daily WHERE run_date=%s AND wave_window_max_m IS NOT NULL", RUN) == 0
    assert one(db, "SELECT count(*) FROM pelago.job_runs WHERE run_date=%s AND status='partial' AND error_code='timeout'", RUN) == 3
    assert w.latest_before(area.area_id, RUN, "wave_wind") == []            # the writer refuses to hand out a wave/wind history


def test_the_database_itself_rejects_what_the_ingest_must_never_send(db, make_area):
    area = make_area([100.7, 12.2, 100.8, 12.3])
    w = Writer(db)
    w.ensure_region(area)
    run_id, _ = w.start_run(area.area_id, RUN, "sst", "erddap_mur_sst", "primary")
    t = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
    for bad in (float("nan"), float("inf"), 99.0):
        with pytest.raises(psycopg.errors.CheckViolation):
            w.write_rows(area.area_id, RUN, "sst", [Row(area.cell_ids()[0], bad, t, "erddap_mur_sst")], run_id)
    with pytest.raises(psycopg.errors.CheckViolation):          # a value without its observation time
        db.execute("INSERT INTO pelago.grid_daily (region_id, run_date, cell_id, sst_c) VALUES (%s,%s,%s,29)",
                   (area.area_id, RUN, area.cell_ids()[0]))
    w.finish_run(run_id, "failed", 0, None, "http://x?token=abc", {})      # the writer replaces a non-code by 'error'
    assert one(db, "SELECT error_code FROM pelago.job_runs WHERE run_id=%s", run_id) == "error"
    with pytest.raises(psycopg.errors.CheckViolation):          # and the database refuses a URL as an error_code anyway
        db.execute("UPDATE pelago.job_runs SET error_code = 'http://x'")
