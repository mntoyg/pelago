# CX-2 API Guard Mutation Log

Date: 2026-11-27. Branch: `feature/backend-api`.

Each mutation was applied to a saved byte copy of the source file, the targeted pytest command was expected to fail,
and a `finally` block restored the exact bytes. SHA-256 before and after each mutation matched. The first ten mutations
used source hash `ad065b0200e700d7f43968598dc67a5e2f48a85d352922ba5e1abddb4300b423`; the ETag mutation used
`2aa2164102846ff30ea40cd0a5cfe02a4df918db2ebdb8c158b0585d8fa4ad5d`.
The confidence-source mutation used `backend/api/repository.py` hash
`fec482cfcbded95d6b4737e9fc60593bb41ca89d29702a9a631abf5767aee9b3`.

| Guard removed | Targeted test | Result |
| --- | --- | --- |
| SST required | `tests/test_api_spot_guards.py -k never_returns` | RED on missing-SST case |
| FSI required (omit FSI from finite-value checks and remove explicit null guard) | same | RED on null-FSI case |
| Eligibility required | same | RED on ineligible case |
| Forecast required | same | RED on missing-forecast case |
| Red sea state excluded | same | RED on red-state case |
| False legal flags excluded | same | RED on each false legal-flag case |
| Trial confidence cap | same | RED on trial/high-confidence case |
| Incomplete legal layer with `withhold` | `tests/test_api_spot_guards.py::test_withhold_policy_hides_incomplete_legal_rows` | RED |
| Minimum spacing | `tests/test_api_spot_guards.py::test_api_rechecks_spacing_instead_of_trusting_pick_rows` | RED |
| Observation age comes from the stored timestamp | `tests/test_db_roundtrip.py::test_api_reads_real_postgis_without_write_privileges` with `PELAGO_REQUIRE_DB=1` | RED on age mismatch against seeded PostGIS row |
| ETag binds to the response body | `tests/test_api_http.py::test_etag_changes_when_the_response_body_changes` | RED when ETag was constant |
| Confidence comes from `fsi_daily`, not the recommendation copy | `tests/test_db_roundtrip.py::test_api_reads_real_postgis_without_write_privileges` | RED when SQL selected `recommendations.confidence`; seeded FSI `medium` and recommendation copy `low` |

All 12 mutations failed their targeted test as expected and restored the saved file hash. Existing PostGIS tests also
assert that the schema rejects recommendations for forbidden cells and unscored FSI rows. These API mutations exercise
the response-boundary guards independently of those database constraints.
