"""Mask -> FSI -> pick against a THROWAWAY PostGIS (PELAGO_TEST_ADMIN_URL; PELAGO_REQUIRE_DB=1 makes a missing one a failure).

The world (real 200-cell Chonburi grid, SYNTHETIC polygons and values), columns west to east at lon 100.725 .. 101.175:
  col 0   outside the waters (the western border is at lon 100.7435)
  col 1   inside, about 3.4 km from that border -> inside the 5 km buffer
  cols 2-7 sea that may be recommended
  cols 8-9 land (lon >= 101.10)
Every cell a guard must refuse also gets the BEST sea-surface temperature, so if a guard were removed it would be ranked first.
"""
import os

import psycopg
import pytest

from fsi.db import FsiStore
from fsi.pipeline import run_fsi
from ingest.config import ConfigError, load_area
from masks.db import MaskStore
from masks.pipeline import run_mask
from pick.db import PickStore
from pick.pipeline import run_pick
from compute.pipeline import run_compute
from tests.mask_helpers import RUN, cell_lon_lat, rect, seed_grid, sphere_km, write_layer
from tests.test_db_roundtrip import ADMIN, db, one  # noqa: F401  (db is a pytest fixture)

pytestmark = pytest.mark.skipif(not ADMIN and not os.environ.get("PELAGO_REQUIRE_DB"), reason="PELAGO_TEST_ADMIN_URL not set")
AREA = "th-chonburi-coast"


@pytest.fixture
def area():
    return load_area(AREA)


@pytest.fixture
def layers(tmp_path):
    d = tmp_path / "layers"
    f = d / AREA
    write_layer(f, "land.geojson", [rect(101.10, 11.5, 102.0, 14.0)])
    write_layer(f, "eez.geojson", [rect(100.7435, 12.0, 101.098, 12.8)])
    write_layer(f, "internal_waters.geojson", [rect(100.7435, 12.8, 101.098, 13.5)])
    return d


def col_row(area, cid):
    i = area.cell_ids().index(cid)
    return i % 10, i // 10


def classes(area):
    """cell ids by role, for the standard world"""
    ids = area.cell_ids()
    at = lambda pred: {c for c in ids if pred(*col_row(area, c))}      # noqa: E731
    return {"outside": at(lambda c, r: c == 0), "buffer": at(lambda c, r: c == 1), "land": at(lambda c, r: c in (8, 9)),
            "red": at(lambda c, r: c == 4 and r < 6), "no_wx": at(lambda c, r: c == 5 and r < 6),
            "no_sst": at(lambda c, r: c == 3 and 6 <= r < 12), "ok": at(lambda c, r: 2 <= c <= 7)}


def seed_world(db, area):
    k = classes(area)
    bad = k["outside"] | k["buffer"] | k["land"] | k["red"] | k["no_wx"]
    seed_grid(db, area,
              sst=lambda i, cid: 29.0 if cid in bad else 28.0 + 0.05 * ((i // 10) * 3 + (i % 10) * 7 % 10),
              no_sst=k["no_sst"], no_wx=k["no_wx"],
              wave=lambda i, cid: 1.8 if cid in k["red"] else 0.4)
    return k


def picks(db):
    return db.execute("""SELECT cell_id, pick_rank, fsi, confidence, legal_status FROM pelago.recommendations
                         ORDER BY pick_rank""").fetchall()


def test_no_recommended_spot_is_ever_in_a_forbidden_or_unknown_cell(db, area, layers):
    k = seed_world(db, area)
    r = run_compute(area, RUN, db, layers_dir=layers)
    assert (r.mask.status, r.fsi.status, r.pick.status) == ("success", "success", "success"), r
    ps = picks(db)
    ids = {p[0] for p in ps}
    assert 3 <= len(ps) <= 5
    # the cells that must be refused really were refused, each for its own cause
    m = {row[0]: row for row in db.execute("SELECT cell_id, is_water, eez_ok, eligible, exclusion_codes FROM pelago.cell_mask_daily")}
    assert all(m[c][1] is False and m[c][3] is False and "land" in m[c][4] for c in k["land"])
    assert all(m[c][1] is True and m[c][2] is False and "outside_eez" in m[c][4] for c in k["outside"] | k["buffer"])
    assert all("red_sea" in m[c][4] for c in k["red"]) and all("no_forecast" in m[c][4] for c in k["no_wx"])
    assert all(m[c][2] is True and m[c][3] is True for c in k["ok"] - k["red"] - k["no_wx"])
    # ... and none of them is a spot (the decoys have the best SST, so they would be ranked first without the guards)
    for name in ("land", "outside", "buffer", "red", "no_wx", "no_sst"):
        assert not ids & k[name], name
    assert ids <= k["ok"]
    # every spot is stored against an eligible mask row and a scored cell, in the database's own terms
    bad = db.execute("""SELECT count(*) FROM pelago.recommendations r
                        JOIN pelago.cell_mask_daily m USING (region_id, run_date, boat_class, cell_id)
                        JOIN pelago.fsi_daily f ON f.region_id = r.region_id AND f.run_date = r.run_date
                             AND f.model_version = r.model_version AND f.cell_id = r.cell_id
                        WHERE NOT (m.eligible AND m.is_water AND m.eez_ok IS TRUE AND f.fsi IS NOT NULL AND m.forecast_ok
                                   AND m.sea_state_level <> 'red')""").fetchone()[0]
    assert bad == 0
    assert all(p[4] == "incomplete" and p[3] != "high" for p in ps)        # trial labels and the confidence cap survive


def test_spots_are_at_least_10_km_apart_by_an_independent_calculation_and_by_postgis(db, area, layers):
    seed_world(db, area)
    run_compute(area, RUN, db, layers_dir=layers)
    ps = picks(db)
    pts = [cell_lon_lat(area, p[0]) for p in ps]
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            assert sphere_km(a[0], a[1], b[0], b[1]) >= 10.0
    rows = db.execute("""SELECT a.pick_rank, b.pick_rank,
                                extensions.ST_Distance(
                                  extensions.ST_SetSRID(extensions.ST_MakePoint(pelago.cell_centre_lon(a.cell_id)::float8,
                                                        pelago.cell_centre_lat(a.cell_id)::float8), 4326)::extensions.geography,
                                  extensions.ST_SetSRID(extensions.ST_MakePoint(pelago.cell_centre_lon(b.cell_id)::float8,
                                                        pelago.cell_centre_lat(b.cell_id)::float8), 4326)::extensions.geography,
                                  false) / 1000.0
                         FROM pelago.recommendations a JOIN pelago.recommendations b ON a.pick_rank < b.pick_rank""").fetchall()
    assert len(rows) == len(ps) * (len(ps) - 1) // 2
    assert min(r[2] for r in rows) >= 10.0
    assert [p[2] for p in ps] == sorted((p[2] for p in ps), reverse=True)           # rank 1 has the best FSI


def test_a_huge_spacing_leaves_one_honest_spot_and_a_partial_run(db, area, layers, make_area):
    big = make_area(mutate=lambda raw: raw["fsi"].update(min_spacing_km=300))
    seed_world(db, big)
    r = run_compute(big, RUN, db, layers_dir=layers)
    assert (r.pick.status, r.pick.error_code, r.pick.picks) == ("partial", "few_picks", {"small": 1})
    assert one(db, "SELECT count(*) FROM pelago.recommendations") == 1


def test_fewer_than_three_eligible_cells_are_stored_as_they_are_never_padded(db, area, layers):
    ids = area.cell_ids()
    keep = {ids[2], ids[7 + 190]}                         # col 2 row 0 and col 7 row 19: far apart
    seed_grid(db, area, no_wx=set(ids) - keep)
    r = run_compute(area, RUN, db, layers_dir=layers)
    assert (r.pick.status, r.pick.error_code, r.pick.picks) == ("partial", "few_picks", {"small": 2})
    assert {p[0] for p in picks(db)} == keep


def test_no_eligible_cell_means_no_spot(db, area, layers):
    seed_grid(db, area, no_wx=set(area.cell_ids()))
    r = run_compute(area, RUN, db, layers_dir=layers)
    assert (r.pick.status, r.pick.error_code, r.pick.picks) == ("partial", "no_picks", {"small": 0})
    assert one(db, "SELECT count(*) FROM pelago.recommendations") == 0


def test_a_cell_outside_the_area_box_is_never_picked_even_if_it_is_eligible_and_best(db, area, layers):
    from ingest.grid import cell_id
    seed_world(db, area)
    outside = cell_id(13.275, 100.925)                    # inside the synthetic waters, north of the area box (max lat 13.2)
    db.execute("""INSERT INTO pelago.grid_daily (region_id, run_date, cell_id, sst_c, sst_observed_at, sst_source, sst_grad_c_per_km,
                  chl_mg_m3, chl_observed_at, chl_source, chl_product, depth_m, depth_source, wave_window_max_m, wind_window_max_kmh,
                  wx_issued_at, wx_source) SELECT region_id, run_date, %s, sst_c, sst_observed_at, sst_source, sst_grad_c_per_km,
                  chl_mg_m3, chl_observed_at, chl_source, chl_product, depth_m, depth_source, wave_window_max_m, wind_window_max_kmh,
                  wx_issued_at, wx_source FROM pelago.grid_daily WHERE cell_id = %s""", (outside, area.cell_ids()[100]))          # copy a best-SST decoy row
    run_compute(area, RUN, db, layers_dir=layers)
    assert one(db, "SELECT eligible FROM pelago.cell_mask_daily WHERE cell_id = %s", outside) is True       # the mask allows it
    assert one(db, "SELECT fsi IS NOT NULL FROM pelago.fsi_daily WHERE cell_id = %s", outside) is True
    assert outside not in {p[0] for p in picks(db)} and len(picks(db)) >= 3


# ---- unknown means not recommended ------------------------------------------------------------------------------------
def test_eez_layer_not_loaded_means_unknown_and_no_spot(db, area, layers):
    (layers / AREA / "internal_waters.geojson").unlink()
    seed_world(db, area)
    r = run_compute(area, RUN, db, layers_dir=layers)
    assert (r.mask.status, r.mask.error_code, r.mask.layers_missing) == ("partial", "layer_not_loaded", ["eez"])
    assert one(db, "SELECT count(*) FROM pelago.cell_mask_daily WHERE eez_ok IS NOT NULL") == 0
    assert one(db, "SELECT count(*) FROM pelago.cell_mask_daily WHERE eligible") == 0
    assert one(db, "SELECT count(*) FROM pelago.cell_mask_daily WHERE 'eez_unknown' = ANY(exclusion_codes) AND is_water") > 100
    assert one(db, "SELECT count(*) FROM pelago.recommendations") == 0 and r.pick.error_code == "no_picks"


def test_land_layer_not_loaded_means_no_cell_is_known_to_be_water(db, area, layers):
    (layers / AREA / "land.geojson").unlink()
    seed_world(db, area)
    r = run_compute(area, RUN, db, layers_dir=layers)
    assert r.mask.status == "partial" and set(r.mask.layers_missing) == {"land", "eez"}
    assert one(db, "SELECT count(*) FROM pelago.cell_mask_daily WHERE is_water OR eligible") == 0
    assert one(db, "SELECT count(*) FROM pelago.cell_mask_daily WHERE 'land_unknown' = ANY(exclusion_codes)") == 200
    assert one(db, "SELECT count(*) FROM pelago.recommendations") == 0


def test_a_corrupt_layer_file_is_an_absent_layer_not_a_crash(db, area, layers):
    (layers / AREA / "eez.geojson").write_text('{"type":"FeatureCollection","features":[{"geometry":{"type":"Point"}}]}')
    seed_world(db, area)
    r = run_compute(area, RUN, db, layers_dir=layers)
    assert r.mask.status == "partial" and one(db, "SELECT count(*) FROM pelago.recommendations") == 0
    detail = db.execute("SELECT detail FROM pelago.job_runs WHERE job_kind = 'mask'").fetchone()[0]
    assert detail["layer_problems"] == {"eez": "bad_geometry"}


def test_the_withhold_policy_recommends_nothing_while_legal_layers_are_incomplete(db, layers, make_area):
    a = make_area(mutate=lambda raw: raw["legal"].update(incomplete_policy="withhold"))
    seed_world(db, a)
    r = run_compute(a, RUN, db, layers_dir=layers)
    assert one(db, "SELECT count(*) FROM pelago.cell_mask_daily WHERE eligible") == 0
    assert one(db, "SELECT bool_and(NOT legal_unknown_allowed) FROM pelago.cell_mask_daily") is True
    assert one(db, "SELECT count(*) FROM pelago.recommendations") == 0 and r.pick.error_code == "no_picks"


def test_a_layer_claimed_loaded_without_an_evaluator_or_a_bad_policy_stops_the_run(db, area, layers, make_area):
    seed_world(db, area)
    for mutate in (lambda raw: raw["legal"]["layers_loaded"].append("protected"),
                   lambda raw: raw["legal"].update(incomplete_policy="maybe"),
                   lambda raw: raw["legal"].update(eez_buffer_km=float("nan")),
                   lambda raw: raw["legal"].update(eez_buffer_km=0),
                   lambda raw: raw["legal"].update(eez_buffer_km=True),
                   lambda raw: raw["max_age_days"]["wave_wind_hours"].update(max=0)):
        with pytest.raises(ConfigError):
            run_mask(make_area(mutate=mutate), RUN, MaskStore(db), layers_dir=layers)
    assert one(db, "SELECT count(*) FROM pelago.cell_mask_daily") == 0 and one(db, "SELECT count(*) FROM pelago.job_runs") == 0
    with pytest.raises(ConfigError):
        run_mask(area, RUN, MaskStore(db), boat_classes=["small", "small"], layers_dir=layers)
    with pytest.raises(ConfigError):
        run_mask(area, RUN, MaskStore(db), boat_classes=["huge"], layers_dir=layers)


# ---- order, job_runs, idempotence, conflicts ---------------------------------------------------------------------------------
def test_every_step_has_a_job_run_and_rerunning_is_idempotent(db, area, layers):
    seed_world(db, area)
    run_compute(area, RUN, db, layers_dir=layers)
    first = picks(db)
    mask_rows = db.execute("SELECT * FROM pelago.cell_mask_daily ORDER BY cell_id").fetchall()
    r = run_compute(area, RUN, db, layers_dir=layers)
    assert r.status == "success"
    assert picks(db) == first                                              # same picks, no duplicates
    assert db.execute("SELECT * FROM pelago.cell_mask_daily ORDER BY cell_id").fetchall() == mask_rows
    assert one(db, "SELECT count(*) FROM pelago.cell_mask_daily") == 200
    runs = db.execute("""SELECT job_kind, attempt, status, error_code FROM pelago.job_runs WHERE job_kind IN ('mask','fsi','pick')
                         ORDER BY job_kind, attempt""").fetchall()
    assert runs == [("fsi", 1, "success", None), ("fsi", 2, "success", None), ("mask", 1, "success", None),
                    ("mask", 2, "success", None), ("pick", 1, "success", None), ("pick", 2, "success", None)]
    d = db.execute("SELECT detail FROM pelago.job_runs WHERE job_kind = 'mask' AND attempt = 1").fetchone()[0]
    assert set(d["layer_sha256"]) == {"land", "eez", "internal_waters"} and d["layers_missing"] == []
    assert "http" not in str(d) and one(db, "SELECT count(*) FROM pelago.job_runs WHERE run_id IN (SELECT run_id FROM pelago.recommendations)") == 1


def test_a_mask_change_that_would_orphan_a_pick_fails_and_leaves_everything_as_it_was(db, area, layers):
    seed_world(db, area)
    run_compute(area, RUN, db, layers_dir=layers)
    top = picks(db)[0][0]
    before = db.execute("SELECT * FROM pelago.cell_mask_daily ORDER BY cell_id").fetchall()
    db.execute("UPDATE pelago.grid_daily SET wave_window_max_m = 1.9 WHERE cell_id = %s", (top,))     # the best spot turns red
    r = run_mask(area, RUN, MaskStore(db), layers_dir=layers)                  # no clear_picks: must not delete the pick
    assert (r.status, r.error_code) == ("failed", "recommendation_conflict")
    assert db.execute("SELECT * FROM pelago.cell_mask_daily ORDER BY cell_id").fetchall() == before
    assert top in {p[0] for p in picks(db)}
    r = run_compute(area, RUN, db, layers_dir=layers)                          # the orchestrated run clears and re-picks
    assert r.status == "success" and top not in {p[0] for p in picks(db)}
    assert one(db, "SELECT sea_state_level FROM pelago.cell_mask_daily WHERE cell_id = %s", top) == "red"


def test_a_failed_mask_skips_the_later_steps_and_says_so(db, area, layers):
    from ingest.db import Writer
    Writer(db).ensure_region(area)                                             # a region but no ingested cells
    r = run_compute(area, RUN, db, layers_dir=layers)
    assert (r.mask.status, r.mask.error_code, r.fsi, r.pick, r.status) == ("failed", "no_ingest", None, None, "failed")
    rows = db.execute("SELECT job_kind, status, error_code, detail FROM pelago.job_runs ORDER BY job_kind").fetchall()
    assert [(k, s) for k, s, _, _ in rows] == [("fsi", "skipped"), ("mask", "failed"), ("pick", "skipped")]
    assert rows[0][3] == {"reason": "mask_failed"} and rows[1][2] == "no_ingest"
    assert one(db, "SELECT count(*) FROM pelago.cell_mask_daily") == 0


def test_no_region_row_fails_without_touching_anything(db, area, layers):
    r = run_compute(area, RUN, db, layers_dir=layers)
    assert (r.mask.status, r.mask.error_code, r.status) == ("failed", "no_region", "failed")
    assert one(db, "SELECT count(*) FROM pelago.job_runs") == 0                # job_runs has a foreign key to regions


def test_pick_alone_before_mask_or_fsi_stores_nothing(db, area, layers):
    seed_world(db, area)
    r = run_pick(area, RUN, PickStore(db))
    assert (r.status, r.error_code) == ("partial", "no_picks") and one(db, "SELECT count(*) FROM pelago.recommendations") == 0
    run_mask(area, RUN, MaskStore(db), layers_dir=layers)
    r = run_pick(area, RUN, PickStore(db))                                     # mask but no FSI yet
    assert r.error_code == "no_picks"
    run_fsi(area, RUN, FsiStore(db))
    assert run_pick(area, RUN, PickStore(db)).status == "success"


def test_the_database_itself_still_refuses_what_the_code_should_never_write(db, area, layers):
    k = seed_world(db, area)
    run_compute(area, RUN, db, layers_dir=layers)
    forbidden = sorted(k["land"])[0]
    db.execute("DELETE FROM pelago.recommendations")                            # free the rank slots
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("""INSERT INTO pelago.recommendations (region_id, run_date, boat_class, model_version, pick_rank, cell_id, fsi,
                      confidence, legal_status) VALUES (%s, %s, 'small', 'fsi-v1.0.0', 5, %s, 50, 'low', 'incomplete')""",
                   (area.area_id, RUN, forbidden))
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("""UPDATE pelago.cell_mask_daily SET eligible = true, is_water = true, eez_ok = NULL, forecast_ok = true,
                      sea_state_level = 'green', legal_unknown_allowed = true
                      WHERE cell_id = %s AND boat_class = 'small'""", (forbidden,))
