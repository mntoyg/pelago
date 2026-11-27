---
name: build-readonly-fastapi-api
description: Add and verify a small read-only FastAPI service backed by PostgreSQL/PostGIS in an existing Python project.
---

# Build a Read-Only FastAPI API

## When to use
Use when adding HTTP read endpoints to a Python application with an existing PostgreSQL/PostGIS schema and a strict no-write boundary.

## Preconditions
- Read the project API contract, database schema, architecture map, and agent rules.
- Confirm the expected environment variable and exact database role; do not print the connection URL.
- Pin and audit dependencies before installing them into the project's virtual environment.
- Use a disposable PostGIS database for integration tests.

## Steps
1. Separate HTTP validation/serialization from a repository adapter; parameterize all SQL.
2. Set `default_transaction_read_only=on` for every API database connection and keep the URL in the process environment.
3. Fail closed on missing/invalid inputs and recheck critical recommendation invariants at the response boundary.
4. Return safe RFC 9457 problem responses; never include exception text, SQL, or tracebacks.
5. Set explicit CORS origins, bounded request/query sizes, a bounded per-process rate limiter, ETag and cache headers, and request IDs.
6. Use `httpx.ASGITransport` for async in-process HTTP tests when the host's socket policy blocks `TestClient` socket pairs.
7. Seed an isolated PostGIS database and call each repository query and HTTP route. Verify writes fail under the read-only transaction.
8. Mutate each safety guard from a saved copy, confirm the targeted test fails for the expected reason, restore the file, and compare hashes.
9. Document local run/test commands and limitations. Disable Uvicorn access logs for this prototype.

## Verify
From `backend/`, run `python -m pytest -q` with `PELAGO_TEST_ADMIN_URL` pointing to disposable PostGIS and `PELAGO_REQUIRE_DB=1`. Also run `python -m compileall -q api tests` and `git diff --check`.

## Pitfalls
- An unbounded set of client IP buckets can grow without limit even when old windows are pruned; enforce a hard key cap.
- A read-only transaction test proves session-level protection, not that a deployed service credential has least-privilege grants.
- Data source attribution and legal-layer completeness must remain explicit product limitations until verified.

## Provenance
Verified in the Pelago Asia CX-2 implementation on 2026-11-27: full backend suite passed with 416 tests and no database skips. Deployment credentials, public deployment, and provider attribution terms remain unverified.
