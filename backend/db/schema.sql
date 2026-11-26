-- Pelago Asia: DRAFT PostgreSQL / PostGIS schema for the one-week backend slice.
--
-- STATUS: DRAFT. Not applied to any database. Not executed against PostgreSQL in the session that wrote it (no local
-- PostgreSQL or Docker daemon was available); see backend/README.md "Verification status". Treat every statement as
-- unverified until it has been run on a throwaway database (a local PostGIS container, or a Supabase branch).
--
-- Companion documents: backend/API_CONTRACT.md (section 9 maps every API field to a column here) and
-- ARCHITECTURE.md (A2 cross-cutting rules, A4 FSI, A5 filters). Spec references: S = function spec 2026-11-24.
--
-- Rules this schema encodes (S p.2 and p.7, ARCHITECTURE.md A2/A4/A5):
--   * Timestamps are timestamptz and are written in UTC. `run_date` is the CALENDAR DATE IN THE AREA'S OWN TIME ZONE.
--   * Coordinates are WGS84 with 4 decimals; the grid is 0.05 degree; one cell-id scheme, computed from coordinates
--     by pelago.cell_id() and nowhere else. Integer arithmetic only (see the function comment for why).
--   * A cell with no SST has NO score: fsi is NULL, never 0.
--   * "Unknown = do not recommend": legal flags are tri-state (true = checked and allowed, false = checked and
--     forbidden, NULL = layer not loaded). The recommendations table can only point at an eligible mask row.
--   * Nothing here stores personal data. User tables (C1, C9, C10) are out of scope this week.
--   * Everything country-specific lives in config files (backend/config/), not here. Tables keep identity and
--     measured/computed data only; `regions.config_sha256` ties results to the exact config that produced them.
--
-- Supabase notes (docs read 2026-11-26, linked in backend/README.md):
--   * PostGIS goes into a dedicated schema (`extensions`), never `public`.
--   * Tables live in the schema `pelago`, which is NOT added to the Data API's exposed schemas, and every table has
--     row level security enabled with no policies, so the anon/authenticated keys see nothing. The FastAPI service
--     connects server-side with its own role. UNVERIFIED: the exact current Supabase defaults for new schemas.

BEGIN;

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS pelago;
CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions;

-- ---------------------------------------------------------------------------------------------------------------
-- Cell-id scheme "pelago-cell-v1" (0.05 degree grid, S p.2: one scheme shared by all functions)
--
--   lat_e4 = round(lat * 10000)        -- integer count of 0.0001 degree; round half AWAY from zero
--   lon_e4 = round(lon * 10000)
--   lat_idx = floor((lat_e4 + 900000)  / 500)     0 .. 3599      (-90 <= lat < 90)
--   lon_idx = floor((lon_e4 + 1800000) / 500)     0 .. 7199      (-180 <= lon < 180)
--   cell_id = lat_idx * 7200 + lon_idx            0 .. 25 919 999 (fits integer)
--   centre  = ((lat_idx*500 - 900000 + 250) / 10000, (lon_idx*500 - 1800000 + 250) / 10000)
--
-- Why integers: (lat + 90) / 0.05 in binary floating point is wrong on cell edges. MEASURED 2026-11-26 in Python:
-- (12.3 + 90) / 0.05 = 2045.9999999999998, so a float floor() puts 12.3 in row 2045 instead of 2046; 170 of the
-- 3000 latitudes 0.00..29.99 (step 0.01) disagreed with the integer method. The Python side must use Decimal with
-- ROUND_HALF_UP (half away from zero, same as PostgreSQL round(numeric)) and must pass the vectors below.
--
-- Test vectors (computed with the integer method in Python on 2026-11-26; the SQL function has NOT been run):
--   lat 12.306,   lon 100.924  -> 14736818  centre (12.3250, 100.9250)
--   lat 12.3,     lon 100.7    -> 14736814  centre (12.3250, 100.7250)   (a point exactly on an edge)
--   lat 12.2999,  lon 100.7    -> 14729614  centre (12.2750, 100.7250)   (just below the edge: previous row)
--   lat 0,        lon 0        -> 12963600  centre (0.0250, 0.0250)
--   lat -0.0001,  lon -0.0001  -> 12956399  centre (-0.0250, -0.0250)
--   lat -90,      lon -180     -> 0
--   lat 89.9999,  lon 179.9999 -> 25919999
--   lat 90 or lon 180          -> error 22003 (out of range)
-- ---------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION pelago.cell_id(p_lat numeric, p_lon numeric)
RETURNS integer
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE
SET search_path = pg_catalog, pg_temp
AS $fn$
DECLARE
  la bigint;
  lo bigint;
BEGIN
  la := round(p_lat * 10000)::bigint;
  lo := round(p_lon * 10000)::bigint;
  IF la < -900000 OR la >= 900000 OR lo < -1800000 OR lo >= 1800000 THEN
    RAISE EXCEPTION 'coordinate out of range: lat=%, lon=%', p_lat, p_lon USING ERRCODE = '22003';
  END IF;
  -- both operands are non-negative here, so bigint division (truncation) equals floor
  RETURN (((la + 900000) / 500) * 7200 + ((lo + 1800000) / 500))::integer;
END
$fn$;

CREATE OR REPLACE FUNCTION pelago.cell_centre_lat(p_cell_id integer)
RETURNS numeric
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
AS $fn$ SELECT (((p_cell_id / 7200) * 500 - 900000 + 250)::numeric / 10000) $fn$;

CREATE OR REPLACE FUNCTION pelago.cell_centre_lon(p_cell_id integer)
RETURNS numeric
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
AS $fn$ SELECT (((p_cell_id % 7200) * 500 - 1800000 + 250)::numeric / 10000) $fn$;

-- ---------------------------------------------------------------------------------------------------------------
-- regions: one row per area. Identity and bounding box only; thresholds, weights, ports, legal-layer lists and the
-- licence route live in backend/config/areas/<region_id>.json (single source of truth).
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE pelago.regions (
  region_id           text PRIMARY KEY
                        CHECK (region_id ~ '^[a-z]{2}(-[a-z0-9]+)+$'),       -- e.g. th-chonburi-coast
  country_code        char(2) NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
  timezone            text NOT NULL CHECK (length(timezone) BETWEEN 1 AND 64), -- IANA name, validated by the app
  min_lon             numeric(8,4) NOT NULL CHECK (min_lon >= -180 AND min_lon < 180),
  min_lat             numeric(7,4) NOT NULL CHECK (min_lat >= -90  AND min_lat < 90),
  max_lon             numeric(8,4) NOT NULL CHECK (max_lon > -180 AND max_lon <= 180),
  max_lat             numeric(7,4) NOT NULL CHECK (max_lat > -90  AND max_lat <= 90),
  geom                extensions.geometry(Polygon, 4326) GENERATED ALWAYS AS
                        (extensions.ST_MakeEnvelope(min_lon::double precision, min_lat::double precision,
                                                    max_lon::double precision, max_lat::double precision, 4326)) STORED,
  -- Accuracy level (ARCHITECTURE.md A9). Changed only by the back-test / verification process, never by hand.
  verification_level  text NOT NULL DEFAULT 'trial' CHECK (verification_level IN ('trial', 'beta', 'confirmed')),
  verified_trips      integer NOT NULL DEFAULT 0 CHECK (verified_trips >= 0),
  config_sha256       text NOT NULL CHECK (config_sha256 ~ '^[0-9a-f]{64}$'),  -- hash of the area config file in use
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CHECK (min_lon < max_lon AND min_lat < max_lat)
);
CREATE INDEX regions_geom_gix ON pelago.regions USING gist (geom);
COMMENT ON TABLE pelago.regions IS 'One row per area. Config file is the source of truth; this row mirrors identity and bbox for keys and spatial queries.';

-- ---------------------------------------------------------------------------------------------------------------
-- job_runs: every ingest / mask / fsi / pick / backtest attempt, kept for freshness reporting and audit (S: C2, C14).
-- Never stores raw upstream error text (it can contain hostnames or query strings): only a short error_code.
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE pelago.job_runs (
  run_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_kind     text NOT NULL CHECK (job_kind IN ('ingest', 'mask', 'fsi', 'pick', 'backtest')),
  region_id    text NOT NULL REFERENCES pelago.regions (region_id),
  run_date     date NOT NULL,                       -- local calendar date of the area this run is FOR
  variable     text CHECK (variable IN ('sst', 'chl', 'depth', 'wave_wind')),   -- ingest only
  source_id    text CHECK (source_id ~ '^[a-z][a-z0-9_]{1,63}$'),               -- fetcher id from config, ingest only
  fetcher_role text CHECK (fetcher_role IN ('primary', 'fallback')),                    -- which fetcher of the chain ran
  attempt      smallint NOT NULL DEFAULT 1 CHECK (attempt BETWEEN 1 AND 10),    -- S C2: retry 3x, then fall back
  status       text NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed', 'skipped')),
  started_at   timestamptz NOT NULL DEFAULT now(),
  finished_at  timestamptz,
  data_date    date,                                -- newest observation date this run retrieved (ingest)
  rows_written integer CHECK (rows_written >= 0),
  error_code   text CHECK (error_code ~ '^[a-z0-9_]{1,64}$'),                   -- e.g. http_503, timeout, empty_grid
  detail       jsonb NOT NULL DEFAULT '{}'::jsonb,  -- counts only (cells total / with value); no URLs, no secrets
  CHECK (job_kind <> 'ingest' OR (variable IS NOT NULL AND source_id IS NOT NULL)),
  CHECK ((status = 'running') = (finished_at IS NULL)),
  CHECK (finished_at IS NULL OR finished_at >= started_at),
  CHECK (error_code IS NULL OR status IN ('failed', 'partial'))
);
-- one row per (region, kind, date, variable, source, attempt); a retry is a new attempt number.
CREATE UNIQUE INDEX job_runs_attempt_uq
  ON pelago.job_runs (region_id, job_kind, run_date, (COALESCE(variable, '')), (COALESCE(source_id, '')), attempt);
CREATE INDEX job_runs_latest_ix ON pelago.job_runs (region_id, job_kind, variable, started_at DESC);

-- ---------------------------------------------------------------------------------------------------------------
-- grid_daily: the ingested inputs per 0.05 degree cell per area-local date. Nullable by design: NULL means "no
-- observation", never zero. Each variable keeps its own observation timestamp and source so ages are per source.
-- NaN / Infinity are rejected by the range checks (PostgreSQL orders NaN above every number, so BETWEEN fails).
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE pelago.grid_daily (
  region_id          text NOT NULL REFERENCES pelago.regions (region_id),
  run_date           date NOT NULL,
  cell_id            integer NOT NULL CHECK (cell_id BETWEEN 0 AND 25919999),
  lat                numeric(7,4) GENERATED ALWAYS AS (pelago.cell_centre_lat(cell_id)) STORED,   -- cell centre
  lon                numeric(8,4) GENERATED ALWAYS AS (pelago.cell_centre_lon(cell_id)) STORED,
  -- sea-surface temperature, deg C (block mean over the cell; method is an ingest decision, see README)
  sst_c              real CHECK (sst_c BETWEEN -2 AND 40),
  sst_observed_at    timestamptz,
  sst_source         text,
  sst_grad_c_per_km  real CHECK (sst_grad_c_per_km BETWEEN 0 AND 100),     -- front strength input (S_front)
  -- chlorophyll-a, mg/m3
  chl_mg_m3          real CHECK (chl_mg_m3 >= 0 AND chl_mg_m3 < 1000),
  chl_observed_at    timestamptz,
  chl_source         text,
  chl_product        text CHECK (chl_product IN ('daily', '8day')),         -- cloud gaps: 8-day composite (G p.6)
  -- depth, metres, positive down
  depth_m            real CHECK (depth_m BETWEEN 0 AND 12000),
  depth_source       text,
  -- wave and wind: maximum over the sea window (default 04:00-14:00 local) of the area's local date
  wave_window_max_m  real CHECK (wave_window_max_m BETWEEN 0 AND 30),
  wind_window_max_kmh real CHECK (wind_window_max_kmh BETWEEN 0 AND 400),
  wx_issued_at       timestamptz,                                           -- forecast issue time, UTC
  wx_source          text,
  ingest_run_id      uuid REFERENCES pelago.job_runs (run_id),               -- last run that wrote this row
  ingested_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (region_id, run_date, cell_id),
  -- a value and its date and source travel together
  CHECK ((sst_c IS NULL) = (sst_observed_at IS NULL) AND (sst_c IS NULL) = (sst_source IS NULL)),
  CHECK ((chl_mg_m3 IS NULL) = (chl_observed_at IS NULL) AND (chl_mg_m3 IS NULL) = (chl_source IS NULL)
         AND (chl_mg_m3 IS NULL) = (chl_product IS NULL)),
  CHECK ((depth_m IS NULL) = (depth_source IS NULL)),
  CHECK ((wave_window_max_m IS NULL AND wind_window_max_kmh IS NULL)
         OR (wx_issued_at IS NOT NULL AND wx_source IS NOT NULL)),
  CHECK (sst_grad_c_per_km IS NULL OR sst_c IS NOT NULL)
);
COMMENT ON TABLE pelago.grid_daily IS 'Ingested inputs per cell and local date. NULL = no observation (never 0). lat/lon are the cell centre.';

-- ---------------------------------------------------------------------------------------------------------------
-- cell_mask_daily: the safety and legal decision per cell, per local date, per boat class (S C3, A5).
-- Tri-state legal flags: true = checked and allowed, false = checked and forbidden, NULL = layer not loaded (unknown).
-- This week only is_water and eez_ok can be non-NULL for the Chonburi area; the rest stay NULL on purpose.
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE pelago.cell_mask_daily (
  region_id            text NOT NULL REFERENCES pelago.regions (region_id),
  run_date             date NOT NULL,
  boat_class           text NOT NULL CHECK (boat_class ~ '^[a-z][a-z0-9_]{0,31}$'),
  cell_id              integer NOT NULL CHECK (cell_id BETWEEN 0 AND 25919999),
  is_water             boolean NOT NULL,                    -- land / coastline mask (Natural Earth, see licence note)
  eez_ok               boolean,                             -- inside the national EEZ, 5 km buffer from the border
  disputed_ok          boolean,                             -- not in a disputed area
  protected_ok         boolean,                             -- not in a protected / no-take zone
  closure_ok           boolean,                             -- not in a closed season today
  boat_zone_ok         boolean,                             -- a zone where this boat class may fish
  legal_status         text NOT NULL CHECK (legal_status IN ('complete', 'incomplete')),
  forecast_ok          boolean NOT NULL,                    -- wave AND wind present and not stale for this cell
  sea_state_level      text NOT NULL CHECK (sea_state_level IN ('green', 'yellow', 'red')),
  sea_reason_code      text NOT NULL CHECK (sea_reason_code IN
                         ('calm', 'wave_caution', 'wind_caution', 'wave_wind_caution',
                          'wave_danger', 'wind_danger', 'wave_wind_danger', 'forecast_missing', 'forecast_stale')),
  legal_unknown_allowed boolean NOT NULL,                   -- policy used for this row: 'label' (true) or 'withhold'
  eligible             boolean NOT NULL,                    -- may this cell be recommended at all
  exclusion_codes      text[] NOT NULL DEFAULT '{}',        -- why not (land, outside_eez, red_sea, no_forecast, ...)
  PRIMARY KEY (region_id, run_date, boat_class, cell_id),
  -- needed so recommendations can reference "this row, and it is eligible" (see recommendations FK)
  UNIQUE (region_id, run_date, boat_class, cell_id, eligible),
  -- 'complete' means every legal layer was actually checked
  CHECK (legal_status <> 'complete' OR (eez_ok IS NOT NULL AND disputed_ok IS NOT NULL AND protected_ok IS NOT NULL
                                        AND closure_ok IS NOT NULL AND boat_zone_ok IS NOT NULL)),
  -- hard backstops, independent of the application code: an eligible cell is water, inside the EEZ buffer, not known
  -- to be forbidden by any layer, not red, and has a forecast. Unknown legal layers need the explicit trial policy.
  CHECK (NOT eligible OR (is_water AND eez_ok IS TRUE
                          AND disputed_ok IS NOT FALSE AND protected_ok IS NOT FALSE
                          AND closure_ok IS NOT FALSE AND boat_zone_ok IS NOT FALSE
                          AND sea_state_level <> 'red' AND forecast_ok
                          AND (legal_status = 'complete' OR legal_unknown_allowed)))
);
CREATE INDEX cell_mask_eligible_ix ON pelago.cell_mask_daily (region_id, run_date, boat_class) WHERE eligible;
COMMENT ON TABLE pelago.cell_mask_daily IS 'Legal and sea-state decision per cell/date/boat class. NULL legal flag = unknown = not recommended unless the trial policy says otherwise.';

-- ---------------------------------------------------------------------------------------------------------------
-- fsi_daily: sub-scores and the index per cell (S C4). Scored for every water cell that has SST; a score is NOT a
-- recommendation (eligibility is in cell_mask_daily). Several model versions may coexist for the back-test.
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE pelago.fsi_daily (
  region_id           text NOT NULL REFERENCES pelago.regions (region_id),
  run_date            date NOT NULL,
  model_version       text NOT NULL CHECK (model_version ~ '^fsi-v[0-9]+\.[0-9]+\.[0-9]+$'),
  cell_id             integer NOT NULL CHECK (cell_id BETWEEN 0 AND 25919999),
  -- sub-scores 0..1; NULL = cannot be computed (no input). s_sst NULL means no SST and therefore no FSI.
  s_sst               real CHECK (s_sst BETWEEN 0 AND 1),
  s_front             real CHECK (s_front BETWEEN 0 AND 1),
  s_chl               real CHECK (s_chl BETWEEN 0 AND 1),
  s_depth             real CHECK (s_depth BETWEEN 0 AND 1),
  s_moon              real CHECK (s_moon BETWEEN 0 AND 1),
  s_season            real CHECK (s_season BETWEEN 0 AND 1),
  -- freshness a_i of each input, 0..1 (1 = today); weights are in the config file whose hash is stored below
  a_sst               real CHECK (a_sst BETWEEN 0 AND 1),
  a_front             real CHECK (a_front BETWEEN 0 AND 1),
  a_chl               real CHECK (a_chl BETWEEN 0 AND 1),
  a_depth             real CHECK (a_depth BETWEEN 0 AND 1),
  a_moon              real CHECK (a_moon BETWEEN 0 AND 1),
  a_season            real CHECK (a_season BETWEEN 0 AND 1),
  fsi                 real CHECK (fsi BETWEEN 0 AND 100),
  confidence          text CHECK (confidence IN ('high', 'medium', 'low')),
  confidence_cap      text CHECK (confidence_cap IN ('no_verified_catch_logs')),
  confidence_reasons  text[] NOT NULL DEFAULT '{}',
  config_sha256       text NOT NULL CHECK (config_sha256 ~ '^[0-9a-f]{64}$'),
  computed_at         timestamptz NOT NULL DEFAULT now(),
  run_id              uuid REFERENCES pelago.job_runs (run_id),
  PRIMARY KEY (region_id, run_date, model_version, cell_id),
  FOREIGN KEY (region_id, run_date, cell_id) REFERENCES pelago.grid_daily (region_id, run_date, cell_id),
  -- "a cell with no SST gets no score (null, not 0)" (S p.7): fsi exists exactly when s_sst exists
  CHECK ((fsi IS NULL) = (s_sst IS NULL)),
  CHECK ((fsi IS NULL) = (confidence IS NULL)),
  -- capped at medium while the area has no verified catch logs (S p.7)
  CHECK (confidence_cap IS NULL OR confidence IS DISTINCT FROM 'high')
);
COMMENT ON TABLE pelago.fsi_daily IS 'Sub-scores, freshness and FSI per cell. fsi NULL = no SST = no score. Not a recommendation.';

-- ---------------------------------------------------------------------------------------------------------------
-- recommendations (STUB): the 3-5 area-level picks per area/date/boat class that the API serves (S C5, G p.9).
-- Later phases add per-user messages (C5) and trip logs (C10) as separate tables; this table holds no user data.
-- The composite foreign keys make "a recommended spot in a forbidden cell" impossible to store.
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE pelago.recommendations (
  region_id       text NOT NULL,
  run_date        date NOT NULL,
  boat_class      text NOT NULL,
  model_version   text NOT NULL,
  pick_rank       smallint NOT NULL CHECK (pick_rank BETWEEN 1 AND 5),
  cell_id         integer NOT NULL,
  eligible        boolean NOT NULL DEFAULT true CHECK (eligible),   -- always true; part of the FK below
  fsi             real NOT NULL CHECK (fsi BETWEEN 0 AND 100),      -- copy of fsi_daily.fsi at pick time
  confidence      text NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
  legal_status    text NOT NULL CHECK (legal_status IN ('complete', 'incomplete')),
  run_id          uuid REFERENCES pelago.job_runs (run_id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (region_id, run_date, boat_class, model_version, pick_rank),
  UNIQUE (region_id, run_date, boat_class, model_version, cell_id),
  FOREIGN KEY (region_id, run_date, boat_class, cell_id, eligible)
    REFERENCES pelago.cell_mask_daily (region_id, run_date, boat_class, cell_id, eligible),
  FOREIGN KEY (region_id, run_date, model_version, cell_id)
    REFERENCES pelago.fsi_daily (region_id, run_date, model_version, cell_id)
);
COMMENT ON TABLE pelago.recommendations IS 'STUB. Area-level picks served by the API. FK to an eligible mask row and to a scored cell. No personal data.';

-- ---------------------------------------------------------------------------------------------------------------
-- Freshness views for GET /v1/areas/{area_id}/freshness (API_CONTRACT.md section 7). security_invoker needs
-- PostgreSQL 15+ (UNVERIFIED for the Supabase project the owner will create; drop the option if it errors).
-- ---------------------------------------------------------------------------------------------------------------
CREATE VIEW pelago.v_ingest_last_success WITH (security_invoker = true) AS
SELECT DISTINCT ON (region_id, variable)
       region_id, variable, source_id, fetcher_role, run_date, data_date, started_at, finished_at, attempt
FROM pelago.job_runs
WHERE job_kind = 'ingest' AND status IN ('success', 'partial')
ORDER BY region_id, variable, started_at DESC;

CREATE VIEW pelago.v_ingest_last_attempt WITH (security_invoker = true) AS
SELECT DISTINCT ON (region_id, variable)
       region_id, variable, source_id, fetcher_role, status, run_date, data_date, started_at, finished_at, attempt, error_code
FROM pelago.job_runs
WHERE job_kind = 'ingest'
ORDER BY region_id, variable, started_at DESC;

-- ---------------------------------------------------------------------------------------------------------------
-- Access control. RLS on every table, no policies: roles without BYPASSRLS read nothing. The API service connects with
-- a read-only role, the ingest job with a write role; both are created by the owner (passwords come from the host's
-- secret store, never from this file). Template, to adapt once the roles exist:
--   GRANT USAGE ON SCHEMA pelago, extensions TO pelago_api;
--   GRANT SELECT ON ALL TABLES IN SCHEMA pelago TO pelago_api;
--   CREATE POLICY api_read ON pelago.recommendations FOR SELECT TO pelago_api USING (true);   -- one per table
--   GRANT USAGE ON SCHEMA pelago, extensions TO pelago_ingest;
--   GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA pelago TO pelago_ingest;
--   CREATE POLICY ingest_all ON pelago.grid_daily FOR ALL TO pelago_ingest USING (true) WITH CHECK (true);
-- ---------------------------------------------------------------------------------------------------------------
ALTER TABLE pelago.regions          ENABLE ROW LEVEL SECURITY;
ALTER TABLE pelago.job_runs         ENABLE ROW LEVEL SECURITY;
ALTER TABLE pelago.grid_daily       ENABLE ROW LEVEL SECURITY;
ALTER TABLE pelago.cell_mask_daily  ENABLE ROW LEVEL SECURITY;
ALTER TABLE pelago.fsi_daily        ENABLE ROW LEVEL SECURITY;
ALTER TABLE pelago.recommendations  ENABLE ROW LEVEL SECURITY;

-- Supabase API roles must not reach this schema even by accident. Skipped silently on plain PostgreSQL.
DO $do$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON SCHEMA pelago FROM %I', r);
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA pelago FROM %I', r);
    END IF;
  END LOOP;
END
$do$;

COMMIT;
