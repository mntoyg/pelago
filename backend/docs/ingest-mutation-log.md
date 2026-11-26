# Ingest: mutation checks of the guards (AGENTS.md section 7, rule 5)

**MEASURED 2026-11-26** on the commit that adds this file's parent change (`feature/backend-ingest`). For each guard the line was
removed (or replaced) in the source file, the named tests were run, the file was restored from a saved copy, and the file's
SHA-256 (first 16 hex digits) was recorded before and after. "RED" means at least one test failed, so the test can fail.
Two single-guard mutations stayed green (M11, M26) because a second, independent guard refuses the same input; they are
covered by the combined mutations M30 and M31, which went red.

Run the suite: from `backend/`, `..\.venv\Scripts\python -m pytest -q` (the database round trip is skipped unless
`PELAGO_TEST_ADMIN_URL` points at a throwaway PostgreSQL; `PELAGO_REQUIRE_DB=1` turns the skip into a failure).

| ID | Guard removed | Result | SHA before | SHA after |
| --- | --- | --- | --- | --- |
| M01 | cell_id integer arithmetic -> float floor | RED (4 failed) e.g. test_vectors[12.3-100.7-14736814-centre1] | `96d43780dbe64ab7` | `96d43780dbe64ab7` |
| M02 | cell_id range check removed | RED (4 failed) e.g. test_out_of_range_or_not_a_number_is_rejected[90-0] | `96d43780dbe64ab7` | `96d43780dbe64ab7` |
| M03 | non-finite coordinate guard removed | RED (3 failed) e.g. test_out_of_range_or_not_a_number_is_rejected[nan-0] | `96d43780dbe64ab7` | `96d43780dbe64ab7` |
| M04 | finite() lets NaN/Inf through | RED (4 failed) e.g. test_all_missing_gives_no_result_never_zero | `c0d3f838b39b05f9` | `c0d3f838b39b05f9` |
| M05 | min_valid_fraction ignored | RED (2 failed) e.g. test_min_valid_fraction_is_enforced_at_the_boundary | `c0d3f838b39b05f9` | `c0d3f838b39b05f9` |
| M06 | window_max accepts a partial window | RED (1 failed) e.g. test_window_max_needs_every_hour_present_and_finite | `c0d3f838b39b05f9` | `c0d3f838b39b05f9` |
| M07 | nearest_assign ignores max_km | RED (2 failed) e.g. test_nearest_assign_snaps_within_range_and_leaves_none_beyond | `c0d3f838b39b05f9` | `c0d3f838b39b05f9` |
| M08 | sea window with a fixed +7h offset | RED (1 failed) e.g. test_sea_window_uses_the_zone_database_not_a_fixed_offset | `89482849383a5326` | `89482849383a5326` |
| M09 | local_today uses the UTC date | RED (1 failed) e.g. test_local_today_differs_from_the_utc_date_after_17h_utc | `89482849383a5326` | `89482849383a5326` |
| M10 | range check removed from validate_rows | RED (2 failed) e.g. test_out_of_range_or_non_finite_values_never_reach_the_writer[41.0] | `ea8f73c8c908eddf` | `ea8f73c8c908eddf` |
| M11 | isfinite check removed from validate_rows | GREEN (second guard covers it, see M30/M31) | `ea8f73c8c908eddf` | `ea8f73c8c908eddf` |
| M12 | cell-set check removed from validate_rows | RED (1 failed) e.g. test_duplicate_missing_or_foreign_cells_and_naive_times_are_rejected | `ea8f73c8c908eddf` | `ea8f73c8c908eddf` |
| M13 | crash text stored as error_code | RED (1 failed) e.g. test_job_runs_never_hold_urls_or_secrets | `ea8f73c8c908eddf` | `ea8f73c8c908eddf` |
| M14 | FetchError code sanitiser removed | RED (2 failed) e.g. test_job_runs_never_hold_urls_or_secrets | `6015f3ccf6434b02` | `6015f3ccf6434b02` |
| M15 | writer error_code sanitiser removed | RED (1 failed) e.g. test_the_database_itself_rejects_what_the_ingest_must_never_send | `ce7fcb38004d6686` | `ce7fcb38004d6686` |
| M16 | pipeline carry-forward guard removed | RED (1 failed) e.g. test_wave_wind_is_never_carried_forward | `ea8f73c8c908eddf` | `ea8f73c8c908eddf` |
| M17 | db latest_before wave/wind guard removed | RED (1 failed) e.g. test_carry_forward_reads_yesterday_from_the_database | `ce7fcb38004d6686` | `ce7fcb38004d6686` |
| M18 | licence route check removed | RED (2 failed) e.g. test_open_meteo_is_refused_on_licence_route_b | `00081f1005cd1c40` | `00081f1005cd1c40` |
| M19 | Open-Meteo GMT guard removed | RED (1 failed) e.g. test_open_meteo_response_not_in_gmt_is_refused | `9fc656886ee06272` | `9fc656886ee06272` |
| M20 | rectangle check of SST grid removed | RED (1 failed) e.g. test_mur_truncated_or_reordered_response_is_bad_shape | `4cb915f160d22256` | `4cb915f160d22256` |
| M21 | retries reduced to 1 | RED (2 failed) e.g. test_primary_is_retried_three_times_then_the_fallback_is_used | `ea8f73c8c908eddf` | `ea8f73c8c908eddf` |
| M22 | missing SST written as 0 | RED (2 failed) e.g. test_round_trip_writes_the_grid_with_nulls_not_zeros | `ce7fcb38004d6686` | `ce7fcb38004d6686` |
| M23 | https-only check removed | RED (1 failed) e.g. test_http_errors_become_short_codes_without_url_or_text | `6015f3ccf6434b02` | `6015f3ccf6434b02` |
| M24 | response size cap removed | RED (1 failed) e.g. test_oversized_response_is_cut_off | `6015f3ccf6434b02` | `6015f3ccf6434b02` |
| M25 | config secret scan removed | RED (5 failed) e.g. test_a_secret_in_the_config_is_refused[https://user:pw@host/x] | `a9eeec6c650151ea` | `a9eeec6c650151ea` |
| M26 | area_id path-traversal check removed | GREEN (second guard covers it, see M30/M31) | `a9eeec6c650151ea` | `a9eeec6c650151ea` |
| M27 | per-area-date lock check removed | RED (1 failed) e.g. test_a_second_ingest_for_the_same_area_and_date_is_refused | `ea8f73c8c908eddf` | `ea8f73c8c908eddf` |
| M28 | chl newest-day rule reversed (oldest wins) | RED (1 failed) e.g. test_chl_takes_the_newest_valid_day_per_cell | `89174c67cc98e4e7` | `89174c67cc98e4e7` |
| M29 | pick_times ignores the end of the local run date | RED (1 failed) e.g. test_pick_times_by_local_date_and_lookback | `5a5dfb418b4395d0` | `5a5dfb418b4395d0` |
| M30 | range check AND isfinite check both removed | RED (5 failed) e.g. test_out_of_range_or_non_finite_values_never_reach_the_writer[nan] | `ea8f73c8c908eddf` | `ea8f73c8c908eddf` |
| M31 | traversal check AND area_id mismatch check both removed | RED (1 failed) e.g. test_traversal_to_an_existing_config_outside_the_directory_is_refused | `a9eeec6c650151ea` | `a9eeec6c650151ea` |
