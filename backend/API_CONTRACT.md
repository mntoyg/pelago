# Pelago Asia backend: API contract `/v1`

**Status: DRAFT for owner review. Design only.** Nothing described here is implemented, deployed or tested. Written
2026-11-26 on branch `feature/backend-contract` for the one-week slice in `TASK.md` section 4.1.

Related: [`../ARCHITECTURE.md`](../ARCHITECTURE.md) (target design; cited below as A2, A4, A5, A7, A9),
[`db/schema.sql`](db/schema.sql) (draft schema), [`README.md`](README.md) (service layout, configuration, decisions
needed). Spec references: **S** = function spec 2026-11-24 (authoritative, decision D2), **G** = build guide
2026-11-21. Anything marked **UNVERIFIED** was not confirmed by running it or reading the primary source.

All example values in this file are **ILLUSTRATIVE**. They are not model output and not measurements.

---

## 1. Endpoints

| Method and path | Purpose | Spec | Built this week |
| --- | --- | --- | --- |
| `GET /v1/areas` | list areas (summary) | C2 | yes |
| `GET /v1/areas/{area_id}` | area metadata: bbox, time zone, boat classes and thresholds, attributions, legal status | A5, A2 | yes |
| `GET /v1/areas/{area_id}/spots` | the 1-5 recommended spots for a local date and boat class, with FSI, sub-scores, confidence, data ages, sea state, legal status | C4, C5 (area part) | yes |
| `GET /v1/areas/{area_id}/freshness` | per-source and per-job freshness for one area | C2, C14 (light) | yes |
| `GET /v1/health` | liveness and database reachability, no area data | C14 (light) | yes |
| `GET /v1/areas/{area_id}/cells` | every scored cell with its mask flags (map layer, back-test) | C12 | **reserved**, not built |
| `GET /v1/areas/{area_id}/outlook` | 7-day wave / wind outlook | C6 | **reserved**, not built |

Reserved paths return `404 not_found` until built. They are listed so nobody reuses the names. When `cells` is built
it must carry the mask flags next to every FSI, so a score in a forbidden zone cannot be mistaken for a
recommendation.

Not in this contract (not in this week, `TASK.md` 4.1): sign-up and any user data (C1, C9, C10), prices, tides,
fish ID, chat connectors, admin writes. **The API is read-only and holds no personal data.**

## 2. Conventions

| Topic | Rule |
| --- | --- |
| Transport | HTTPS only (the host terminates TLS). `GET`, `HEAD`, `OPTIONS` only; any other method is `405`. |
| Format | JSON, UTF-8, `Content-Type: application/json` (errors: `application/problem+json`). Keys are `snake_case`. |
| Versioning | Major version in the path (`/v1`). Within `v1` changes are additive only: new optional keys, new enum values only where noted. Clients ignore unknown keys. The body carries `api_version` (`"1.0"`), minor bumps for additive changes. |
| Time | **Every timestamp is UTC**, ISO 8601 with `Z`, whole seconds: `2026-11-26T20:00:00Z`. Never a local offset. |
| `date` parameter and fields | A **calendar date in the area's own time zone** (`YYYY-MM-DD`), because the fisher's day is local. Stored as `run_date`. Default when omitted: today in the area's time zone. |
| Coordinates | WGS84 (EPSG:4326), decimal degrees, **at most 4 decimals** (about 11 m), always `{ "lat": number, "lon": number }`. Longitude `-180 <= lon < 180`, latitude `-90 <= lat < 90`. The server rounds half away from zero to 4 decimals before using an input. The shape is `lat`/`lon` objects so the order cannot be swapped by accident (the front end's `spot.coord` is `[lon, lat]`; see section 8). |
| Grid | 0.05 degree cells, one id scheme `pelago-cell-v1`, `cell_id` an integer computed from coordinates with integer arithmetic (full definition and test vectors in `db/schema.sql`). A cell's `position` is its **centre**. |
| Units | Temperature degC; chlorophyll-a mg/m3; depth metres (positive down); waves metres; wind km/h; distances km; scores unitless. Money is not used this week. |
| Nulls | A missing value is the JSON `null` with the key **present**. Never `0`, `""`, `"N/A"` or `-1` for "no data". This is the main safety rule of the API (see section 4.4). |
| Numbers | JSON numbers, never strings. Rounding on output: `fsi` integer; scores and weights 3 decimals; SST 2; chlorophyll 3; depth 0; wave 2; wind 0; gradient 3. |
| Enums | lower-case strings. |
| Text | Machine codes (`reason_code`, `notices`, `caveats`) are the contract. Human sentences (`reason`, `status_detail`) are English diagnostics; **the front end translates by code** (S: chat/UI text lives in translation files, first version Thai). |
| IDs | `area_id` matches `^[a-z]{2}(-[a-z0-9]+)+$`, max 40 chars, e.g. `th-chonburi-coast`. `boat_class` matches `^[a-z][a-z0-9_]{0,31}$` and must be one of the area's classes. |

### 2.1 Caching

The data changes once per area per day, so responses are cacheable. `ETag` is a strong validator derived from the
`run_id` and the request parameters; `If-None-Match` returns `304` with no body.

| Response | `Cache-Control` |
| --- | --- |
| `/areas`, `/areas/{id}` | `public, max-age=3600` |
| `/spots`, date = today in the area's zone, status `ok` | `public, max-age=300, stale-while-revalidate=300` |
| `/spots`, date in the past, status `ok` | `public, max-age=3600` |
| `/spots`, any status other than `ok` | `public, max-age=60` (a run may finish any minute) |
| `/freshness` | `public, max-age=60` |
| `/health` | `no-store` |
| every error | `no-store` |

Always sent: `ETag` (cacheable GETs), `Vary: Accept-Encoding`, `X-Request-Id` (also in error bodies),
`X-Content-Type-Options: nosniff`. Starting values; the real numbers are tuned once the schedule exists.

### 2.2 Access, CORS, abuse limits

- No authentication this week: the data is public satellite-derived and the API stores nothing about callers. If the
  owner wants a key, it is one environment variable plus a header check; it is not designed here.
- CORS: `Access-Control-Allow-Origin` echoes only origins listed in configuration (the Vercel front end and local
  dev hosts). No credentials, no cookies, `GET` only.
- Rate limit: `429 rate_limited` with `Retry-After`. The numbers depend on the host (UNVERIFIED which limiter the
  chosen host provides); the app must at least cap `limit`, reject unknown parameters and bound every query by
  `(area_id, date)`.
- Request logs must not contain personal data. Client IP is only whatever the host logs by default (decision needed,
  README section 5).

## 3. Area metadata

### 3.1 `GET /v1/areas`

```json
{ "api_version": "1.0", "areas": [ <AreaSummary>, ... ] }
```

`AreaSummary` = `area_id`, `name`, `country_code`, `bbox`, `timezone`, `legal_status`, `verification_level`
(definitions below).

### 3.2 `GET /v1/areas/{area_id}` : `Area`

| Field | Type | Unit / format | Null | Meaning |
| --- | --- | --- | --- | --- |
| `api_version` | string | `"1.0"` | no | |
| `area_id` | string | pattern in section 2 | no | |
| `name` | string | English display name | no | |
| `names` | object | map language code to string, e.g. `{"th": "ชายฝั่งชลบุรี"}` | no (may be `{}`) | optional translations of the name |
| `country_code` | string | ISO 3166-1 alpha-2 | no | |
| `timezone` | string | IANA name, e.g. `Asia/Bangkok` | no | defines the local `date` |
| `bbox` | number[4] | `[min_lon, min_lat, max_lon, max_lat]`, WGS84, 4 decimals | no | the area; the grid covers cells whose centre is inside |
| `grid` | object | `{ "scheme": "pelago-cell-v1", "cell_deg": 0.05 }` | no | |
| `sea_window_local` | string[2] | `["04:00","14:00"]`, local `HH:MM` | no | time at sea over which wave/wind maxima are taken (A5 filter 6) |
| `boat_classes` | object | map `boat_class` to `BoatClass` | no | at least one |
| `fsi` | object | `{ "model_version": string, "weights": {sst,front,chl,depth,moon,season}, "weights_status": "untuned" }` | no | weights are numbers >= 0; always `"untuned"` until fitted on verified catch logs (A4) |
| `verification` | object | `{ "level": "trial"\|"beta"\|"confirmed", "verified_trips": integer }` | no | A9. Only `confirmed` areas may show accuracy claims. |
| `legal` | object | `Legal` (section 4.3) | no | |
| `licence_route` | string | `"A"` or `"B"` | no | which licence route the data sources were enabled under (section 9) |
| `sources` | object[] | `SourceInfo` | no | the fetchers enabled for this area |
| `attributions` | object[] | `Attribution` | no | credit lines the UI must display (A7) |
| `notices` | string[] | codes | no | e.g. `satellite_estimate_not_legal_boundary`, `trial_area` |
| `config_hash` | string | first 12 hex chars of the config file's SHA-256 | no | ties results to the config that produced them |

`BoatClass`:

| Field | Type | Unit | Null | Meaning |
| --- | --- | --- | --- | --- |
| `label_key` | string | translation key | no | UI label looked up in the front end's translation file |
| `length_m_min` | number | m | no | |
| `length_m_max` | number | m | **yes** | `null` = no upper bound |
| `max_range_km` | number | km, round trip safe range | **yes** | `null` = not set (not used for filtering this week, there is no port or route yet) |
| `wave_yellow_m` | number | m | no | caution at wave >= this |
| `wave_red_m` | number | m | no | do not go at wave >= this |
| `wind_yellow_kmh` | number | km/h | no | |
| `wind_red_kmh` | number | km/h | no | |

Starting values from ARCHITECTURE.md A5 (to be tuned with local fishers and agencies before real use):

| `boat_class` | length | wave yellow / red | wind yellow / red |
| --- | --- | --- | --- |
| `small` | under 10 m | 1.0 / 1.5 m | 20 / 30 km/h |
| `medium` | 10 to 18 m | 1.5 / 2.5 m | 30 / 40 km/h |

A5 also makes thunderstorms red for the small class; that rule needs a data source that is not in this week's
plan, so the API reports it as a caveat (section 4.3) instead of silently skipping it. `max_range_km` for `medium` is
not given in the reference documents: `null`.

`SourceInfo`: `variable` (`sst`\|`chl`\|`depth`\|`wave_wind`), `source_id` (string, fetcher id from config),
`role` (`primary`\|`fallback`), `provider` (string), `dataset_id` (string), `route_allowed` (`["A"]` or `["A","B"]`).
All non-null.

`Attribution`: `attribution_id` (string), `text` (string, the exact credit line to show), `url` (string or **null**),
`required` (boolean), `applies_to` (array of variables), `text_verified` (boolean; `false` means the wording has not
been checked against the provider's terms and must be confirmed before launch).

## 4. Spots: `GET /v1/areas/{area_id}/spots`

### 4.1 Request

| Parameter | Type | Default | Rules |
| --- | --- | --- | --- |
| `area_id` (path) | string | required | pattern above, else `422`; unknown area `404 area_not_found` |
| `date` | `YYYY-MM-DD` | today in the area's zone | must be a real calendar date; not in the future; not older than the area's retention (default 60 days); else `422 date_out_of_range` |
| `boat_class` | string | the area's first class (`small`) | must be an area class, else `422 unsupported_boat_class` |
| `limit` | integer | 5 | `1..5`; picks are the 3-5 best cells at least `min_spacing_km` apart (G p.9) |

Unknown query parameters are `422 unknown_parameter` (so a typo such as `boatclass` cannot silently return the wrong
class).

### 4.2 Response envelope

| Field | Type | Unit / format | Null | Meaning |
| --- | --- | --- | --- | --- |
| `api_version` | string | `"1.0"` | no | |
| `area_id` | string | | no | |
| `date` | string | `YYYY-MM-DD`, area-local | no | the date answered |
| `boat_class` | string | | no | the class answered |
| `status` | string | enum below | no | **read this before `spots`** |
| `status_detail` | string | English sentence | no | one line explaining `status` |
| `generated_at` | string | UTC timestamp | no | when the run that produced this answer finished (not the request time) |
| `run_id` | string | UUID | **yes** | the run; `null` when `status` is `no_run` |
| `model_version` | string | `fsi-v1.0.0` pattern | no | version of the scoring code that is active for the area |
| `config_hash` | string | 12 hex chars | no | config the run used |
| `verification_level` | string | `trial`\|`beta`\|`confirmed` | no | |
| `confidence_ceiling` | string | `high`\|`medium` | no | `medium` while the area has no verified catch logs (S p.7) |
| `legal` | object | `Legal` | no | |
| `area_sea_state` | object | `AreaSeaState` | no | **shown before any spot**; derived from the same run |
| `sources` | object | map variable to `SourceSummary` | no | newest data per source that fed the run, even when `spots` is empty |
| `caveats` | string[] | codes | no | limits of this answer, e.g. `legal_layers_incomplete`, `no_official_warning_feed`, `no_thunderstorm_rule` |
| `notices` | string[] | codes | no | texts the UI must show (e.g. `satellite_estimate_not_legal_boundary`) |
| `attribution_ids` | string[] | ids from the area's `attributions` | no | credits for the data actually used |
| `spots` | object[] | `Spot`, ordered by `rank` | no | empty unless `status` is `ok` |

`status` (additive enum; clients must treat an unknown value as "no recommendation"):

| `status` | Meaning | `spots` |
| --- | --- | --- |
| `ok` | at least one eligible, scored cell was picked | 1 to `limit` items |
| `no_run` | no completed compute run for that date (not run yet, or it failed) | `[]` |
| `no_data` | a run exists but **no cell has an SST value** (no data = no recommendation) | `[]` |
| `no_eligible_cells` | scored cells exist but none may be recommended (legal mask, missing forecast, spacing) | `[]` |
| `withheld_sea_red` | scored, legally allowed cells exist but every one is red for this boat class | `[]` |
| `withheld_legal_incomplete` | the area's policy is `withhold` and its legal layers are incomplete | `[]` |

Precedence when several apply: `no_run`, `withheld_legal_incomplete`, `no_data`, `withheld_sea_red`,
`no_eligible_cells`, `ok`. HTTP status is `200` for all of them: an honest "nothing to recommend" is a valid answer,
not a failure. The front end must not treat a `200` with empty `spots` as a reason to show anything else.

`SourceSummary`: `source_id` (string, **null** if never ingested), `observed_at` (UTC timestamp, **null**; newest
observation date over the area), `age_days` (integer, **null**), `status` (`fresh`\|`stale`\|`expired`\|`never`, defined in
section 7).

### 4.3 Shared objects

`Legal` (area-level and, as `legal_status`, per spot):

| Field | Type | Null | Meaning |
| --- | --- | --- | --- |
| `status` | `"complete"`\|`"incomplete"` | no | `complete` only when **every** legal layer was checked for that cell/area (EEZ with 5 km buffer, disputed areas, protected zones, closed seasons, boat-class zones; A5 filters 1-5) |
| `layers_checked` | string[] | no | e.g. `["land","eez_buffer_5km"]` |
| `layers_missing` | string[] | no | e.g. `["disputed","protected","seasonal_closure","boat_class_zones"]`; empty when `complete` |
| `incomplete_policy` | `"label"`\|`"withhold"` | no | what the area does while incomplete: `label` returns spots flagged `incomplete`; `withhold` returns none (owner decision, open question 3 in `TASK.md`) |

For the Chonburi demo area this week the status is `incomplete` with the four layers above missing (`TASK.md` 4.1,
item 3). **A spot with `legal_status: "incomplete"` is a trial output, "not for real use"; the UI must label it.**

`AreaSeaState`:

| Field | Type | Unit | Null | Meaning |
| --- | --- | --- | --- | --- |
| `level` | `"green"`\|`"yellow"`\|`"red"` | | no | the **worst** level over the area's water cells for this boat class (conservative: one red corner makes the area red) |
| `reason_code` | string | enum in 4.5 | no | |
| `reason` | string | English | no | one line, e.g. "Waves up to 1.7 m, above the 1.5 m limit for small boats" |
| `share_red` | number | fraction 0-1 | no | share of water cells that are red |
| `share_yellow` | number | fraction 0-1 | no | |
| `share_no_forecast` | number | fraction 0-1 | no | share of water cells without a usable wave/wind forecast |
| `window_local` | string[2] | `HH:MM` local | no | same as the area's `sea_window_local` |

### 4.4 Rules the server must enforce (each has a test that must go red when the rule is removed)

1. **No SST, no score.** A cell without an SST value has `fsi = null` (not `0`), and is never a spot. (S p.7;
   differs from the prototype, which scores such a cell, see section 8.)
2. **No data, no recommendation.** `spots` contains only cells with a non-null `fsi`, `eligible = true` for the boat
   class, and a usable wave and wind forecast. A missing or stale forecast makes the cell ineligible (A5 says both
   "send no spot" and "treat as yellow"; the server does both: the cell is `yellow` with `reason_code`
   `forecast_missing` and is not recommended. Interpretation, open question D6).
3. **Red is never returned.** No spot has `sea_state.level = "red"`. The enum allows it so the same type can be used
   by the reserved `cells` endpoint.
4. **Forbidden is never returned.** A cell with any legal flag `false` is never a spot; a cell whose legal flag is
   unknown (`null`, layer not loaded) is a spot only under `incomplete_policy = "label"` and then carries
   `legal_status: "incomplete"`. The database enforces this independently (`cell_mask_daily` CHECK and the composite
   foreign keys from `recommendations`).
5. **Confidence is capped.** While `verification_level` is `trial`, no spot has `confidence = "high"` and
   `confidence_cap = "no_verified_catch_logs"` (S p.7).
6. **Only measured freshness.** `observed_at` and `age_days` come from the stored observation, never from the time of
   the request.
7. **Spacing.** Picks are at least `min_spacing_km` apart (config, default 5 km as in G p.9; see risk R3: at a 0.05
   degree grid every distinct cell centre is already at least 5.4 km from its neighbour at 12-13 degrees north, so 5 km
   does not spread the picks).
8. **Determinism.** Same `(area_id, date, boat_class, run)` gives byte-identical bodies (stable key order, stable
   rounding), so `ETag` works.

### 4.5 `Spot`

| Field | Type | Unit / format | Null | Meaning |
| --- | --- | --- | --- | --- |
| `rank` | integer | 1..5 | no | 1 = best |
| `cell_id` | integer | `pelago-cell-v1`, 0..25 919 999 | no | stable id; the same cell has the same id in every table and every day |
| `position` | object | `{lat, lon}`, WGS84, 4 decimals, cell centre | no | |
| `fsi` | integer | 0-100, rounded | **yes** | **never null inside `spots` in v1**; nullable so the reserved `cells` endpoint can share the type. `null` always means "no SST, not scored", never zero |
| `subscores` | object | keys `sst`, `front`, `chl`, `depth`, `moon`, `season`, each a `SubScore` | no | the explanation of `fsi` (AGENTS.md section 6, rule 3: show inputs and limits) |
| `confidence` | string | `high`\|`medium`\|`low` | no | rule in 4.6 |
| `confidence_cap` | string | `"no_verified_catch_logs"` | **yes** | non-null when the cap lowered or limits the result |
| `confidence_reasons` | string[] | codes: `sst_missing`, `sst_stale`, `chl_missing`, `chl_stale`, `depth_missing`, `front_missing`, `no_verified_catch_logs`; and, added 2026-11-26 (additive), `sst_invalid`, `front_invalid`, `chl_invalid`, `depth_invalid`: the input exists but was refused (not finite, out of range, no or naive timestamp, or dated after the end of the local `date`), so it carries weight 0 | no (may be `[]`) | why not higher |
| `model_version` | string | `fsi-v1.0.0` pattern | no | scoring code version that produced `fsi` |
| `observations` | object | see below | no | the inputs, each with its date and age |
| `sea_state` | object | `SeaState` | no | for this cell and boat class |
| `legal_status` | string | `"complete"`\|`"incomplete"` | no | `incomplete`: the UI labels the spot as a trial |
| `notices` | string[] | codes | no | per-spot notices, usually `[]` |

`SubScore`:

| Field | Type | Unit | Null | Meaning |
| --- | --- | --- | --- | --- |
| `score` | number | 0-1, 3 decimals | **yes** | `null` = cannot be computed (no input). Excluded from the weighted average |
| `weight` | number | >= 0 | no | weight from the area config |
| `freshness` | number | 0-1, 3 decimals | **yes** | `a_i` in `FSI = 100 * sum(w_i a_i S_i) / sum(w_i a_i)` (A4); `null` when `score` is `null` |

`observations` (every member always present):

| Key | Shape | Unit |
| --- | --- | --- |
| `sst` | `Observation` | degC |
| `front` | `Observation` (value = SST gradient) | degC per km |
| `chl` | `Observation` | mg/m3 |
| `depth` | `Observation` | m, positive down |
| `wave` | `Forecast` | m, maximum over the sea window |
| `wind` | `Forecast` | km/h, maximum over the sea window |
| `moon` | `{ "phase": number, "age_days": number, "illumination": number }` | phase 0-1 through the cycle, age in days, illumination fraction 0-1. Computed from the date, never null |

`Observation`:

| Field | Type | Unit / format | Null | Meaning |
| --- | --- | --- | --- | --- |
| `value` | number | per table above | **yes** | `null` = no observation |
| `observed_at` | string | UTC timestamp of the observation | **yes** | null iff `value` is null. For SST this is the product's own timestamp (e.g. the MUR analysis time), not the download time |
| `age_days` | integer | days, >= 0 | **yes** | area-local `date` minus the local date of `observed_at`, floored at 0 |
| `source_id` | string | config fetcher id | **yes** | which fetcher delivered it (primary or a fallback; a fallback is visible here) |
| `product` | string | `daily`\|`8day`\|`null` | **yes** | chlorophyll only: cloud-gap composites are labelled (G p.6); `null` elsewhere |

`Forecast` (wave, wind): `value` (number, **null**), `issued_at` (UTC timestamp, **null**; retrieval time, because Open-Meteo does not return a forecast issue time),
`age_hours` (integer >= 0, **null**), `window_local` (`["04:00","14:00"]`, no), `source_id` (string, **null**).

`SeaState`:

| Field | Type | Null | Meaning |
| --- | --- | --- | --- |
| `level` | `"green"`\|`"yellow"`\|`"red"` | no | `red` if wave >= `wave_red_m` or wind >= `wind_red_kmh`; else `yellow` if wave >= `wave_yellow_m` or wind >= `wind_yellow_kmh`; else `green`; comparisons are `>=` over the sea-window maxima. Missing/stale forecast = `yellow` with a `forecast_*` reason and the cell is not recommended |
| `reason_code` | string | no | `calm`, `wave_caution`, `wind_caution`, `wave_wind_caution`, `wave_danger`, `wind_danger`, `wave_wind_danger`, `forecast_missing`, `forecast_stale` |
| `reason` | string | no | English one-liner for logs and fallback display |
| `boat_class` | string | no | the class the thresholds came from |

### 4.6 Confidence rule (one rule, replaces the two in the prototype, `TASK.md` section 5)

Evaluated per spot from stored inputs; thresholds come from the area config (starting values, mine, UNVERIFIED):

1. Start at `low`.
2. `medium` when **all** of: `sst`, `front`, `chl`, `depth` have values; SST age <= 2 days; chlorophyll age <= 3 days
   (for a `daily` product) or <= 8 days (for an `8day` product).
3. `high` only when rule 2 holds **and** the area `verification.level` is `beta` or `confirmed` (A9: 100+ verified
   trips). Otherwise it is capped at `medium` and `confidence_cap = "no_verified_catch_logs"`.
4. Every missed condition adds a code to `confidence_reasons`.

This week no area can reach `high`.

### 4.7 Example (ILLUSTRATIVE VALUES, abbreviated to one spot)

```json
{
  "api_version": "1.0",
  "area_id": "th-chonburi-coast",
  "date": "2026-12-01",
  "boat_class": "small",
  "status": "ok",
  "status_detail": "1 spot picked from 63 eligible cells; legal layers incomplete (trial).",
  "generated_at": "2026-11-30T21:14:05Z",
  "run_id": "00000000-0000-0000-0000-000000000000",
  "model_version": "fsi-v1.0.0",
  "config_hash": "0123456789ab",
  "verification_level": "trial",
  "confidence_ceiling": "medium",
  "legal": { "status": "incomplete", "layers_checked": ["land", "eez_buffer_5km"],
             "layers_missing": ["disputed", "protected", "seasonal_closure", "boat_class_zones"],
             "incomplete_policy": "label" },
  "area_sea_state": { "level": "yellow", "reason_code": "wave_caution",
                      "reason": "Waves up to 1.2 m, above the 1.0 m caution level for small boats",
                      "share_red": 0.0, "share_yellow": 0.41, "share_no_forecast": 0.05,
                      "window_local": ["04:00", "14:00"] },
  "sources": {
    "sst":       { "source_id": "erddap_mur_sst", "observed_at": "2026-11-30T09:00:00Z", "age_days": 1, "status": "fresh" },
    "chl":       { "source_id": "erddap_viirs_chl", "observed_at": "2026-11-28T00:00:00Z", "age_days": 3, "status": "fresh" },
    "depth":     { "source_id": "erddap_etopo_depth", "observed_at": null, "age_days": null, "status": "fresh" },
    "wave_wind": { "source_id": "open_meteo_marine", "observed_at": "2026-11-30T18:00:00Z", "age_days": 0, "status": "fresh" }
  },
  "caveats": ["legal_layers_incomplete", "no_official_warning_feed", "no_thunderstorm_rule"],
  "notices": ["satellite_estimate_not_legal_boundary", "trial_area"],
  "attribution_ids": ["mur_sst", "open_meteo"],
  "spots": [
    {
      "rank": 1, "cell_id": 14736818, "position": { "lat": 12.325, "lon": 100.925 },
      "fsi": 77,
      "subscores": {
        "sst":    { "score": 0.912, "weight": 0.2,  "freshness": 1.0 },
        "front":  { "score": 0.640, "weight": 0.2,  "freshness": 1.0 },
        "chl":    { "score": 0.701, "weight": 0.25, "freshness": 0.513 },
        "depth":  { "score": 0.980, "weight": 0.15, "freshness": 1.0 },
        "moon":   { "score": 0.772, "weight": 0.1,  "freshness": 1.0 },
        "season": { "score": 0.500, "weight": 0.1,  "freshness": 1.0 }
      },
      "confidence": "medium", "confidence_cap": "no_verified_catch_logs", "confidence_reasons": ["no_verified_catch_logs"],
      "model_version": "fsi-v1.0.0",
      "observations": {
        "sst":   { "value": 29.31, "observed_at": "2026-11-30T09:00:00Z", "age_days": 1, "source_id": "erddap_mur_sst", "product": null },
        "front": { "value": 0.021, "observed_at": "2026-11-30T09:00:00Z", "age_days": 1, "source_id": "erddap_mur_sst", "product": null },
        "chl":   { "value": 0.812, "observed_at": "2026-11-28T00:00:00Z", "age_days": 3, "source_id": "erddap_viirs_chl", "product": "daily" },
        "depth": { "value": 31, "observed_at": null, "age_days": null, "source_id": "erddap_etopo_depth", "product": null },
        "wave":  { "value": 0.74, "issued_at": "2026-11-30T18:00:00Z", "age_hours": 3, "window_local": ["04:00", "14:00"], "source_id": "open_meteo_marine" },
        "wind":  { "value": 17, "issued_at": "2026-11-30T18:00:00Z", "age_hours": 3, "window_local": ["04:00", "14:00"], "source_id": "open_meteo_marine" },
        "moon":  { "phase": 0.31, "age_days": 9.2, "illumination": 0.38 }
      },
      "sea_state": { "level": "green", "reason_code": "calm", "reason": "Waves 0.74 m, wind 17 km/h, below the small-boat caution levels", "boat_class": "small" },
      "legal_status": "incomplete",
      "notices": []
    }
  ]
}
```

(The `fsi` of 77 follows the formula in A4 with the prototype's freshness rule `exp(-max(0, age-1)/3)` and the moon rule `1 - 0.6 x illumination`, both starting values; recomputed 2026-11-26, not model output. A real answer carries up to `limit` spots. The `depth` observation has no `observed_at`: depth is a static grid, its
`source_id` is the evidence. Decision D9 below.)

## 5. Errors

Errors use **RFC 9457 problem details** (`application/problem+json`), never a stack trace or an internal message:

```json
{ "type": "urn:pelago:problem:area_not_found", "title": "Area not found", "status": 404,
  "code": "area_not_found", "detail": "No area with this id.", "request_id": "b4e1...",
  "errors": [ { "param": "date", "code": "date_out_of_range", "message": "date is in the future" } ] }
```

`errors` appears only for `422`. `detail` and `message` never echo more than 64 characters of user input and never
include SQL, file paths, hostnames or upstream error text.

| HTTP | `code` | When |
| --- | --- | --- |
| 304 | (no body) | `If-None-Match` matches |
| 404 | `area_not_found` | no such `area_id` |
| 404 | `not_found` | unknown path (including the reserved paths until built) |
| 405 | `method_not_allowed` | anything but `GET`, `HEAD`, `OPTIONS` |
| 422 | `validation_error` | bad `area_id` pattern, bad date format, `limit` out of range. Individual `errors[].code`: `invalid_format`, `date_out_of_range`, `unsupported_boat_class`, `unknown_parameter`, `limit_out_of_range` |
| 429 | `rate_limited` | with `Retry-After` (seconds) |
| 500 | `internal_error` | unexpected; body has `request_id` only |
| 503 | `service_unavailable` | database unreachable; with `Retry-After`. The front end may then use its in-browser demo path (section 8, risk R1) |

A valid request that has nothing to recommend is **`200` with a `status`**, not an error (section 4.2).

## 6. Health: `GET /v1/health`

```json
{ "api_version": "1.0", "status": "ok", "service_version": "0.1.0", "time": "2026-11-30T21:20:00Z",
  "checks": { "database": "ok" } }
```

| Field | Type | Null | Meaning |
| --- | --- | --- | --- |
| `status` | `"ok"` or `"degraded"` | no | `degraded` when a check fails but the process still answers |
| `service_version` | string | no | semantic version of the deployed service |
| `time` | UTC timestamp | no | server time (lets a client detect clock skew) |
| `checks.database` | `"ok"` or `"error"` | no | a trivial query succeeded |

`200` when `status` is `ok`, `503 service_unavailable` when the database check fails. It carries no area data and no
upstream error text, so it is safe to expose to an uptime monitor.

## 7. Freshness: `GET /v1/areas/{area_id}/freshness`

Answers "is this area's data current, which source is behind, did the last job run work" (S C2 and C14 light).

| Field | Type | Unit / format | Null | Meaning |
| --- | --- | --- | --- | --- |
| `api_version` | string | | no | |
| `area_id` | string | | no | |
| `generated_at` | string | UTC timestamp | no | request time |
| `local_date` | string | `YYYY-MM-DD` | no | today in the area's zone, the date ages are measured against |
| `status` | string | `ok`\|`degraded`\|`down` | no | `ok`: every source `fresh` and today's compute done; `degraded`: any source `stale` or `expired`, a fallback is active, or today's compute is not done yet; `down`: no source usable, or the last successful compute is more than 36 h old |
| `sources` | object[] | one per variable | no | see below |
| `compute` | object | `{ "mask": Job, "fsi": Job, "pick": Job }` | no | |
| `next_expected_run_at` | string | UTC timestamp | **yes** | from the schedule config; `null` if not configured |

Source item (variable `sst`, `chl`, `depth`, `wave_wind`):

| Field | Type | Null | Meaning |
| --- | --- | --- | --- |
| `variable` | string | no | |
| `source_id` | string | **yes** | the fetcher that produced the latest success; `null` if never |
| `fetcher_role` | `"primary"`\|`"fallback"` | **yes** | `fallback` = the primary failed after its retries (S C2) |
| `status` | string | no | `fresh`: age <= `fresh_days`; `stale`: older but within `max_age_days`, still used with a lower weight; `expired`: older than `max_age_days`, **not used** (the cell then has no value); `never`: no data ever |
| `latest_data_date` | string | **yes** | `YYYY-MM-DD` UTC date of the newest observation ingested |
| `latest_ingest_at` | string | **yes** | UTC timestamp of the run that fetched it |
| `age_days` | integer | **yes** | `local_date` minus `latest_data_date`, floored at 0 |
| `fresh_days`, `max_age_days` | integer | no | the thresholds in force (config; starting values SST 2 / 5, chlorophyll 3 / 10, wave-wind 1 / 2, depth static) |
| `fallback_active` | boolean | no | |
| `last_attempt` | object | **yes** | `{ "status": "success"\|"partial"\|"failed"\|"running"\|"skipped", "attempt": integer, "started_at": ts, "finished_at": ts or null, "error_code": string or null }` |

`Job` = `{ "last_success_at": ts or null, "run_date": date or null, "model_version": string or null }` (`model_version`
only for `fsi`/`pick`). `error_code` is a short token such as `http_503`, `timeout`, `empty_grid`; raw upstream messages
are never exposed.

## 8. How the payload maps onto what the front end uses today

The prototype consumes `spot.fsi` (number) and `spot.signal = { sst, sstT, chl, chlT, depth, moon }` set by
`fetchSpotSignal` in `src/services/marine-data.js`, read by `src/ui/popup.js` and `src/ui/sidebar.js`. The seam is
that one function: replace its body with an API call and an adapter.

| Front end | Source in the API response | Notes |
| --- | --- | --- |
| `spot.coord` `[lon, lat]` | `[position.lon, position.lat]` | the API uses an object to avoid order mistakes; one line in the adapter |
| `spot.fsi` (number) | `fsi` | **UI change:** `fsi` can be `null` in future endpoints and the popup prints `${spot.fsi}`; handle `null` as "no data" before wiring `cells` |
| `spot.signal.sst` | `observations.sst.value` | degC; `null` means no value (same as today's `undefined` check `signal.sst != null`) |
| `spot.signal.sstT` | `observations.sst.observed_at` | the popup does `.slice(0, 10)`, which gives the UTC date of the observation; ISO UTC keeps that working |
| `spot.signal.chl` / `chlT` | `observations.chl.value` / `.observed_at` | `chlT == null` shows "ไม่มี (เมฆบัง)" as today |
| `spot.signal.depth` | `observations.depth.value` | |
| `spot.signal.moon` `{ph, age, ill}` | `{ ph: moon.phase, age: moon.age_days, ill: moon.illumination }` | `computeFsi` read only `moon.ill`; once the server computes FSI the browser needs no moon maths for scoring (`moonText` can keep its own) |
| `computeFsi` | removed | the browser no longer scores; `subscores`, `confidence`, `legal_status` replace it |
| popup confidence `allLive ? 'กลาง' : 'ต่ำ'` and sidebar `fsi >= 75 ? ... : ...` | `confidence` | one rule from the server (4.6) replaces both; map `high`/`medium`/`low` to Thai labels |
| `spot.name` | not provided | spots are grid cells, not named places. Show `"จุด 0N"` from `rank` plus coordinates. A `label` field is reserved for later |
| `spot.demoMetrics[3]` (distance from port, nm) | not provided | needs ports and routing (C7), out of this week; keep the demo value labelled as a sample |
| `sourceStatus.sst/chl/depth/wx` (1 / -1 / 0) | `/freshness` `sources[].status`: `fresh`,`stale` -> 1; `expired`,`never` -> -1; request pending -> 0 | the data screen's labels stay |
| `weekForecast` (Open-Meteo, 7 days) | unchanged this week | the `outlook` endpoint is reserved |
| country / province / spot tree | the API area is the Chonburi province node; other provinces and countries stay demo and labelled | the UI keeps its "demo" labels everywhere the API has no area |

Adapter sketch (illustrative, not committed in `src/`):

```js
async function fetchSpotSignal(spot) {            // replaces the three NOAA requests
  const o = spot.observations;                    // from the cached /spots response, matched by cell_id
  spot.fsi = spot.apiFsi;                         // null stays null
  spot.signal = { sst: o.sst.value, sstT: o.sst.observed_at, chl: o.chl.value, chlT: o.chl.observed_at,
                  depth: o.depth.value, moon: { ph: o.moon.phase, age: o.moon.age_days, ill: o.moon.illumination } };
}
```

**Safety rule for the fallback.** Plan item 6 says the front end "falls back to today's in-browser path" when the API
is unreachable. That path has **no legal filter, no land mask and no sea-state filter** (ARCHITECTURE.md B3). The
front end may fall back only on a network error or a `5xx`, never on a `200` (including `no_eligible_cells` or
`withheld_sea_red`), and anything shown from the fallback must say "demo, not filtered, not a recommendation". See R1.

## 9. Field-to-column table (schema consistency)

Tables are in `db/schema.sql`, schema `pelago`. "config" = the area config file (`backend/config/areas/<area_id>.json`,
README section 3); "derived" = computed by the service at request time.

| API field | Table . column | Notes |
| --- | --- | --- |
| `area_id` | `regions.region_id` | |
| `country_code`, `timezone` | `regions.country_code`, `regions.timezone` | |
| `bbox` | `regions.min_lon, min_lat, max_lon, max_lat` | `[min_lon, min_lat, max_lon, max_lat]`; `regions.geom` is the same box for spatial queries |
| `name`, `names`, `boat_classes`, `sea_window_local`, `fsi.weights`, `fsi.model_version`, `legal.layers_*` (required set), `legal.incomplete_policy`, `licence_route`, `sources`, `attributions`, `notices` (static part) | config | **not in the database**; the config file is the single source of truth |
| `config_hash` | `regions.config_sha256` (first 12 chars), `fsi_daily.config_sha256` | the run's own hash is on `fsi_daily` |
| `verification.level`, `verification.verified_trips` | `regions.verification_level`, `regions.verified_trips` | |
| `date` | `*.run_date` | area-local date |
| `boat_class` | `cell_mask_daily.boat_class`, `recommendations.boat_class` | |
| `run_id`, `generated_at` | `job_runs.run_id`, `job_runs.finished_at` of the `pick` run (`recommendations.run_id`) | |
| `model_version` | `fsi_daily.model_version`, `recommendations.model_version` | |
| `status`, `status_detail` | derived | from `job_runs` (`no_run`), `fsi_daily` (`no_data`), `cell_mask_daily.eligible/sea_state_level` (`no_eligible_cells`, `withheld_sea_red`), config policy (`withheld_legal_incomplete`) |
| `legal` (area) | derived | aggregate of `cell_mask_daily.legal_status` and the flag columns; `layers_checked` = flags that are not NULL |
| `area_sea_state.level/reason_code/share_*` | derived | worst `cell_mask_daily.sea_state_level` and shares over `is_water` rows |
| `sources.*` (envelope) | derived | newest `grid_daily.*_observed_at` / `wx_issued_at`, `job_runs` for status |
| `spots[].rank` | `recommendations.pick_rank` | |
| `spots[].cell_id` | `recommendations.cell_id` | |
| `spots[].position.lat/lon` | derived | `pelago.cell_centre_lat(cell_id)`, `pelago.cell_centre_lon(cell_id)`; same values as `grid_daily.lat/lon` |
| `spots[].fsi` | `recommendations.fsi` (copy of `fsi_daily.fsi`, rounded for output) | |
| `spots[].subscores.<k>.score` | `fsi_daily.s_sst, s_front, s_chl, s_depth, s_moon, s_season` | |
| `spots[].subscores.<k>.freshness` | `fsi_daily.a_sst, a_front, a_chl, a_depth, a_moon, a_season` | |
| `spots[].subscores.<k>.weight` | config `fsi.weights` | the config hash on the row says which weights |
| `spots[].confidence`, `confidence_cap`, `confidence_reasons` | `fsi_daily.confidence`, `confidence_cap`, `confidence_reasons` (`recommendations.confidence` is a copy) | |
| `spots[].observations.sst.value / observed_at / source_id` | `grid_daily.sst_c`, `sst_observed_at`, `sst_source` | |
| `spots[].observations.front.value` | `grid_daily.sst_grad_c_per_km` | `observed_at` and `source_id` are the SST ones |
| `spots[].observations.chl.value / observed_at / source_id / product` | `grid_daily.chl_mg_m3`, `chl_observed_at`, `chl_source`, `chl_product` | |
| `spots[].observations.depth.value / source_id` | `grid_daily.depth_m`, `depth_source` | no date column: static grid |
| `spots[].observations.wave.value`, `wind.value` | `grid_daily.wave_window_max_m`, `wind_window_max_kmh` | |
| `spots[].observations.wave/wind.issued_at, source_id` | `grid_daily.wx_issued_at`, `wx_source` | |
| `*.age_days`, `*.age_hours` | derived | `run_date` minus the local date of the timestamp; `age_hours` against `fsi_daily.computed_at` |
| `spots[].observations.moon` | derived | computed from the date |
| `spots[].sea_state.level / reason_code` | `cell_mask_daily.sea_state_level`, `sea_reason_code` | |
| `spots[].legal_status` | `cell_mask_daily.legal_status` (`recommendations.legal_status` is a copy) | |
| `freshness.sources[].*` | `v_ingest_last_success`, `v_ingest_last_attempt` (from `job_runs`), thresholds from config | `latest_data_date` = `job_runs.data_date` |
| `freshness.compute.*` | `job_runs` rows with `job_kind` in (`mask`, `fsi`, `pick`) | |
| `health.*` | none | a trivial query only |

Cross-checks the schema enforces for contract rules (4.4): rule 1 `fsi_daily` CHECK `(fsi IS NULL) = (s_sst IS NULL)` plus the foreign key from `recommendations` to the *scored* `fsi_daily` row (`scored` column; added 2026-11-26 after the PM's test showed a no-SST cell could otherwise be stored as a spot);
rules 3 and 4 `cell_mask_daily` CHECK on `eligible` and the composite FK from `recommendations` to
`(…, cell_id, eligible)`; rule 5 `fsi_daily` CHECK on `confidence_cap`.

## 10. Data sources, licence route and attribution

The service reads data through swappable **fetchers**; each declares which licence routes it may be enabled under.
`licence_route` in the area config is `A` (non-profit, decision D3) or `B` (business). The loader refuses to enable a
fetcher not allowed by the route, and **does not substitute silently**: if no allowed fetcher remains for a variable,
that variable reports `never`/`expired` and cells lose that input (and `confidence`). Switching A to B is a config
change plus a fetcher for the replaced sources, not a code change in the core (ARCHITECTURE.md A11).

Licence facts below are copied from ARCHITECTURE.md A7 (as stated in reference document D on 2026-11-25). **None
was independently confirmed here.**

| Variable | This week's fetcher (prototype's dataset) | A7 says | Route | Status |
| --- | --- | --- | --- | --- |
| SST | NOAA ERDDAP `jplMURSST41` (NASA JPL MUR) | commercial: yes | A, B | per A7; **UNVERIFIED** by us |
| Chlorophyll | NOAA ERDDAP `noaacwNPPVIIRSchlaDaily` (VIIRS) | A7 lists Sentinel-3 OLCI (commercial yes, with Copernicus attribution), PACE, MODIS; **VIIRS is not in A7** | A (B unknown) | **UNVERIFIED** |
| Depth | NOAA ERDDAP `ETOPO_2022_v1_15s` | A7 lists GEBCO (not for navigation); **ETOPO is not in A7** | A (B unknown) | **UNVERIFIED** |
| Waves, wind | Open-Meteo Marine and Forecast | prototype only; **not commercial without a paid plan** | **A only** | per A7; disabled under route B |
| Land | Natural Earth | commercial: yes | A, B | per A7 |
| EEZ | Marine Regions | CC-BY, **not a legal line** | A, B | per A7; attribution required by the licence name |
| Protected areas | WDPA | **no commercial use**; not loaded this week | A only | not used |
| Fishing activity | Global Fishing Watch | CC BY-NC, **internal back-testing only** | A | **never appears in any API response** |

Attribution: the API returns the credit lines in `Area.attributions` and the ids actually used in
`Spots.attribution_ids`; the UI must display them. The task brief names the Copernicus line "Contains modified
Copernicus Sentinel data" for Sentinel-derived data (A7: chlorophyll from Sentinel-3 OLCI and Copernicus Marine need
attribution). That line is only needed if a Sentinel or Copernicus fetcher is enabled, and its **exact wording and
year must be taken from the Copernicus terms: `text_verified` is `false` until then**. Likewise the wording for
Open-Meteo, Marine Regions and Natural Earth/OSM is **UNVERIFIED**; each is a config entry, so correcting a string
needs no code change.

## 11. Open questions for the owner and risks found

Decisions are also listed in `README.md` section 5. Severity follows `AGENTS.md` section 8; "actor" = who or what
creates the precondition.

### Interpretations I made (please confirm or overrule)

| # | Question | My default | Why it matters |
| --- | --- | --- | --- |
| D6 | A5 says a missing forecast means "send no spot" and also "treat as yellow". | cell is yellow **and** not recommended | the safer reading of "unknown = do not recommend" |
| D7 | Area-level sea state: worst cell, or something nearer the user's route? | worst level over water cells, plus `share_*` | one red corner turns the headline red; no ports or routes exist yet to do better |
| D8 | Rounding: `fsi` is an integer in the API (the UI shows an integer), stored as real. | integer out, real in the table | back-testing keeps full precision |
| D9 | `depth` has no `observed_at` (static grid). | `null`, `source_id` is the evidence | its `age_days` is always `null`, never a false 0 |

### Risks and findings (not fixed here; this is design only)

| ID | Severity | Finding | Evidence | Actor / precondition |
| --- | --- | --- | --- | --- |
| R1 | **Medium** | Plan item 6 makes the front end fall back to the in-browser path when the API fails. That path has no land, EEZ or sea-state filter (B3), so during an outage the UI would show unfiltered "spots" while the API's whole purpose is that filter. | REPORTED from `TASK.md` 4.1 item 6 and B3; code read, not run | needs an API outage or misconfigured URL; any visitor sees it. Mitigation in section 8 (fallback only on network/5xx, labelled "demo, not filtered") |
| R2 | Medium | The prototype scores a cell with no SST (it sets the SST score to 0 and zero weight, the other factors still produce a number: `computeFsi` in `src/services/marine-data.js:31-56`). The spec says no score. Moving to the server changes visible behaviour: some demo spots will lose their FSI. | code read, not run (READ 2026-11-26) | normal use when ERDDAP returns no SST |
| R3 | Low | The spacing rule "at least 5 km apart" (G p.9) does nothing on a 0.05 degree grid: neighbouring cell centres are 5.56 km apart in latitude and 5.43 km in longitude at 12.5 degrees north (0.05 x 111.32 x cos 12.5 degrees), so the top 5 may be five adjacent cells. | MEASURED 2026-11-26 by arithmetic, not from data | design; use `min_spacing_km` of 10-15 or a minimum cell gap (owner choice, config) |
| R4 | Low (caught) | Computing the cell id with floating point is wrong on cell edges: `(12.3 + 90) / 0.05 = 2045.9999999999998`; 170 of 3000 latitudes (0.00 to 29.99 step 0.01) landed in the wrong row. The scheme in the schema uses integer 1e-4 degree arithmetic and has test vectors. | MEASURED 2026-11-26, Python 3.12, script run locally | any implementer using `floor((lat + 90) / 0.05)` |
| R5 | Medium, UNVERIFIED | Open-Meteo marine data may have no value (or a coarser grid) for near-shore cells, in which case many Chonburi cells would be `forecast_missing`, and the demo could often return `no_eligible_cells`. Not checked: no network calls this session. | UNVERIFIED; settle by one dry run of the fetcher on the bbox before Monday | depends on the upstream grid |
| R6 | Medium | The "no data, no recommendation" and missing-forecast rules mean a dead or lagging upstream shrinks the answer to "nothing". That is correct for safety but looks like a bug in a demo. `/freshness` and `status_detail` exist to explain it; the demo script should show it on purpose. | design | upstream outage, cloud cover |
| R7 | Low | `run_date` is the area-local date; ingest products are dated in UTC (MUR analysis ~09:00 UTC). A run at 03:00 local is 20:00 UTC the previous day. `age_days` is defined by local dates to stay consistent, but a mistake here shifts ages by one day and therefore the freshness weights. | design, covered by a section 2 rule | implementer error |
| R8 | Medium | Legal layers are incomplete for the demo area. With policy `label`, a spot can lie in a closed season or protected zone the system does not know about; the label is the only guard. G p.14 names recommending a forbidden zone as a main risk. | `TASK.md` open question 3 | any user ignoring the label |
| R9 | Low | Chlorophyll (VIIRS) and depth (ETOPO) fetchers are not in the A7 licence table; wording of every attribution is unverified. Fine for route A prototypes, not to be assumed for B. | A7 read; sources not opened | switching to route B |
| R10 | Low, UNVERIFIED | Free-tier hosting (Supabase and the FastAPI host) may pause or cold-start after inactivity, which would make the demo's first request slow or fail. I did not confirm each provider's current policy. | UNVERIFIED | owner's hosting choice |
| R11 | Low | Public unauthenticated API with CORS limited to the front end's origin does not stop other clients; it only returns public aggregate data, bounded per `(area, date)`. Rate limiting depends on the host. | design | anyone on the internet |
| R12 | Medium | Weights in the S example config (0.20, 0.20, 0.25, 0.15, 0.10, 0.10) differ from the prototype's (1.5, 1.5, 1, 0.5, 0.5; no front factor). Both are untuned. The UI's FSI numbers will change when the server takes over; any screen text implying continuity would be wrong. | code read, ARCHITECTURE.md A2 | normal |

### Not covered by this design

Official warnings, thunderstorm rule, closed seasons, protected zones, boat-class zones, ports, routes and fuel,
tides, the 7-day outlook, user data, authentication, and anything about message delivery. The `caveats` array carries
the ones that affect a spot's meaning so the UI cannot forget them.

## 12. Contract tests the implementation must have (each must be shown to go red by removing its guard)

1. A cell with no SST in `grid_daily` yields `fsi: null` in any response that shows cells, and is absent from `spots`.
2. A spot never has `sea_state.level = "red"`; raise a cell's wave above `wave_red_m` and it disappears.
3. A cell with `protected_ok = false` (or `eez_ok` not true, or land) is never in `spots`; the database rejects the
   `recommendations` row on its own (mutation: drop the foreign key, the app test must still catch it, and the
   reverse).
4. In a `trial` area no spot has `confidence = "high"`.
5. `cell_id` for the test vectors in `db/schema.sql` equals the values listed there in both the Python function and
   `pelago.cell_id()`.
6. `date` in the future, `date=2026-02-30`, `limit=0`, `limit=6`, an unknown `boat_class` and an unknown query
   parameter each return `422` with the right `errors[].code`.
7. NaN and Infinity in an ingested value are rejected, never stored as 0 and never returned.
8. Same inputs give the same `ETag`; `If-None-Match` returns `304`.
9. Every response timestamp ends with `Z`; every `position` has at most 4 decimals.
10. With the area policy `withhold` and incomplete legal layers, status is `withheld_legal_incomplete` and `spots`
    is empty.
11. With route `B`, the Open-Meteo fetcher is not enabled and `wave_wind` degrades to `never` rather than being
    replaced silently.
