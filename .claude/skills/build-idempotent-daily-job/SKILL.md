---
name: build-idempotent-daily-job
description: Add and verify an area/date-scoped daily pipeline runner with safe retries, completion checks, and explicit unavailable-stage records.
---

# Build an idempotent daily job

## When to use

Use when adding a scheduled backend pipeline that must recover after partial failure and must not write duplicate results on a completed rerun.

## Preconditions

- Read `ARCHITECTURE.md`, `TASK.md`, and the existing ingest/compute pipeline and `job_runs` schema.
- Keep scheduling configuration outside the repository until the owner chooses a host.
- Use an isolated branch/worktree and disposable PostGIS for database integration tests.

## Steps

1. Confirm every scheduled stage and its existing pipeline entry point before creating a wrapper.
2. Make stage order explicit. A failed stage must stop downstream stages; preserve existing transactional writes.
3. Define completion from the latest successful per-stage records and the configuration identity. Failed or incomplete attempts must be retryable.
4. Record unavailable optional stages explicitly as `skipped` with a machine-readable reason.
5. Inject a stage failure, assert downstream stages and recommendation writes do not occur, then retry and assert recovery.
6. Snapshot relevant tables, rerun a completed area/date, and assert both counts and stage calls are unchanged.
7. Mutate the failure and completion guards on a copy; expect red assertions and verify the original file hash is restored.
8. Document the host command and the environment-variable name only; never put credentials in source or logs.

## Verify

Run targeted and full backend pytest suites with PostGIS explicitly required (`PELAGO_REQUIRE_DB=1`). Confirm zero database skips, CLI failure output contains no DSN/raw exception, and run `git diff --check`.

## Pitfalls

- A mocked stage test alone does not prove SQL state, recovery, or idempotence; use a database-backed orchestration test.
- Do not treat a partially completed date as complete; compare ingest and compute completion timestamps.
- Do not configure a scheduler or commit credentials before the owner selects a deployment host.

## Provenance

Verified in Pelago Asia on 2026-11-27. Evidence: `backend/tests/test_jobs_db.py`, `backend/docs/daily-job-mutation-log.md`, and 383 passing backend tests on PostGIS 16-3.7. Live NOAA fetching and deployed scheduling remain unverified.
