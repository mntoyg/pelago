# backend/: Pelago Asia API and daily ingest (DESIGN, nothing built yet)

**Status: DRAFT design, written 2026-11-26.** This folder currently holds only documents. No service, no database,
no deployment exists. It is the proposal for `TASK.md` section 4.1 (one-week slice); the owner has not approved it.

| File | What it is |
| --- | --- |
| [`API_CONTRACT.md`](API_CONTRACT.md) | the `/v1` HTTP contract: endpoints, fields (type, unit, null), errors, caching, field-to-column table, risks |
| [`db/schema.sql`](db/schema.sql) | DRAFT PostgreSQL/PostGIS schema (not applied, not executed) |
| `README.md` (this file) | proposed layout, configuration rules, ingest design notes, decisions needed |
| [`.gitignore`](.gitignore) | backend-only ignores (the repository root has no `.env` entry) |

Read first: [`../AGENTS.md`](../AGENTS.md), [`../ARCHITECTURE.md`](../ARCHITECTURE.md) (Part A is the target; cited here
as A2, A5, A7, ...), [`../TASK.md`](../TASK.md).

## 1. Scope for the week

One area (proposed: the Chonburi coast), one boat class set, FSI v1 computed on the server, daily ingest of SST,
chlorophyll, depth and wave/wind, a land mask and an EEZ mask with a 5 km buffer, "no data = no recommendation",
a freshness endpoint. Everything else in Part A is **not built** and the API says so through `caveats`.

## 2. Proposed folder layout

```
backend/
  README.md  API_CONTRACT.md  .gitignore
  db/
    schema.sql                  the draft schema (later: numbered migrations, see below)
  config/
    app.example.json            non-secret service settings (CORS origins, log level, cache ages)
    areas/
      th-chonburi-coast.json    ONE FILE PER AREA: bbox, time zone, boat classes, weights, thresholds, sources
    i18n/                       message and label keys if the API ever needs text (UI text stays in the front end)
  pyproject.toml                pinned dependencies (fastapi, pydantic, uvicorn, psycopg, numpy, xarray, ...)
  app/                          the FastAPI service (read-only)
    main.py                     app factory, middleware (request id, security headers, CORS from config), error handlers
    settings.py                 reads environment variables; refuses to start if a required one is missing
    config_loader.py            loads and validates config/areas/*.json (pydantic), computes config_sha256
    api/
      areas.py                  GET /v1/areas, /v1/areas/{id}
      spots.py                  GET /v1/areas/{id}/spots
      freshness.py              GET /v1/areas/{id}/freshness, GET /v1/health
      errors.py                 RFC 9457 problem details, error codes from API_CONTRACT.md section 5
    schemas.py                  pydantic response models, 1:1 with API_CONTRACT.md (the contract tests compare)
    db.py                       connection pool, read-only queries (parameterised only)
    domain/
      grid.py                   cell_id(lat, lon) with Decimal integer maths; must equal pelago.cell_id() (test vectors)
      fsi.py                    sub-scores, freshness weights, FSI v1, confidence rule (API_CONTRACT.md 4.6)
      seastate.py               green / yellow / red from boat-class thresholds and the sea-window maxima
      legal.py                  mask evaluation, tri-state flags, trial policy
      picks.py                  3-5 best eligible cells, spacing rule
      moon.py                   moon phase from the date
  ingest/                       the daily job (separate process, write role)
    run.py                      entry point: python -m ingest.run --area th-chonburi-coast --date today
    pipeline.py                 order: fetch sources -> mask -> fsi -> pick; writes job_runs at every step
    fetchers/
      base.py                   Fetcher interface: fetch(area, date) -> GridLayer | raises FetchError(code)
      registry.py               maps source_id in config to a class; enforces licence_route (see section 3.3)
      erddap_mur_sst.py         jplMURSST41
      erddap_viirs_chl.py       nesdisVHNchlaDaily
      erddap_etopo_depth.py     ETOPO_2022_v1_15s
      open_meteo_marine.py      route A only; sea-window maxima of wave and wind
    masks/
      land.py  eez.py           polygon masks from files under config/layers/ (Natural Earth, Marine Regions)
    backtest/                   later in the week: FSI over past dates, hit-rate method of G p.12
  tests/
    contract/                   one test per rule in API_CONTRACT.md sections 4.4 and 12
    unit/                       grid vectors, fsi, seastate, picks, legal
    db/                         schema checks on a throwaway database
    fixtures/                   small synthetic grids (no secrets, no real upstream dumps)
```

Rules for the layout: the API process holds a **read-only** database role and cannot write; the ingest job holds the
write role and exposes no HTTP port. They share `domain/` code through an importable package, not through HTTP.

### Migrations

`db/schema.sql` is a single draft. Once it passes on a real PostGIS it becomes `db/migrations/0001_init.sql` and every
later change is a new numbered file (Supabase CLI or plain SQL runner; owner's choice). Never edit an applied file.

## 3. Configuration

### 3.1 The rule

**Everything that differs by country or area lives in a config file, never in code** (G p.8, ARCHITECTURE.md A2): language
keys, time zone, units, bbox, boat-class thresholds, FSI weights and targets, ports, the legal-layer list, the licence
route, the fetcher chain per variable, maximum data ages. Adding a country is adding a file plus fetchers, not
editing `app/domain/`. A test greps `app/` and `ingest/` for the demo bbox, `Asia/Bangkok` and any weight literal and
fails if it finds one outside `config/`.

Config files are validated at startup (pydantic, unknown keys rejected, ranges checked). An invalid file stops the
service. The SHA-256 of each file is stored with every result, so a number can always be traced to the exact weights
that produced it.

### 3.2 Area config (starting values; every number is untuned, ARCHITECTURE.md A2)

```json
{
  "area_id": "th-chonburi-coast",
  "name": "Chonburi coast",
  "names": { "th": "ชายฝั่งชลบุรี" },
  "country_code": "TH",
  "timezone": "Asia/Bangkok",
  "bbox": [100.7, 12.2, 101.2, 13.2],
  "licence_route": "A",
  "sea_window_local": ["04:00", "14:00"],
  "boat_classes": {
    "small":  { "label_key": "boat.small",  "length_m_min": 0,  "length_m_max": 10,   "max_range_km": 30,
                "wave_yellow_m": 1.0, "wave_red_m": 1.5, "wind_yellow_kmh": 20, "wind_red_kmh": 30 },
    "medium": { "label_key": "boat.medium", "length_m_min": 10, "length_m_max": 18,   "max_range_km": null,
                "wave_yellow_m": 1.5, "wave_red_m": 2.5, "wind_yellow_kmh": 30, "wind_red_kmh": 40 }
  },
  "fsi": {
    "model_version": "fsi-v1.0.0",
    "weights": { "sst": 0.20, "front": 0.20, "chl": 0.25, "depth": 0.15, "moon": 0.10, "season": 0.10 },
    "targets": { "sst_c": 29, "sst_sigma_c": 2.5, "log10_chl": 0, "log10_chl_sigma": 0.5, "bloom_mg_m3": 10 },
    "freshness": { "grace_days": 1, "decay_days": 3 },
    "min_spacing_km": 5
  },
  "max_age_days": { "sst": { "fresh": 2, "max": 5 }, "chl": { "fresh": 3, "max": 10 },
                    "wave_wind_hours": { "fresh": 24, "max": 48 } },
  "legal": { "layers_required": ["land", "eez_buffer_5km", "disputed", "protected", "seasonal_closure", "boat_class_zones"],
             "layers_loaded": ["land", "eez_buffer_5km"], "incomplete_policy": "label", "eez_buffer_km": 5 },
  "sources": {
    "sst":       [ { "source_id": "erddap_mur_sst",      "role": "primary" } ],
    "chl":       [ { "source_id": "erddap_viirs_chl",    "role": "primary" } ],
    "depth":     [ { "source_id": "erddap_etopo_depth",  "role": "primary" } ],
    "wave_wind": [ { "source_id": "open_meteo_marine",   "role": "primary" } ]
  },
  "schedule": { "run_local_time": "03:00", "retries": 3 },
  "notices": ["satellite_estimate_not_legal_boundary", "trial_area"]
}
```

Where the numbers come from: bbox from the Chonburi proposal in `TASK.md` 4.1 (and it contains the prototype's three
Chonburi demo spots, read from `src/data/spots.js`); time zone, weights `0.20/0.20/0.25/0.15/0.10/0.10` and boat-class
thresholds from ARCHITECTURE.md A2/A5 (the weights there are labelled illustrative); freshness `exp(-max(0, age - grace)/decay)`
and the SST/chlorophyll targets from the prototype (`src/config.js`, `src/services/marine-data.js`, marked untuned);
max-age and fresh-day values, `schedule`, and the `medium` class `max_range_km: null` are **mine, UNVERIFIED**.
The bbox yields 10 x 20 = **200 cells** at 0.05 degree (cell centres 100.725..101.175 E, 12.225..13.175 N). That count
is arithmetic, not run.

### 3.3 Licence route A/B switch and swappable sources

Every fetcher class declares `routes = ("A",)` or `("A", "B")` (from ARCHITECTURE.md A7; the register is in
`API_CONTRACT.md` section 10). `registry.py` refuses to instantiate a fetcher whose routes do not include the area's
`licence_route`, and **does not substitute another source on its own**: switching to route B means writing or choosing
an allowed fetcher (ECMWF Open Data or NOAA GFS/WaveWatch for wave/wind, official announcements instead of WDPA, no Global
Fishing Watch) and listing it in the area file. Until then that variable is `never`/`expired` and the answer says so.

A variable's list in `sources` is an ordered chain: primary, then fallbacks. The ingest job retries the primary
3 times with back-off, then tries the next fetcher, then keeps the latest stored data with its age (S C2). Which
fetcher won is recorded in `job_runs` and shown per observation (`source_id`). Swapping MODIS for VIIRS or a new sensor
is a new fetcher and a config line.

### 3.4 Secrets

Secrets are **environment variables or the host's secret store only**. The repository is public. Names (no values here, none
anywhere in git):

| Variable | Used by | Meaning |
| --- | --- | --- |
| `DATABASE_URL_API` | API | connection string of the **read-only** role |
| `DATABASE_URL_INGEST` | ingest | connection string of the write role |
| `CORS_ALLOW_ORIGINS` | API | comma-separated front-end origins |
| `LOG_LEVEL` | both | default `INFO` |
| `SENTRY_DSN` | both, optional | error monitoring (A2 lists Sentry); leave unset to disable |
| `GFW_API_TOKEN` | back-test only | Global Fishing Watch token, **internal back-testing only** (licence CC BY-NC); never read by the API |

Rules: no secret in a config file, a log, an error body, a test fixture or a prompt; `settings.py` never prints values;
`job_runs.detail` and `error_code` never hold URLs with tokens; a `.env` file is for local use only and is ignored by
`backend/.gitignore`. Supabase's service-role key is **not used** by this design (the API and ingest connect as
their own database roles), so it should never be put in the front end or the repo.

## 4. Ingest and compute: design notes for whoever builds it

1. **Order per area and local date:** fetch sources, then mask, then FSI, then picks. Each step writes a `job_runs` row
   (`running`, then `success`/`partial`/`failed`). A re-run is an upsert on the table keys and a new `attempt` number
   (idempotent); a half-finished run never leaves a `recommendations` row without its mask and FSI rows (the foreign
   keys forbid it). Write each step in one transaction.
2. **One request per variable per area, not per cell.** The prototype asks ERDDAP per spot. For 200 cells ask for the
   bbox. MUR is 0.01 degree, so the bbox is about 50 x 100 = 5000 points per day (arithmetic): fetch full resolution
   and take the **mean of each 0.05 degree block**, rather than a strided point sample like the stride-5 example in A7
   (D), which skips 24 of every 25 pixels. Decision for the ingest builder; document the choice in the fetcher.
3. **Front (S_front).** Gradient magnitude from the full-resolution SST, aggregated to the cell, then a percentile
   within the area for that day (A4). Needs at least a minimum number of valid cells (config) or `s_front` is null.
4. **Dates.** Observations are dated in UTC by the provider; `run_date` is the area-local date (API_CONTRACT.md section 2).
   Age is whole local days. Use IANA zones (`zoneinfo`); never add a fixed offset.
5. **Validate on the way in.** Reject NaN, infinity and out-of-range values before the database sees them (the CHECK
   constraints are the second line). Fill values (for example ERDDAP `NaN`, `-9999`) become `NULL`, never `0`.
6. **Never trust the upstream's shape.** Check axis order and units on every response; treat an empty or truncated grid
   as a failed attempt (`error_code = empty_grid`), not as "all cells have no value".
7. **Failure behaviour.** Retry 3 times, then fallback fetcher, then keep yesterday's data (its age grows, its weight
   falls, past `max` it is ignored). Alert (log + Sentry if set) when a source has been `stale` for 2 runs.
8. **Back-test later in the week.** Needs the same `fsi_daily` rows for past dates, produced with the same code and a
   stored `config_sha256`; so the compute step must accept a `--date` in the past and the sources must offer history
   (MUR and chlorophyll do; Open-Meteo's marine history is a separate endpoint, UNVERIFIED). Global Fishing Watch
   stays out of the API and out of git.

## 5. Decisions needed from the owner

The four from `TASK.md` section 6 that this design depends on are repeated; the rest are new. My default is what the
documents assume if you say nothing.

| # | Decision | My default | Needed by |
| --- | --- | --- | --- |
| 1 | **Legal-incomplete policy** for the demo area (`TASK.md` open question 3): `label` (return spots marked "trial: legal layers incomplete, not for real use") or `withhold` (return none) | `label` | before the front end is wired (Mon) |
| 2 | Where FastAPI runs and who creates the account (`TASK.md` open question 2) | Render or Fly, owner creates | before deploy (Mon) |
| 3 | Demo area: Chonburi coast bbox `[100.7, 12.2, 101.2, 13.2]`, id `th-chonburi-coast` (`TASK.md` open question 4) | as written | before ingest (Sat) |
| 4 | `backend/` inside this repository (`TASK.md` open question 6) | yes | now |
| 5 | **Front-end fallback** when the API is unreachable: show the in-browser demo path labelled "demo, not filtered", or show nothing (API_CONTRACT.md risk R1) | labelled demo, never on a `200` | before the front end is wired |
| 6 | Boat classes in scope this week: `small` only, or `small` and `medium` (A5 gives both; `max_range_km` for `medium` is unknown) | both in config, UI uses `small` | Sat |
| 7 | Missing wave/wind forecast for a cell: not recommended (yellow with `forecast_missing`) | not recommended | Sat |
| 8 | Area-level sea state = worst cell (conservative), with `share_*` fractions | worst cell | Sat |
| 9 | Spot spacing: G's 5 km does nothing on this grid (R3); use 10-15 km or a minimum cell gap | config keeps 5 km (the spec) until you choose; I recommend 10 km | Sun |
| 10 | Starting freshness limits and confidence thresholds (API_CONTRACT.md 4.6, section 7) are mine, unverified | as written, tune after the back-test | Sun |
| 11 | Open API without a key and with CORS limited to the front end, request logs without personal data | yes | Mon |
| 12 | Attribution wording for each source: owner or the PM checks the provider terms (`text_verified: false` until then) | placeholders | Tue |
| 13 | Supabase: project region, and a read-only and a write database role created by you (passwords only in the host's secret store) | owner creates | Sat |
| 14 | Global Fishing Watch token for the back-test (`TASK.md` open question 5) | skip unless you register | Tue |
| 15 | Add `.env` and `backend/` to the repository root's `.gitignore` and a root `.vercelignore` (see section 6, findings F1 and F2); the root files are outside this task | PM does it | before any `.env` exists |

## 6. Findings made while designing (not fixed; outside this task's files)

| ID | Severity | Finding | Evidence | Fix |
| --- | --- | --- | --- | --- |
| F1 | Medium | The repository root `.gitignore` lists only `.vercel`, `.DS_Store`, `Thumbs.db`, `node_modules`. A `.env` file created at the root, or in any folder without its own ignore, would be committed to a **public** repository. Actor: any contributor creating a local `.env`; precondition: `git add -A` or `git add .` (which `CLAUDE.md` forbids, but a human or another tool may do). | MEASURED 2026-11-26: `cat .gitignore` on `main` at `19cc7b6` | add `.env`, `.env.*`, `!.env.example` to the root `.gitignore`. `backend/.gitignore` in this branch covers only `backend/` |
| F2 | Low | `vercel.json` serves the repository as static files with no build, so `backend/` (the schema, the contract, later the config files and any file placed there by mistake) would be published at `/backend/...` on the front end's domain. Nothing secret is in git, but a local untracked `.env` could be uploaded by a CLI deploy. UNVERIFIED which deploy method the owner uses (Git integration deploys only tracked files). | `vercel.json` and `AGENTS.md` section 5 read; no deploy tested | root `.vercelignore` listing `backend/`, or a Vercel "root directory" setting |
| F4 | Low | `schema.sql` creates PostGIS in the `extensions` schema (the Supabase convention). On a database that already has PostGIS in `public` (the `postgis/postgis` Docker image's default database) it stops with `type "extensions.geometry" does not exist`. Create the test database `TEMPLATE template0`, or drop the extension first. Fixed in the test instructions, not in the schema. | MEASURED 2026-11-26 | document only |
| F3 | Low | The root `README.md` and `AGENTS.md` repository maps do not mention `backend/` yet. | read | PM updates after the owner approves the layout |

## 7. Verification status of this design (what was and was not run)

| Item | Result | Label |
| --- | --- | --- |
| `schema.sql` executed on PostgreSQL/PostGIS | **EXECUTED by the PM on 2026-11-26** on `postgis/postgis:16-3.7` (PostgreSQL 16.16, PostGIS 3.7.0) in a clean database: applies with no error. `db/tests/schema_test.sql` then passed **42 of 42** checks: cell-id vectors in SQL, generated columns, 21 guard tests that must reject, 4 mutation tests (remove one guard, the forbidden write is then accepted, so the guard tests can fail), the views. The first run found a hole (no-SST cell could be recommended); fixed with the `scored` column and foreign key. **Still not run:** Supabase itself (its role setup, `security_invoker` on its PostgreSQL version, RLS with real roles) | MEASURED 2026-11-26 |
| Cell-id scheme | the integer method and its test vectors were computed in Python 3.12 on 2026-11-26; the SQL function was not run | MEASURED (Python only) |
| Structural lint of `schema.sql` | a throwaway script (not committed) checked: balanced parentheses, every statement terminated, every `REFERENCES` / `FOREIGN KEY` target table and column exists in the file. This is **not** a PostgreSQL parse | MEASURED 2026-11-26, see the report |
| Contract examples | illustrative; the FSI in the example was recomputed with the formula, not produced by a model | MEASURED (arithmetic) |
| Licence statements | copied from ARCHITECTURE.md A7; sources not opened | REPORTED |
| Upstream datasets (ERDDAP names, Open-Meteo near-shore coverage) | not queried (no network calls were allowed) | not tested |
| Supabase behaviour | public docs searched on 2026-11-26: PostGIS belongs in a dedicated schema such as `extensions`, not `public`; the Data API exposes `public` by default; your own tables still need RLS; Supabase has announced that new tables will no longer be exposed to the Data API automatically (changelog 45329, details not read). Current defaults for custom schemas are **UNVERIFIED** | REPORTED |

Docs consulted: [PostGIS on Supabase](https://supabase.com/docs/guides/database/extensions/postgis),
[Security Advisor and PostGIS objects](https://supabase.com/kb/troubleshooting/security-advisor-flags-spatial_ref_sys-and-other-postgis-objects-in-the-public-schema-f9d408),
[Data API exposure change](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically).

## 8. First steps for the builder (when the owner approves)

1. ~~Run `db/schema.sql` on a throwaway PostGIS~~ — done 2026-11-26 (see section 7). Re-run `db/schema.sql` and
   `db/tests/schema_test.sql` on every schema change, and once on a Supabase branch before the demo.
2. Write `app/schemas.py` from the contract and the contract tests in `API_CONTRACT.md` section 12 first; make each
   go red by removing its guard before trusting it (`AGENTS.md` section 7, rule 5).
3. One dry run of each fetcher on the bbox with output to a scratch folder; record dataset, axis order, fill values
   and coverage near the coast (this settles R5).
