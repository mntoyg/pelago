-- Behaviour and mutation tests for backend/db/schema.sql. Runs in ONE transaction and rolls everything back.
-- Needs a database where schema.sql has already been applied (a clean PostgreSQL 15+ with PostGIS NOT pre-installed in
-- public, because the schema creates it in the `extensions` schema like Supabase). Example with a throwaway container:
--   docker run -d --name pelago-schema-test -e POSTGRES_PASSWORD=<random, local only> -p 127.0.0.1:55432:5432 postgis/postgis:16-3.7
--   createdb from template0, then: psql -v ON_ERROR_STOP=1 -f backend/db/schema.sql ; psql -f backend/db/tests/schema_test.sql
-- Every guard test (G*) must reject; every mutation test (M*) removes one guard and must then ACCEPT the forbidden write,
-- which proves the matching G test can go red. Last verified 2026-11-26 on PostgreSQL 16.16 + PostGIS 3.7.
\set ON_ERROR_STOP on
BEGIN;
CREATE TEMP TABLE res (n serial, label text, expected text, got text, ok boolean);

-- expect_fail: runs the SQL in a sub-block, always rolls it back; ok when PostgreSQL rejects it.
CREATE FUNCTION pg_temp.expect_fail(p_label text, p_sql text) RETURNS void LANGUAGE plpgsql AS $f$
BEGIN
  BEGIN
    EXECUTE p_sql;
    RAISE EXCEPTION '__ACCEPTED__';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM = '__ACCEPTED__' THEN
      INSERT INTO res (label, expected, got, ok) VALUES (p_label, 'rejected', 'ACCEPTED', false);
    ELSE
      INSERT INTO res (label, expected, got, ok) VALUES (p_label, 'rejected', 'rejected ' || SQLSTATE, true);
    END IF;
  END;
END $f$;

-- expect_accept: ok when the SQL is accepted (used for mutation checks and the known gap); always rolled back.
CREATE FUNCTION pg_temp.expect_accept(p_label text, p_sql text) RETURNS void LANGUAGE plpgsql AS $f$
BEGIN
  BEGIN
    EXECUTE p_sql;
    RAISE EXCEPTION '__ACCEPTED__';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM = '__ACCEPTED__' THEN
      INSERT INTO res (label, expected, got, ok) VALUES (p_label, 'accepted', 'accepted', true);
    ELSE
      INSERT INTO res (label, expected, got, ok) VALUES (p_label, 'accepted', 'REJECTED ' || SQLSTATE || ' ' || left(SQLERRM, 70), false);
    END IF;
  END;
END $f$;

-- ---------- 1. cell-id vectors (SQL side) ----------
INSERT INTO res (label, expected, got, ok)
SELECT 'cell_id ' || v.lat || ',' || v.lon, v.exp::text, pelago.cell_id(v.lat, v.lon)::text, pelago.cell_id(v.lat, v.lon) = v.exp
FROM (VALUES (12.306::numeric, 100.924::numeric, 14736818), (12.3, 100.7, 14736814), (12.2999, 100.7, 14729614),
             (0, 0, 12963600), (-0.0001, -0.0001, 12956399), (-90, -180, 0), (89.9999, 179.9999, 25919999)) AS v(lat, lon, exp);
INSERT INTO res (label, expected, got, ok)
SELECT 'centre of 14736818', '12.3250,100.9250', pelago.cell_centre_lat(14736818)::text || ',' || pelago.cell_centre_lon(14736818)::text,
       pelago.cell_centre_lat(14736818) = 12.3250 AND pelago.cell_centre_lon(14736818) = 100.9250;
SELECT pg_temp.expect_fail('cell_id(90,0) out of range', 'SELECT pelago.cell_id(90, 0)');
SELECT pg_temp.expect_fail('cell_id(0,180) out of range', 'SELECT pelago.cell_id(0, 180)');

-- ---------- 2. seed one valid chain ----------
INSERT INTO pelago.regions (region_id, country_code, timezone, min_lon, min_lat, max_lon, max_lat, config_sha256)
VALUES ('th-chonburi-coast', 'TH', 'Asia/Bangkok', 100.7, 12.2, 101.2, 13.2, repeat('a', 64));
INSERT INTO res (label, expected, got, ok)
SELECT 'regions.geom generated', 'POLYGON bbox', extensions.ST_AsText(geom), extensions.ST_AsText(geom) LIKE 'POLYGON((100.7 12.2,%'
FROM pelago.regions;

INSERT INTO pelago.grid_daily (region_id, run_date, cell_id, sst_c, sst_observed_at, sst_source, sst_grad_c_per_km,
  chl_mg_m3, chl_observed_at, chl_source, chl_product, depth_m, depth_source,
  wave_window_max_m, wind_window_max_kmh, wx_issued_at, wx_source)
VALUES ('th-chonburi-coast', '2026-11-30', 14736818, 29.1, '2026-11-29 09:00+00', 'erddap_mur', 0.12,
  0.8, '2026-11-29 05:00+00', 'erddap_viirs', 'daily', 25, 'etopo', 0.7, 17, '2026-11-29 18:00+00', 'open_meteo');
-- a second cell with NO sst (and no chl, depth)
INSERT INTO pelago.grid_daily (region_id, run_date, cell_id) VALUES ('th-chonburi-coast', '2026-11-30', 14736819);
INSERT INTO res (label, expected, got, ok)
SELECT 'grid_daily lat/lon generated from cell_id', '12.3250,100.9250', lat::text || ',' || lon::text, lat = 12.3250 AND lon = 100.9250
FROM pelago.grid_daily WHERE cell_id = 14736818;

INSERT INTO pelago.fsi_daily (region_id, run_date, model_version, cell_id, s_sst, s_front, s_chl, s_depth, s_moon, s_season,
  a_sst, a_front, a_chl, a_depth, a_moon, a_season, fsi, confidence, confidence_cap, confidence_reasons, config_sha256)
VALUES ('th-chonburi-coast', '2026-11-30', 'fsi-v1.0.0', 14736818, .9, .5, .8, .7, .6, .5, 1, 1, 1, 1, 1, 1, 77, 'medium',
        'no_verified_catch_logs', '{no_verified_catch_logs}', repeat('a', 64));
-- unscored row for the cell without SST (fsi NULL, confidence NULL)
INSERT INTO pelago.fsi_daily (region_id, run_date, model_version, cell_id, config_sha256)
VALUES ('th-chonburi-coast', '2026-11-30', 'fsi-v1.0.0', 14736819, repeat('a', 64));

-- eligible mask row (trial policy: legal layers unknown but allowed to label) and a non-eligible (land) row
INSERT INTO pelago.cell_mask_daily (region_id, run_date, boat_class, cell_id, is_water, eez_ok, legal_status, forecast_ok,
  sea_state_level, sea_reason_code, legal_unknown_allowed, eligible)
VALUES ('th-chonburi-coast', '2026-11-30', 'small', 14736818, true, true, 'incomplete', true, 'green', 'calm', true, true);
INSERT INTO pelago.cell_mask_daily (region_id, run_date, boat_class, cell_id, is_water, eez_ok, legal_status, forecast_ok,
  sea_state_level, sea_reason_code, legal_unknown_allowed, eligible, exclusion_codes)
VALUES ('th-chonburi-coast', '2026-11-30', 'small', 14736819, false, true, 'incomplete', true, 'green', 'calm', true, false, '{land}');

-- third cell: HAS an SST score but is land (non-eligible). Used by G12/M2 so that only the mask foreign key can refuse it.
INSERT INTO pelago.grid_daily (region_id, run_date, cell_id, sst_c, sst_observed_at, sst_source)
VALUES ('th-chonburi-coast', '2026-11-30', 14736820, 28.5, '2026-11-29 09:00+00', 'erddap_mur');
INSERT INTO pelago.fsi_daily (region_id, run_date, model_version, cell_id, s_sst, a_sst, fsi, confidence, confidence_cap, confidence_reasons, config_sha256)
VALUES ('th-chonburi-coast', '2026-11-30', 'fsi-v1.0.0', 14736820, .8, 1, 60, 'low', 'no_verified_catch_logs', '{chl_missing}', repeat('a', 64));
INSERT INTO pelago.cell_mask_daily (region_id, run_date, boat_class, cell_id, is_water, eez_ok, legal_status, forecast_ok,
  sea_state_level, sea_reason_code, legal_unknown_allowed, eligible, exclusion_codes)
VALUES ('th-chonburi-coast', '2026-11-30', 'small', 14736820, false, true, 'incomplete', true, 'green', 'calm', true, false, '{land}');

SELECT pg_temp.expect_accept('valid recommendation (eligible, scored cell) is accepted',
 $q$INSERT INTO pelago.recommendations (region_id, run_date, boat_class, model_version, pick_rank, cell_id, fsi, confidence, legal_status)
    VALUES ('th-chonburi-coast','2026-11-30','small','fsi-v1.0.0',1,14736818,77,'medium','incomplete')$q$);

-- ---------- 3. guards that must reject ----------
SELECT pg_temp.expect_fail('G1 fsi without s_sst (fsi=50, s_sst NULL)',
 $q$INSERT INTO pelago.fsi_daily (region_id,run_date,model_version,cell_id,fsi,confidence,config_sha256)
    VALUES ('th-chonburi-coast','2026-11-30','fsi-v9.9.9',14736819,50,'low',repeat('a',64))$q$);
SELECT pg_temp.expect_fail('G2 s_sst present but fsi NULL',
 $q$INSERT INTO pelago.fsi_daily (region_id,run_date,model_version,cell_id,s_sst,config_sha256)
    VALUES ('th-chonburi-coast','2026-11-30','fsi-v9.9.9',14736818,0.5,repeat('a',64))$q$);
SELECT pg_temp.expect_fail('G3 confidence high while cap set',
 $q$UPDATE pelago.fsi_daily SET confidence='high' WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G4 eligible cell with protected_ok = false',
 $q$UPDATE pelago.cell_mask_daily SET protected_ok=false WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G5 eligible cell with closure_ok = false',
 $q$UPDATE pelago.cell_mask_daily SET closure_ok=false WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G6 eligible cell with sea_state red',
 $q$UPDATE pelago.cell_mask_daily SET sea_state_level='red', sea_reason_code='wave_danger' WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G7 eligible cell with eez_ok NULL',
 $q$UPDATE pelago.cell_mask_daily SET eez_ok=NULL WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G8 eligible cell that is land',
 $q$UPDATE pelago.cell_mask_daily SET is_water=false WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G9 eligible cell without forecast',
 $q$UPDATE pelago.cell_mask_daily SET forecast_ok=false WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G10 incomplete legal layers while policy is withhold',
 $q$UPDATE pelago.cell_mask_daily SET legal_unknown_allowed=false WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G11 legal_status complete with unknown layers',
 $q$UPDATE pelago.cell_mask_daily SET legal_status='complete' WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G12 recommendation pointing at a non-eligible (land) cell that HAS a score',
 $q$INSERT INTO pelago.recommendations (region_id,run_date,boat_class,model_version,pick_rank,cell_id,fsi,confidence,legal_status)
    VALUES ('th-chonburi-coast','2026-11-30','small','fsi-v1.0.0',2,14736820,50,'low','incomplete')$q$);
SELECT pg_temp.expect_fail('G13 recommendation with no fsi_daily row for the model version',
 $q$INSERT INTO pelago.recommendations (region_id,run_date,boat_class,model_version,pick_rank,cell_id,fsi,confidence,legal_status)
    VALUES ('th-chonburi-coast','2026-11-30','small','fsi-v7.0.0',2,14736818,50,'low','incomplete')$q$);
SELECT pg_temp.expect_fail('G14 recommendation rank 6',
 $q$INSERT INTO pelago.recommendations (region_id,run_date,boat_class,model_version,pick_rank,cell_id,fsi,confidence,legal_status)
    VALUES ('th-chonburi-coast','2026-11-30','small','fsi-v1.0.0',6,14736818,77,'medium','incomplete')$q$);
SELECT pg_temp.expect_fail('G15 SST NaN',
 $q$UPDATE pelago.grid_daily SET sst_c='NaN'::real WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G16 chlorophyll Infinity',
 $q$UPDATE pelago.grid_daily SET chl_mg_m3='Infinity'::real WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G17 SST value without its date and source',
 $q$UPDATE pelago.grid_daily SET sst_observed_at=NULL WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G18 chlorophyll 0 stored with NULL timestamp (zero-for-missing)',
 $q$UPDATE pelago.grid_daily SET chl_mg_m3=0, chl_observed_at=NULL WHERE cell_id=14736818$q$);
SELECT pg_temp.expect_fail('G19 bad region id',
 $q$INSERT INTO pelago.regions (region_id,country_code,timezone,min_lon,min_lat,max_lon,max_lat,config_sha256)
    VALUES ('Bad Id','TH','Asia/Bangkok',100,12,101,13,repeat('a',64))$q$);
SELECT pg_temp.expect_fail('G20 inverted bbox',
 $q$INSERT INTO pelago.regions (region_id,country_code,timezone,min_lon,min_lat,max_lon,max_lat,config_sha256)
    VALUES ('th-x-y','TH','Asia/Bangkok',101,12,100,13,repeat('a',64))$q$);

-- ---------- 4. no SST, no spot: a recommendation must not point at an UNSCORED fsi_daily row (PM finding F-3, fixed) ----------
-- 14736819 has no SST; make its mask row eligible and recommend it with a made-up fsi. The schema must refuse.
SELECT pg_temp.expect_fail('G21 recommendation of a cell with NO SST (unscored fsi row, fsi copied as 50)',
 $q$UPDATE pelago.cell_mask_daily SET is_water=true, eligible=true, exclusion_codes='{}' WHERE cell_id=14736819;
    INSERT INTO pelago.recommendations (region_id,run_date,boat_class,model_version,pick_rank,cell_id,fsi,confidence,legal_status)
    VALUES ('th-chonburi-coast','2026-11-30','small','fsi-v1.0.0',3,14736819,50,'low','incomplete')$q$);

-- ---------- 5. mutation checks: remove each guard, the forbidden write must then be ACCEPTED (so the tests above can fail) ----------
-- Results are kept in variables and written to res AFTER the sub-blocks are rolled back (an INSERT made inside a rolled-back block is lost).
DO $m$
DECLARE c_elig text; c_fk text; c_fsi text; c_fk2 text; m1 text; m2 text; m3 text; m4 text;
BEGIN
  SELECT conname INTO c_elig FROM pg_constraint WHERE conrelid='pelago.cell_mask_daily'::regclass AND contype='c'
     AND pg_get_constraintdef(oid) LIKE '%NOT eligible%';
  SELECT conname INTO c_fk FROM pg_constraint WHERE conrelid='pelago.recommendations'::regclass AND contype='f'
     AND confrelid='pelago.cell_mask_daily'::regclass;
  SELECT conname INTO c_fsi FROM pg_constraint WHERE conrelid='pelago.fsi_daily'::regclass AND contype='c'
     AND pg_get_constraintdef(oid) LIKE '%fsi IS NULL) = (s_sst IS NULL%';

  SELECT conname INTO c_fk2 FROM pg_constraint WHERE conrelid='pelago.recommendations'::regclass AND contype='f'
     AND confrelid='pelago.fsi_daily'::regclass;

  BEGIN  -- M1: drop the eligible CHECK; a protected-zone cell can stay eligible (G4 would go red)
    EXECUTE format('ALTER TABLE pelago.cell_mask_daily DROP CONSTRAINT %I', c_elig);
    BEGIN
      UPDATE pelago.cell_mask_daily SET protected_ok=false WHERE cell_id=14736818;
      m1 := 'accepted';
    EXCEPTION WHEN OTHERS THEN m1 := 'REJECTED anyway ' || SQLSTATE;
    END;
    RAISE EXCEPTION '__ROLLBACK__';
  EXCEPTION WHEN OTHERS THEN NULL;
  END;

  BEGIN  -- M2: drop the FK to the eligible mask row; a non-eligible (land) cell can be recommended (G12 would go red)
    EXECUTE format('ALTER TABLE pelago.recommendations DROP CONSTRAINT %I', c_fk);
    BEGIN
      INSERT INTO pelago.recommendations (region_id,run_date,boat_class,model_version,pick_rank,cell_id,fsi,confidence,legal_status)
      VALUES ('th-chonburi-coast','2026-11-30','small','fsi-v1.0.0',2,14736820,50,'low','incomplete');
      m2 := 'accepted';
    EXCEPTION WHEN OTHERS THEN m2 := 'REJECTED anyway ' || SQLSTATE || ' ' || left(SQLERRM,60);
    END;
    RAISE EXCEPTION '__ROLLBACK__';
  EXCEPTION WHEN OTHERS THEN NULL;
  END;

  BEGIN  -- M3: drop the fsi/s_sst CHECK; a score without SST can be stored (G1 would go red)
    EXECUTE format('ALTER TABLE pelago.fsi_daily DROP CONSTRAINT %I', c_fsi);
    BEGIN
      INSERT INTO pelago.fsi_daily (region_id,run_date,model_version,cell_id,fsi,confidence,config_sha256)
      VALUES ('th-chonburi-coast','2026-11-30','fsi-v9.9.9',14736819,50,'low',repeat('a',64));
      m3 := 'accepted';
    EXCEPTION WHEN OTHERS THEN m3 := 'REJECTED anyway ' || SQLSTATE || ' ' || left(SQLERRM,60);
    END;
    RAISE EXCEPTION '__ROLLBACK__';
  EXCEPTION WHEN OTHERS THEN NULL;
  END;

  BEGIN  -- M4: drop the FK to the scored fsi row; a cell with no SST can be recommended (G21 would go red)
    EXECUTE format('ALTER TABLE pelago.recommendations DROP CONSTRAINT %I', c_fk2);
    UPDATE pelago.cell_mask_daily SET is_water=true, eligible=true, exclusion_codes='{}' WHERE cell_id=14736819;
    BEGIN
      INSERT INTO pelago.recommendations (region_id,run_date,boat_class,model_version,pick_rank,cell_id,fsi,confidence,legal_status)
      VALUES ('th-chonburi-coast','2026-11-30','small','fsi-v1.0.0',3,14736819,50,'low','incomplete');
      m4 := 'accepted';
    EXCEPTION WHEN OTHERS THEN m4 := 'REJECTED anyway ' || SQLSTATE || ' ' || left(SQLERRM,60);
    END;
    RAISE EXCEPTION '__ROLLBACK__';
  EXCEPTION WHEN OTHERS THEN NULL;
  END;

  INSERT INTO res (label, expected, got, ok) VALUES
   ('mutation setup: constraint names found', 'all 4', coalesce(c_elig,'?')||' / '||coalesce(c_fk,'?')||' / '||coalesce(c_fsi,'?')||' / '||coalesce(c_fk2,'?'), c_elig IS NOT NULL AND c_fk IS NOT NULL AND c_fsi IS NOT NULL AND c_fk2 IS NOT NULL),
   ('M1 without the eligible CHECK, a protected cell stays eligible (G4 goes red)', 'accepted', coalesce(m1,'?'), m1 = 'accepted'),
   ('M2 without the mask FK, a non-eligible cell can be recommended (G12 goes red)', 'accepted', coalesce(m2,'?'), m2 = 'accepted'),
   ('M3 without the fsi/SST CHECK, a score without SST is stored (G1 goes red)', 'accepted', coalesce(m3,'?'), m3 = 'accepted'),
   ('M4 without the scored-row FK, a cell with no SST can be recommended (G21 goes red)', 'accepted', coalesce(m4,'?'), m4 = 'accepted');
END $m$;

-- ---------- 6. views run ----------
INSERT INTO pelago.job_runs (job_kind, region_id, run_date, variable, source_id, fetcher_role, status, finished_at, data_date)
VALUES ('ingest', 'th-chonburi-coast', '2026-11-30', 'sst', 'erddap_mur', 'primary', 'success', now(), '2026-11-29');
INSERT INTO res (label, expected, got, ok)
SELECT 'v_ingest_last_success returns the ingest', '1 row', count(*)::text || ' row', count(*) = 1 FROM pelago.v_ingest_last_success;
INSERT INTO res (label, expected, got, ok)
SELECT 'v_ingest_last_attempt returns the ingest', '1 row', count(*)::text || ' row', count(*) = 1 FROM pelago.v_ingest_last_attempt;
SELECT pg_temp.expect_fail('job_runs: running with finished_at set',
 $q$INSERT INTO pelago.job_runs (job_kind,region_id,run_date,status,finished_at) VALUES ('mask','th-chonburi-coast','2026-11-30','running',now())$q$);

SELECT n, CASE WHEN ok THEN 'PASS' ELSE 'FAIL' END AS result, label, got FROM res ORDER BY n;
SELECT count(*) FILTER (WHERE ok) AS passed, count(*) FILTER (WHERE NOT ok) AS failed FROM res;
ROLLBACK;
