# Back-test harness: mutation log (guards proven able to fail)

MEASURED 2026-11-26 on branch `feature/backtest`, worktree `pelago-fsi/backend`; `backtest.__file__` printed as
`D:/Hackathon/CodeAgis 2026/pelago-fsi/backend/backtest/__init__.py`. Same method as `fsi-mutation-log.md`: saved copy, hash before,
edit, run `tests/test_backtest.py`, restore from the copy, hash after. Control: 19 passed in 0.64s.

| Mutation | File | Hash before | Hash after | Failing tests | First failing test |
| --- | --- | --- | --- | --- | --- |
| B01 hit rate: trips at the median count as good | `backtest/checks.py` | 99cb97152b443cfc | 99cb97152b443cfc | 3 | `test_hit_rate_synthetic_matches_a_hand_count` |
| B02 top set excludes ties at the threshold | `backtest/checks.py` | 99cb97152b443cfc | 99cb97152b443cfc | 1 | `test_top_set_includes_ties_and_overlap` |
| B03 request cap off by one | `backtest/inputs.py` | 638bbde9d4d1dbfe | 638bbde9d4d1dbfe | 2 | `test_request_cap_is_enforced_before_the_request_is_made` |
| B04 pause between requests not kept | `backtest/inputs.py` | 638bbde9d4d1dbfe | 638bbde9d4d1dbfe | 1 | `test_pause_between_requests_is_kept` |
| B05 cache inside the repository allowed | `backtest/inputs.py` | 638bbde9d4d1dbfe | 638bbde9d4d1dbfe | 2 | `test_cache_must_be_outside_the_repository` |
| B06 transient failures cached and scored | `backtest/inputs.py` | 638bbde9d4d1dbfe | 638bbde9d4d1dbfe | 1 | `test_load_history_caches_stops_at_the_cap_and_leaves_out_transient_fai` |
| B07 spearman of a constant reported as a number | `backtest/checks.py` | 99cb97152b443cfc | 99cb97152b443cfc | 2 | `test_spearman_known_values` |
| B08 sensitivity runs a zero SST weight | `backtest/checks.py` | 99cb97152b443cfc | 99cb97152b443cfc | 1 | `test_sensitivity_to_an_unchanged_weight_is_zero_and_to_a_removed_input` |
| B09 dates not spread for an early stop | `backtest/inputs.py` | 638bbde9d4d1dbfe | 638bbde9d4d1dbfe | 1 | `test_weekly_dates_are_spread_so_stopping_early_still_covers_the_year` |
| B10 report without the not-accuracy header | `backtest/report.py` | 6045a99a0a41e3ae | 6045a99a0a41e3ae | 1 | `test_end_to_end_offline_report_says_it_is_not_evidence_of_accuracy` |

All data in these tests is SYNTHETIC. They prove the harness computes what it says; they say nothing about accuracy.
