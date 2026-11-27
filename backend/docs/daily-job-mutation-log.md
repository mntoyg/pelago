# Daily job runner mutation log

Measured on 2026-11-27 in the `feature/daily-job` worktree, against disposable PostGIS 16-3.7. Mutations were applied to an in-memory copy of `backend/jobs/run_daily.py`; the checked-out source was not changed by the mutation harness.

Base SHA-256 of `backend/jobs/run_daily.py`: `a11d5f51c82cbe442f6511e3d344e8d3997711cd6605b9016e1855fab1a5267e`.

| Guard mutated | Mutation | Expected red assertion | Result |
| --- | --- | --- | --- |
| Ingest failure gate | Replace `if failed_ingest:` with `if False:` | `test_daily_runner_retries_after_failure_then_skips_a_completed_rerun` expects compute not to run and no recommendation to be written after failed ingest | RED; original source hash restored and matched |
| Completion/idempotence gate | Replace `if completed:` with `if False:` | Same integration test expects the completed rerun to leave job/data row counts unchanged and not call ingest/compute again | RED; original source hash restored and matched |

Both mutation tests exited non-zero on the named regression assertions, not on syntax/import errors. The unmutated targeted suite subsequently passed with PostGIS required. These tests inject ingest/compute results; live NOAA fetching and a host scheduler were not exercised.
