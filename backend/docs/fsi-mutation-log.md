# FSI v1: mutation log (guards proven able to fail)

MEASURED 2026-11-26 on branch `feature/fsi-v1` (base commit `554cd53` plus one added test), worktree `pelago-fsi/backend`,
`fsi.__file__` printed as `D:/Hackathon/CodeAgis 2026/pelago-fsi/backend/fsi/__init__.py` (the tree under test is this one).

Method: for each row the file was copied to a saved copy, its SHA-256 (first 16 hex) recorded, the edit applied, the three FSI
test files run (`tests/test_fsi_model.py`, `test_fsi_config.py`, `test_fsi_db.py`; database tests with `PELAGO_REQUIRE_DB=1` against a
throwaway `postgis/postgis:16-3.7`), then the file restored from the saved copy and the hash recorded again. A mutation that leaves
the suite green means the guard is NOT proven; M07 was green on the first run, so the test `test_freshness_enters_numerator_and_denominator`
was added and M07 re-run (red). Control (no mutation): 94 passed on the first run, 95 after the added test.

| Mutation | File | Hash before | Hash after | Failing tests | First failing test |
| --- | --- | --- | --- | --- | --- |
| M01 missing SST scored as 0 degC | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 15 | `test_no_sst_means_no_score_even_when_everything_else_is_present` |
| M02 SST/chl age limit not enforced | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 2 | `test_sst_age_limit_is_inclusive_and_one_day_later_is_expired` |
| M03 future-dated observation accepted | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 1 | `test_observation_after_the_end_of_the_local_run_date_is_not_used` |
| M04 chlorophyll <= 0 accepted | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 1 | `test_chlorophyll_that_cannot_be_real_is_invalid_and_not_scored[0.0]` |
| M05 bloom cut removed | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 1 | `test_bloom_is_cut_to_zero_above_the_threshold_only` |
| M06 zero-denominator guard removed | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 1 | `test_zero_total_weight_gives_no_score_instead_of_dividing_by_zero` |
| M07 weights normalised without freshness | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 1 | `test_freshness_enters_numerator_and_denominator` |
| M08 missing chlorophyll scored as 0 | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 10 | `test_missing_chlorophyll_is_excluded_not_scored_as_zero` |
| M09 verification level not fail-closed | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 3 | `test_confidence_is_capped_until_the_area_is_verified[None-medium-no_ve` |
| M10 trial area may reach high | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 15 | `test_full_cell_matches_the_formula_computed_by_hand` |
| M11 medium without chlorophyll | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 3 | `test_missing_chlorophyll_is_excluded_not_scored_as_zero` |
| M12 medium with stale SST | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 2 | `test_stale_sst_lowers_freshness_and_confidence` |
| M13 front percentile without min cells | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 1 | `test_front_needs_enough_cells_in_the_area` |
| M14 front ranks land-proxy cells too | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 2 | `test_front_percentile_only_ranks_cells_with_a_depth_value` |
| M15 8-day freshness constant 8 -> 3 | `fsi/config.py` | ef57d7369cf53bb2 | ef57d7369cf53bb2 | 1 | `test_eight_day_composite_is_fresh_for_eight_days` |
| M16 freshness does not decay | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 1 | `test_stale_sst_lowers_freshness_and_confidence` |
| M17 naive timestamp accepted | `fsi/model.py` | 534065cf8baa0cdf | 534065cf8baa0cdf | 1 | `test_naive_timestamp_is_invalid` |
| M18 writer stores 0 for a missing sub-score | `fsi/db.py` | 7c923d6a2e5bffda | 7c923d6a2e5bffda | 9 | `test_run_writes_scores_nulls_and_the_cap` |
| M19 precheck: unscored pick not detected | `fsi/db.py` | 7c923d6a2e5bffda | 7c923d6a2e5bffda | 1 | `test_losing_the_sst_of_a_picked_cell_fails_the_run_and_keeps_everythin` |
| M20 precheck: changed pick not detected | `fsi/db.py` | 7c923d6a2e5bffda | 7c923d6a2e5bffda | 1 | `test_a_changed_score_under_a_stored_pick_is_also_a_conflict` |
| M21 config: negative weight accepted | `ingest/config.py` | d302820cba76ee4e | d302820cba76ee4e | 2 | `test_validate_fsi_refuses[negative` |
| M22 config: bool counts as a number | `ingest/config.py` | d302820cba76ee4e | d302820cba76ee4e | 1 | `test_validate_fsi_refuses[bool` |
| M23 config: NaN/Inf accepted | `ingest/config.py` | d302820cba76ee4e | d302820cba76ee4e | 2 | `test_validate_fsi_refuses[nan` |
| M24 config: weight sum 0 accepted | `ingest/config.py` | d302820cba76ee4e | d302820cba76ee4e | 1 | `test_validate_fsi_refuses[weights` |
| M25 config: unknown weight key accepted | `ingest/config.py` | d302820cba76ee4e | d302820cba76ee4e | 2 | `test_validate_fsi_refuses[unknown` |
| M26 config: weights.sst = 0 accepted | `fsi/config.py` | ef57d7369cf53bb2 | ef57d7369cf53bb2 | 1 | `test_sst_weight_zero_is_refused_by_params` |
| M27 config: age limits not checked | `fsi/config.py` | ef57d7369cf53bb2 | ef57d7369cf53bb2 | 1 | `test_age_limits_are_checked[bad0]` |
| M28 config: fsi block not validated by the loader | `ingest/config.py` | d302820cba76ee4e | d302820cba76ee4e | 1 | `test_fsi_block_is_checked_by_the_area_loader` |

Double guards found while doing this: the schema CHECK `(fsi IS NULL) = (s_sst IS NULL)` also refuses a writer that stores 0 for a missing
sub-score (M18 turns red because the run then fails with `write_failed`; the test also asserts the stored NULLs directly).
`effective_level()` and the membership test in `score_cell` say the same thing twice, so M09 mutates the membership test, not the helper.
M01, M08 and M10 fail many tests because those guards sit under many scenarios.

Not mutated: the `.gitattributes` line (no test can fail on it), the advisory lock, `AttemptLimit`, the CLI exit codes.
