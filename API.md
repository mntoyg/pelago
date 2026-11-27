# API.md — interfaces of Pelago Asia

Status: skeleton written 2026-11-27 by the PM. **No public API is deployed yet.** The HTTP API is designed and not built (Codex item CX-2 in
`TASK.md` section 4.3). The full design, with field tables and examples, is [`backend/API_CONTRACT.md`](backend/API_CONTRACT.md); this file does
not repeat it, so the two cannot drift apart.

## 1. HTTP API (designed, not built)

All endpoints are `GET`, read-only, JSON, versioned under `/v1`. The contract defines errors, caching headers, CORS and rate limits.

| Endpoint | Purpose | Status |
| --- | --- | --- |
| `/v1/health` | liveness and database reachability | designed |
| `/v1/areas` | list areas | designed |
| `/v1/areas/{area_id}` | one area: bbox, boat classes, legal status | designed |
| `/v1/areas/{area_id}/spots` | the 1 to 5 recommended spots for a date and boat class | designed |
| `/v1/areas/{area_id}/freshness` | per-source and per-job data age | designed |
| `/v1/areas/{area_id}/cells`, `/v1/areas/{area_id}/outlook` | reserved | not planned this week |

Auth: none for these read-only endpoints in the demo (decision in the contract, section 2.2). Example request and response: `backend/API_CONTRACT.md`
section 4.7 (illustrative values, not real data).

## 2. Command-line entry points (built; run from the `backend/` folder)

Taken from `backend/README.md` and exercised by the reviews in `TASK.md` section 7. Environment variable names only; values never go in the repository.

| Command | Purpose | Needs |
| --- | --- | --- |
| `python -m ingest.run --area th-chonburi-coast --date today` | fetch the public sources onto the grid | `DATABASE_URL_INGEST` (write role), network |
| `python -m fsi.run --area th-chonburi-coast --date YYYY-MM-DD` | compute FSI v1 for a stored day | `DATABASE_URL_INGEST` |
| `python -m compute.run --area th-chonburi-coast --date YYYY-MM-DD` | mask, then FSI, then pick, with a `job_runs` row per step | `DATABASE_URL_INGEST`; the EEZ layer from `masks/fetch_eez.py` |
| `python -I masks/fetch_eez.py --bbox 100.7 12.2 101.2 13.2 --out-dir config/layers/th-chonburi-coast` | fetch the EEZ layer at build time | network (Marine Regions, CC BY 4.0) |
| `python -m backtest.run --area th-chonburi-coast --end YYYY-MM-DD --count 52 --cache-dir <outside the repo> --out report.md` | coverage and sanity back-test | network, a cache folder outside the repository |
| `python -m pytest -q` | the test suite; database tests need `PELAGO_TEST_ADMIN_URL` (and `PELAGO_REQUIRE_DB=1` to fail instead of skip) | a throwaway PostGIS |

Known problem on the date of writing: the back-test client does not yet work against the host allowlist added in `fix/backend-hygiene`
(`TASK.md`, REVIEW-005, F-20); that branch is not merged.

## 3. External services the project calls (not ours)

NASA GIBS (map tiles), Esri (base map), NOAA ERDDAP (temperature, chlorophyll, depth), Open-Meteo (waves and wind, non-commercial plan), Marine
Regions (EEZ polygons, fetched at build time). Licences and attribution are in `backend/API_CONTRACT.md` section 10 and
`backend/config/layers/th-chonburi-coast/PROVENANCE.md`.

## 4. Front-end functions

The page calls its own functions through inline handlers listed in `src/main.js` (`AGENTS.md` section 5); they are not a public interface.
