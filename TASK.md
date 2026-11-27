# TASK.md — Pelago Asia work board

Owned by the PM seat. Rules for everyone are in [`AGENTS.md`](AGENTS.md). Last updated: **2026-11-26**.
Items marked **PROPOSED** are the PM's suggestions and are not agreed scope until the owner says so.

## 1. Snapshot

| Item | Value |
| --- | --- |
| Owner fork (`origin`) | https://github.com/mntoyg/pelago |
| Teammate's original (`upstream`) | https://github.com/orapin67855-coder/pelago (we never push here) |
| `main` | equals `origin/main` (check with `git ls-remote origin main`); moves only with the owner's go-ahead. On 2026-11-26 it was fast-forwarded from `db85230` through the refactor, the agent guides, and `ARCHITECTURE.md` + `README.md` |
| `refactor/frontend-structure`, `docs/agent-guides`, `docs/readme-architecture` | all **merged into `main`** (the refactor branch is also kept on `origin`) |
| Stack | static HTML/CSS/vanilla ES modules, no build, deployed as-is on Vercel |
| Data | all FSI values and spots are DEMO DATA; live inputs are NOAA ERDDAP, NASA GIBS, Esri, Open-Meteo |
| Team focus | backend and AI (front end is kept stable) |

## 2. Seats

| Seat | Chat | Status |
| --- | --- | --- |
| Owner | `mntoyg` | decides scope, merges, pushes to `main` |
| PM | "PM" chat | active |
| SWE 01 | "Pelago SWE 01" | idle; delivered TASK-002 |
| Backend, AI (Claude seats) | done: contract/schema, ingest, FSI + back-test | idle |
| Mask and pick seat | "Land/EEZ mask and pick step", started 2026-11-26 | **finished its build and stopped** (the owner's hold arrived after it had pushed). Branch `feature/mask-and-pick` = `3a357a2`, **not reviewed by the PM, not merged** (TASK-010) |
| Codex (backend + AI) | one chair, work package in section 4.3 | assigned 2026-11-26, not started |

## 3. Done

| ID | What | Evidence |
| --- | --- | --- |
| TASK-000 | Forked `orapin67855-coder/pelago` to `mntoyg/pelago`, cloned, set `origin` and `upstream` | MEASURED 2026-11-26: `git remote -v`, GitHub shows `isFork: true` |
| TASK-001 | Fixed `index.html` asset paths (`css/styles.css`, `js/app.js` did not exist, so the page had no styles or script) | MEASURED 2026-11-26: after the fix `styles.css` and `app.js` return 200 and the page renders. Pushed as `db85230` |
| TASK-002 | Front-end restructure by SWE 01: `app.js` split into `src/` ES modules, `styles.css` sectioned with CSS variables, README structure section. UI and features unchanged | Reviewed by the PM, see REVIEW-001. Merged into `main` at `86519dd` (fast-forward, pushed to `origin`, MEASURED 2026-11-26: `git ls-remote origin main` = `86519dd`) |
| TASK-006 | `ARCHITECTURE.md` and a new `README.md` from the team's three reference documents (build guide 2026-11-21, function spec 2026-11-24, data sources 2026-11-25), plus a gap analysis of this prototype against them | MEASURED 2026-11-26: the PM read all three documents, including the two figures that have no text layer (system layers, 5-phase plan), and checked each statement about the prototype against the code. While doing so it found and fixed two wrong lines the PM had written earlier in `AGENTS.md` and `TASK.md`: the catch journal does not save anything (only price reports and pins are saved in `localStorage`). Merged into `main` on 2026-11-26 |
| TASK-007 | Backend API contract, draft PostGIS schema and service layout (design only) by the first backend seat | Reviewed by the PM, see REVIEW-002. Merged into `main` on 2026-11-26 (fast-forward from `feature/backend-contract` `93b82e0`). Root `.gitignore` now ignores `.env*` and key files; new `.vercelignore` keeps `backend/` and env files out of CLI deploys |
| TASK-008 | Backend daily ingest for `th-chonburi-coast` by the second backend seat: dry run of the public sources, area config, one fetcher per source behind a swappable interface, aggregation onto the 0.05 degree grid, writer, 101 tests, mutation log | Reviewed by the PM, see REVIEW-003. Merged into `main` on 2026-11-26 (fast-forward from `feature/backend-ingest` `73d2f00`, with the PM's review notes) |
| TASK-009 | FSI v1 on the server and the first back-test by the AI-engineer seat (Pelago AIE 01): `backend/fsi/`, `backend/backtest/`, strict `fsi` config validation, `.gitattributes` for the config files, 115 more tests, two mutation logs, one report | Reviewed by the PM, see REVIEW-004. Merged into `main` on 2026-11-26 (fast-forward from `feature/backtest` `5e829f5`, which contains `feature/fsi-v1` `baedcde`, plus the PM's review notes) |
| TASK-010 | Land mask, EEZ mask, sea-state rule and pick step by the mask seat: `backend/masks/`, `backend/pick/`, `backend/compute/` (order mask, fsi, pick), `backend/legal.py`, `backend/seastate.py`, 7 test files, `backend/docs/mask-pick-mutation-log.md`, `land.geojson` (Natural Earth 1:10m, public domain, 3.6 KB, clipped) and `PROVENANCE.md` | **Reviewed by the PM, see REVIEW-007: approved for merge; not yet merged (waits for the owner's word).** Branch `feature/mask-and-pick` = `3a357a2` on `origin` (MEASURED 2026-11-26 by the PM: `git ls-remote origin` = `3a357a2`; 2 commits, 29 files, all under `backend/`). The PM has not run the tests or the mutation checks. The EEZ layer (Marine Regions, CC BY 4.0) is **not committed** and is fetched at build time by `backend/masks/fetch_eez.py`; the seat's note says the owner chose build-time download. The PM did not see that approval in this chat: the owner should confirm that the Natural Earth and Marine Regions downloads were approved |
| TASK-011 | Codex work package written into this file (section 4.3) and the mask work put on hold, by the PM | MEASURED 2026-11-26: `main` = `origin/main` = `34ca635` |
| TASK-012 | The owner's nine-file documentation set (Standing Rule 3) and the project skills folder (Rule 4): added `CURSOR.md`, `PRD.md`, `API.md`, `.github/copilot-instructions.md` as short truthful skeletons, linked them from `AGENTS.md`, created `.claude/skills/` with one skill (`review-branch-by-reproduction`) and a local `.codex/skills` junction (ignored by git) | MEASURED 2026-11-27: all nine paths exist and are not empty (`Docs: 9/9`). Not yet merged; the PRD and API files are skeletons the owner should read |

## 4. Next up

### 4.0 Progress checklist (`[x]` = done and checked by the PM, `[ ]` = not done)

Updated 2026-11-26. "Checked" means the PM reproduced the evidence, not only read the seat's report (REVIEW-001 to REVIEW-003).

Foundations

- [x] Fork, clone, remotes (`origin`, `upstream`); asset-path fix (TASK-000, TASK-001)
- [x] Front-end restructure into `src/` modules, UI unchanged (TASK-002, REVIEW-001)
- [x] Agent guides and this board (`AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `TASK.md`)
- [x] `ARCHITECTURE.md` and `README.md` from the three reference documents (TASK-006)
- [x] Owner decisions D1 to D11 recorded (section 6)
- [x] PM answers to the AI-engineer seat's design note (9 points and 3 additions) recorded in REVIEW-004
- [x] Root `.gitignore` ignores `.env*` and key files; `.vercelignore` added

Backend slice for the demo (plan 4.1, deliverables 1 to 7)

- [x] Backend API contract and draft schema (TASK-007, REVIEW-002)
- [x] Schema executed on PostgreSQL 16 + PostGIS 3.7; 42 checks pass; no-SST recommendation gap found and fixed
- [x] Dry run of the public sources with measured coverage (`backend/docs/ingest-dry-run.md`)
- [x] Area config `th-chonburi-coast` (10 km spacing, small and medium boat classes, licence route A)
- [x] Fetchers: SST, chlorophyll (primary plus NOAA-20 fallback, D11), depth, waves and wind; licence-route check
- [x] Aggregation onto the 0.05 degree grid with the integer cell id (Python twin of the SQL function)
- [x] Writer into `grid_daily` and `job_runs`; retry 3 times, fallback, carry-forward with the value's own age
- [x] Ingest tests: 101 pass (reproduced by the PM against a real PostGIS); mutation checks reproduced by the PM (5 of 5 red)
- [ ] Daily scheduler for the ingest (not built)
- [x] Land mask and EEZ mask, and the test "no recommended spot in a forbidden cell" (deliverable 3): built on `feature/mask-and-pick` `3a357a2`, PM-checked 2026-11-27 (REVIEW-007); **not yet merged into `main`**; protected zones, closed seasons, disputed areas and boat-class zones stay unknown (NULL) and the area stays labelled trial
- [x] Pick step (3 to 5 spots, 10 km apart, writes `recommendations`): same branch, PM-checked 2026-11-27, not yet merged
- [x] FSI v1 on the server: six sub-scores, confidence, per-cell explanation (deliverable 4); 216 tests pass (PM run), 10 PM mutations red
- [ ] API (FastAPI) reading the database (deliverable 1)
- [x] Back-test report (deliverable 5): coverage and sanity checks only, **not evidence of accuracy** (no catch logs, no Global Fishing Watch token); 41 of 52 dates
- [ ] Front end reads the API, labelled demo fallback (D9) (deliverable 6)
- [ ] Red-team review pass of the filter and the API (deliverable 7)
- [ ] Deployment: Supabase project and a FastAPI host
- [ ] Demo script and rehearsal

Owner actions and decisions

- [ ] Create the Supabase project (free tier) and two database roles (read-only, write)
- [ ] Create an account on a host for FastAPI
- [ ] Optional: Global Fishing Watch token for the back-test (internal use only)
- [ ] Decide the legal-incomplete policy: label spots "trial" (PM proposal) or show none (open question 3)
- [ ] Confirm the submission date and format (open question 1)
- [ ] Decide how the demo handles empty chlorophyll (open question 12)
- [ ] Tell the teammate who owns `upstream` (TASK-005)

Small fixes found in review, not yet done

- [ ] Root `.gitignore`: add `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/` (F-8)
- [x] `.gitattributes` with `eol=lf` for `backend/config/**/*.json` so `config_sha256` is the same on every machine (F-7; done in `feature/fsi-v1`, new hash `46e87256a902eb47` confirmed by the PM)
- [ ] Use the canonical ERDDAP dataset ids and do not follow redirects blindly (F-9)
- [ ] Fix the two lines that still say "owner may remove it" about the NOAA-20 fallback (D11)
- [ ] Reword `wx_issued_at` in the contract: it is the retrieval time, not a forecast issue time (F-10)
- [ ] Verify the temperature-front input (SST gradient) on one real SST field, because it drives the ranking and was only checked on a synthetic field (F-16)
- [ ] Decide whether the week-to-week change of the spots is acceptable for the demo (open question 13)
- [ ] Optional: more request budget for the 11 missing back-test dates and a daily sample (open question 14)

### 4.1 One-week plan (PROPOSED, for the owner's approval)

Deadline: hackathon submission **within one week of 2026-11-26** (about **2026-12-03**; the exact date is still to be
confirmed). Scope decided by the owner: prototype **plus** a backend/AI core. A week cannot hold the whole of
`ARCHITECTURE.md` Part A, so the plan is a thin vertical slice for **one area**, with everything else labelled as not
built. Proposed demo area: the Chonburi coast (the prototype's own demo spots, about lon 100.7–101.2, lat 12.2–13.2).

What gets demonstrated at the end:

| # | Deliverable | Spec | Notes |
| --- | --- | --- | --- |
| 1 | Backend API (FastAPI) on Supabase PostGIS, deployed online | S: C2, C4, C14 (light) | `GET` spots for an area with FSI, sub-scores, confidence, data age, sea state; a health/freshness endpoint |
| 2 | Daily ingest for the demo area into a 0.05° grid: SST, chlorophyll, depth, waves/wind | S: C2 | Reuse the datasets the prototype already queries (`jplMURSST41`, `nesdisVHNchlaDaily`, `ETOPO_2022_v1_15s`, Open-Meteo); store the data date; retry, then fall back to the latest data with its age |
| 3 | Minimal safety filter: land mask, EEZ with a 5 km buffer, "no data = no recommendation" | S: C3 (part) | Closed seasons and protected zones for the area are **not available** this week; the area is labelled "trial: legal layers incomplete" (see open question 3) |
| 4 | FSI v1 on the server: 6 sub-scores including the temperature front, freshness weights, confidence level, explanation | S: C4 | Replaces `computeFsi` in the browser; same output shape for the UI |
| 5 | Back-test report: FSI over the past 1–2 years, hit-rate method as in G p.12 | G p.12 | Compared with Global Fishing Watch only if the owner provides an API token (internal use only); otherwise coverage and sanity checks only, stated plainly |
| 6 | Front end reads the API (config switch, falls back to today's in-browser path) and shows data age and one confidence rule | front end | Also fixes the two-rule confidence finding (section 5) |
| 7 | Automated tests, a red-team review pass, demo script | `AGENTS.md` §7 | Includes "no recommended spot in a forbidden cell" and mutation checks of the filter tests |

Schedule. The owner's Claude weekly meter is shared by every seat and **resets on Sat 2026-11-28 at 10:00 Thai time**
(it is at 59% today), so the light work goes first and the heavy building starts after the reset:

| Day | Work |
| --- | --- |
| Thu 26 Nov | decisions recorded (this section), plan approved, owner actions below |
| Fri 27 Nov | light: API contract, DB schema, repo layout for `backend/`, test plan (PM + one SWE, small) |
| Sat 28 Nov (after 10:00) | ingest for the demo bbox (SST, chlorophyll, depth, waves/wind) into the grid |
| Sun 29 Nov | land/EEZ masks and the filter tests; FSI v1 on the server |
| Mon 30 Nov | deploy the API and the scheduled ingest; front end reads the API |
| Tue 1 Dec | back-test; red-team review of the filter and the API (separate seat, reproduces everything) |
| Wed 2 Dec | fixes, docs, demo rehearsal, freeze |
| Thu 3 Dec | buffer and submission |

Seats (PROPOSED): **SWE-BE 01** (backend: API, ingest, FSI), **Pelago SWE 01** (front end), a **reviewer** seat for the
red-team pass, and the PM. At most two builders at once, because the weekly meter is shared.

Owner actions (the PM cannot do these for you): create the Supabase project (free tier is enough); create an account on
a host for the FastAPI service (the guide suggests a cloud host; Render or Fly are options); optionally register for a
Global Fishing Watch API token (internal back-testing only, not for display). Keep every key in environment variables
or the host's secret store, never in the repository.

Not in this week: chat apps and sign-up (C1, C5, E6, E7), tides, catch log and price server, fish ID, mangroves,
admin dashboard, official-warning feed, other countries. The data screen keeps saying so.

### 4.3 Codex work package: backend + AI (assigned by the owner, 2026-11-26)

One Codex chair, items in order, **one branch per item, cut from `main`**, pushed to `origin` with the remote named.
The mask and pick work is built but unreviewed on `feature/mask-and-pick` (section 2, TASK-010) and is on hold, so
Codex does **not** touch `backend/masks/`, `backend/legal.py`, `backend/pick/`, `backend/compute/`, the pick step or
the `recommendations` writer. Everything here is the PM's brief; read `AGENTS.md`, `CODEX.md`,
`backend/README.md` and `backend/API_CONTRACT.md` first.

How the boxes work:

- `[ ]` open. `[x]` = Codex finished the item and says so. When you finish an item, tick **only your own boxes in this
  section**, on your branch, and append the short SHA and the date, e.g. `[x] ... (a1b2c3d, 2026-11-27)`. Change nothing
  else in `TASK.md`.
- The PM reproduces each item before it is merged and then appends `PM-checked` to the line. A ticked box without
  `PM-checked` is a claim, not a result.
- If an item turns out wrong or too big, stop and tell the PM; do not widen the scope.

Rules for every item:

- Verify yourself (`AGENTS.md` section 7): quote the output; every new guard or test gets a mutation check on a copy
  (remove the guard, the test must go red for that cause, record the file hash before and after, restore from the
  saved copy).
- Real PostGIS tests: Docker image `postgis/postgis:16-3.7` is already on the owner's machine; bind to `127.0.0.1`,
  random password that never touches the repo, database `TEMPLATE template0`, remove the container afterwards, run
  with `PELAGO_REQUIRE_DB=1` and `PELAGO_TEST_ADMIN_URL`. If your sandbox cannot reach Docker or localhost, say so and
  report "not tested: real PostGIS"; do not report a skipped test as a pass.
- No new package, dataset or other download without the owner's explicit yes (name, source, size). Needed packages
  are named below so you can ask once. The repository is public: no secrets, tokens, `.env`, raw dumps.
- Stay inside `backend/` and the root `.gitignore` unless the item says otherwise. Do not touch `src/`, `index.html`.
- Usage: read your meter before each item (the owner's rule: Codex remaining must stay at or above the day's floor).
  Keep context small; open one file at a time.

**CX-1 Backend hygiene** (branch `fix/backend-hygiene`; files: `.gitignore`, `backend/ingest/fetchers/`,
`backend/API_CONTRACT.md`, `backend/README.md`, `backend/config/`; small, do it first)

- [ ] Root `.gitignore` ignores `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/` (F-8); `git status` is clean after a test run
- [ ] Fetchers use the canonical ERDDAP dataset ids, and `http_get` in `backend/ingest/fetchers/base.py` no longer follows redirects blindly: only `https`, only the hosts already named in the area config, at most 2 hops; a test sends a redirect to another host and it is refused for that reason (F-9)
- [ ] The two lines that say the owner "may remove" the NOAA-20 fallback now say it is kept (D11)
- [ ] `wx_issued_at` is reworded in the contract and README as the retrieval time, not a forecast issue time (F-10)

**CX-2 FastAPI read API** (branch `feature/backend-api`; new folder `backend/api/`; the contract is the spec, section
12 of `backend/API_CONTRACT.md` lists the tests; asks the owner once for `fastapi`, `uvicorn`, `httpx` from PyPI)

- [ ] `GET /v1/health`, `GET /v1/areas`, `GET /v1/areas/{area_id}`, `GET /v1/areas/{area_id}/freshness` as in the contract
- [ ] `GET /v1/areas/{area_id}/spots` reads the `recommendations` / `fsi_daily` / mask rows only (never writes); with no picks it answers `200` with empty `spots` and the contract's `status` (`no_run`, `no_data`, `withheld_legal_incomplete`, ...), it never invents spots and the front end must not read an empty `200` as a reason to show anything else; legal status is passed through and the area stays labelled "trial: legal layers incomplete"
- [ ] The single confidence rule of contract 4.6 lives in one place and the API output uses it
- [ ] Connects with the read-only database role from `DATABASE_URL` (environment only); no secret in code, logs or error bodies; no stack trace in any error response; errors follow contract section 5
- [ ] Input hardening: unknown `area_id`, bad date, future date, bad `boat_class`, oversized or repeated query parameters, odd Unicode in path and query: each returns the documented 4xx and never a 500
- [ ] CORS allowlist and a basic rate limit (contract 2.2); the responses carry the `ETag` / `Cache-Control` / `X-Request-Id` headers of 2.1 (including `304` on `If-None-Match`)
- [ ] Contract tests of section 12 pass on a real PostGIS with seeded rows; each rule in 4.4 has a mutation check that goes red
- [ ] `backend/README.md` says how to run the API locally and what is not built

**CX-3 Daily job runner** (branch `feature/daily-job`; new `backend/jobs/`; the scheduler account, secrets and any
workflow file are owner actions, so no workflow file and no secret are committed)

Status: done (Codex, 2026-11-27). `origin/main` contains `backend/compute/pipeline.py` (merged in `8434caf`), and
the runner calls the mask → FSI → pick pipeline after ingest. The pre-merge fallback is also exercised explicitly.

- [x] `python -m backend.jobs.run_daily --area th-chonburi-coast [--date YYYY-MM-DD]` runs ingest then compute, writes `job_runs` rows per step, is idempotent (a second run changes nothing), and exits non-zero if any step failed; verified with required PostGIS tests enabled.
- [x] Mask and pick use a named hook. The merged compute pipeline path and explicit `skipped: not_built` fallback are both tested.
- [x] A failed ingest stops compute and creates no recommendation row; an injected failure recovers on retry. Mutation checks for the failure gate and idempotence gate fail on their named regression; see `backend/docs/daily-job-mutation-log.md`.
- [x] `backend/README.md` explains host cron/scheduler setup. No host account, schedule or workflow was configured; deployment choice remains open.
- Verification (2026-11-27): `383 passed in 70.87s` on PostGIS 16-3.7 with `PELAGO_REQUIRE_DB=1`; no tests skipped. Targeted job tests: `9 passed in 2.94s`. Disposable local PostGIS was removed after verification.

**CX-4 AI: FSI checks and stability measurements — MOVED from Codex to Claude AIE 01 on 2026-11-27 (see 4.5; Codex skips this item)** (branch `feature/fsi-checks`; files: `backend/fsi/`,
`backend/backtest/`, one new report under `backend/docs/`; numbers only, no accuracy claim)

- [ ] F-16: the SST temperature-front input is checked on one real SST field for the area (one small ERDDAP request, within the request limits already in the back-test brief); the report shows the gradient map statistics, edge-of-grid and land-adjacent behaviour, and says plainly if the front looks wrong
- [ ] Open question 13: with the existing back-test harness, measure week-to-week agreement for (a) today's weights, (b) a lower front weight, (c) the front smoothed over several days; same metrics as REVIEW-004 (Spearman, top-20% overlap vs random); the default weights in the config are **not** changed, the owner decides
- [ ] The report states what each result does and does not show; chlorophyll-empty behaviour (open question 12) is shown unchanged

Out of scope for Codex now: land/EEZ mask, pick step (they exist on the unreviewed branch `feature/mask-and-pick`; the PM reviews and merges them), front end, deployment accounts, Supabase project creation.

### 4.4 Handoff, end of 2026-11-26 (what Claude did today, and what Codex continues)

Done today by Claude seats (the PM chat and its seats), all on `main` unless stated:

- Front-end restructure, agent guides, `ARCHITECTURE.md`/`README.md`, API contract and schema, ingest, FSI v1 and
  back-test: merged earlier today and reviewed (TASK-002, 006 to 009; REVIEW-001 to 004).
- New PM chat: confirmed state (`main` = `origin/main` = `a861e8d`), wrote section 4.3 and recorded the mask hold
  (`34ca635`, pushed to `origin/main`).
- Mask seat: built the mask and pick step on `feature/mask-and-pick` `3a357a2` before the hold; not reviewed (TASK-010).

State to start from:

- `main` holds everything reviewed; 216 backend tests pass on it (PM run, REVIEW-004).
- `feature/mask-and-pick` is the only unmerged backend work. Codex must not merge it, rebase onto it or branch from it.
- The weekly Claude meter was 70% at the end of the day and resets Sat 2026-11-28 10:00 Thai time.
  Codex has its own meter; read it before each item.
- Owner decisions still open (section 6): 1, 2, 3, 12, 13, 14. Owner actions still open: Supabase project and roles,
  FastAPI host account, optional Global Fishing Watch token, confirm the dataset downloads of the mask seat.

Order for Codex: CX-1 (with CX-1b), then CX-2, then CX-3. CX-4 now belongs to Claude AIE 01 (section 4.5). After each item: tick your boxes (section 4.3 rules), push your branch to `origin`, print
`git ls-remote origin <branch>`, and send the report (Thai, `AGENTS.md` section 8) to the owner. The PM reviews by
reproducing; nothing goes to `main` without the owner's word.

Next for the Claude PM (not Codex): review `feature/mask-and-pick` after the weekly reset (suite on real PostGIS,
mutation checks on copies, check the provenance and licence note against the live pages), then merge on the owner's
word; then the front-end adapter (Pelago SWE 01, decision D9) once CX-2 is merged; then a reviewer seat for the red-team
pass; then the demo script.

**CX-1b (Codex, same branch `fix/backend-hygiene`; do before CX-2, findings in REVIEW-005):**

- [ ] F-20: `PoliteHttp` (and any other caller of `http_get`) works against the real allowlist: a test drives the back-test client against a faked `requests.get` and shows the request reaches the allowed host; the same test goes red when the fix is removed
- [ ] F-21: tests for the empty-allowlist refusal, the config `hosts` validation (empty, duplicate, uppercase, bad DNS name), userinfo and non-443 port, `bad_redirect` (no `Location`) and `redirect_limit` (three hops); mutation checks M4, M7, M8 go red
- [ ] F-22: confirm the two chlorophyll dataset ids and the host live (`.das` plus one small data request, within the request limits), quote the output, fix the fetcher if the layout differs, and record the new `config_sha256`; if `coastwatch.noaa.gov` still answers 5xx, say so and leave this box open


### 4.5 Claude seats: AIE 01 and SWE 01 (assigned by the PM on the owner's request, 2026-11-27)

Both seats work in **their own worktree** (`git worktree add .claude/worktrees/<name> -b <branch> origin/main`), not in
the main checkout, and push their branch to `origin` with the remote named. They tick only their own boxes here, on
their own branch, like Codex (section 4.3); the PM adds `PM-checked` after reproducing. The Claude weekly meter is shared
by every Claude chat: read it before starting and keep to the day's ceiling.

**AI-1 (Claude AIE 01 = Pelago AIE 01; branch `feature/fsi-checks`; this is the former CX-4)**

Files: new files under `backend/backtest/` and `backend/docs/`, and `backend/fsi/` only if a defect forces it. Do **not**
edit `backend/backtest/inputs.py` or `backend/backtest/run.py`: Codex fixes the allowlist problem there (F-20, CX-1b);
rebase on `main` after that merge before you re-run the live parts. Numbers only, no accuracy claim, default weights
unchanged.

- [x] F-16: check the SST temperature-front input on one real SST field for the area (one small ERDDAP request on `jplMURSST41`, within the request limits of the back-test brief): gradient statistics, grid-edge and land-adjacent behaviour; say plainly if the front looks wrong (`b2a07c5`, report `f462aba`) PM-checked 2026-11-27 (code, tests and mutations reproduced; the live numbers are REPORTED, see REVIEW-006)
- [x] Open question 13: with the existing harness measure week-to-week agreement for (a) today's weights, (b) a lower front weight, (c) the front smoothed over several days, same metrics as REVIEW-004 (Spearman, top-20% overlap vs random); the owner decides, the config default is not changed (`b2a07c5`, report `f462aba`) PM-checked 2026-11-27 (code, tests and mutations reproduced; the live numbers are REPORTED, see REVIEW-006)
- [x] The report states what each result does and does not show; chlorophyll-empty behaviour (open question 12) is shown unchanged (`f462aba`) PM-checked 2026-11-27 (code, tests and mutations reproduced; the live numbers are REPORTED, see REVIEW-006)

**FE-1 (Claude SWE 01 = Pelago SWE 01; branch `feature/frontend-api-adapter`; independent of Codex's API)**

Files: `src/`, `index.html` (minimal), `styles.css` (small), `README.md` front-end section, one mock server under
`tools/api-mock/` (Python standard library only, labelled ILLUSTRATIVE, added to `.vercelignore`). Spec: `backend/API_CONTRACT.md`
sections 4, 5 and 8, and decisions D9, D10 in section 6. No build step, no dependency, no change to what the UI promises.

- [ ] `src/services/api.js` reads `GET /v1/areas/{area_id}/spots` (`boat_class=small`) from a base URL in `src/config.js`; with no base URL set the page behaves exactly as today (compare the 12 screens against the baseline)
- [ ] D9: only a network error or a 5xx falls back to today's in-browser path, labelled "demo, not filtered, not a recommendation"; a `200` never falls back, including `200` with empty `spots`, where the Thai text for `status` (`no_run`, `no_data`, `withheld_legal_incomplete`, `withheld_sea_red`, ...) is shown; a test goes red when the guard is removed
- [ ] The popup and the sidebar use one confidence value (the API's; label "demo" on the fallback path), closing the two-rule finding (section 5 backlog); data age and the "trial: legal layers incomplete, not for real use" label are shown (one constant, so the owner's decision on open question 3 is a one-line change)
- [ ] Verified in a real browser over `http://` against the mock server (200 ok, 200 empty, 304, 500, network down), console clean, every local file 200; report what was not tested

Not assigned yet (the PM keeps them): review of `feature/mask-and-pick`, review of Codex branches, the red-team pass by a
separate reviewer seat, the demo script, deployment (owner accounts needed).

### 4.2 Other next steps

| ID | Task | Owner | Notes |
| --- | --- | --- | --- |
| TASK-004 | Feature summary of the code (what each screen and module does, what is real vs demo) | PM | Largely covered now by `ARCHITECTURE.md` Part B (gap analysis). Confirm with the owner whether a separate summary is still wanted |
| TASK-005 | Tell the teammate (upstream owner) about the path fix and the refactor before they keep building on `app.js` | Owner | MEASURED 2026-11-26 (`git fetch upstream`): `upstream/main` is still `5991d5b`, i.e. it has the broken `css/` / `js/` paths and the single-file `app.js`, and no commits we lack. If they edit `app.js` meanwhile, merging our `src/` layout will conflict |

## 5. Backlog (PROPOSED)

Backend:

- Define the API contract for spots and FSI (request, response, errors, freshness) so the front end can swap
  `src/data/spots.js` and `fetchSpotSignal` (`src/services/marine-data.js`) for backend calls.
- Move FSI computation server-side (it runs in the browser today, with weights `FSI_WEIGHTS` / `FSI_TARGETS` in
  `src/config.js` marked "untuned"). Needs a data source for real catch logs before the weights can be tuned.
- Decide where user data lives (price reports and pins are `localStorage` only; the catch journal saves nothing) and
  the privacy promise that goes with it.
- Follow `ARCHITECTURE.md` section B4: Phase 0 ingest job and legal layers, FSI v1 server-side, back-test harness,
  catch-log schema.
- Hosting: the front end stays on Vercel; the backend is FastAPI + Supabase (decision D5); where FastAPI runs is still
  to be chosen (section 6, open question 2).

AI:

- Fish-ID model behind the fish screen (`src/ui/views.js`, `fish()`): today a mock-up with no upload. Needs a data
  set, an evaluation plan, and a "human confirms the species" step that the UI already promises.
- Evaluation: a labelled set of catch records to check whether FSI predicts anything, before the UI claims it does.

Front end and quality:

- Verify the NASA GIBS layer ids and tile-matrix sets against `WMTSCapabilities.xml` (marked UNVERIFIED in
  `src/config.js`). The chlorophyll, sea-surface-temperature and true-colour layers may not render.
- Add a small automated smoke test (load the page, open each of the 12 screens, assert no console errors) so
  future changes do not rely on manual comparison.
- Favicon (the browser requests `/favicon.ico` and gets 404).
- **[Low] Two different "confidence" rules in the UI.** The map popup (`src/ui/popup.js:54`) says "medium" only when SST,
  chlorophyll and depth are all live; the sidebar spot list (`src/ui/sidebar.js:42`) says "medium" when the FSI score is
  75 or more. The second is derived from the score, not from data coverage, so the two can disagree for one spot.
  UNVERIFIED by running; read from the code. Settle with one rule (the guide's: high / medium / low from data
  completeness and freshness, capped at "medium" for areas without verified catch logs).
- Optional: a recovery note for the dropped superseded code (see finding F-2).

## 6. Decisions and open questions

### Decided by the owner on 2026-11-26

| # | Decision | Consequence |
| --- | --- | --- |
| D1 | Scope: prototype **plus** a backend/AI core | plan in section 4.1 |
| D2 | The function spec **S (2026-11-24)** is authoritative where it differs from the guide G (2026-11-21) | phases in `ARCHITECTURE.md` A3 follow S |
| D3 | Project type: **non-profit / social project** (the guide's route A) | all sources may be used, including non-commercial ones such as Open-Meteo, but the design must keep a switch to route B (replace WDPA, Open-Meteo, drop Global Fishing Watch) by configuration |
| D4 | Deadline: **within one week** | thin vertical slice, one area |
| D5 | Backend: **Python FastAPI + Supabase (PostgreSQL/PostGIS)** | needs a place to run FastAPI (owner action) |
| D6 | AI focus this week: **server-side FSI + back-testing**; fish ID stays a labelled mock-up | the fish screen keeps saying it is not real AI |
| D7 | The three reference documents are **not stored** in the repository; `ARCHITECTURE.md` is the summary | nothing to commit |
| D8 | Spot spacing: **10 km** minimum between recommended spots (config value; the guide's 5 km does nothing on the 0.05 degree grid) | `min_spacing_km: 10` in the area config |
| D9 | If the API is unreachable (network error or 5xx, never after a 200) the front end shows today's in-browser demo path, labelled "demo, not filtered, not a recommendation" | front end task must implement the label and the 200-never rule |
| D10 | Boat classes this week: `small` only in the UI; `medium` stays in the area config | UI uses `small` |
| D11 | Keep the NOAA-20 chlorophyll fallback (`erddap_viirs_n20_chl`) that the ingest seat added | stays in `th-chonburi-coast.json`; two wording lines saying "owner may remove it" still to fix |

### Still open

1. Exact submission date and format (a live demo? a video? a pitch?). The plan assumes about 2026-12-03.
2. Where the FastAPI service runs, and who creates that account (section 4.1, owner actions).
3. **Legal data gap.** The guide's rule is "no complete legal-zone data = do not recommend". For the Chonburi coast we
   will have land and EEZ but **not** closed seasons or protected zones this week. Options: show spots clearly marked
   "trial: legal layers incomplete, not for real use" (PM's proposal, matches the prototype's honest labelling), or
   show no spots for the area. Which one for the demo?
4. Demo area: the Chonburi coast (proposed), or another?
5. Global Fishing Watch token for the back-test: will the owner register one (internal use only)?
6. ~~Repository layout for the backend~~: `backend/` in this repository, as proposed; merged 2026-11-26 with the contract. Tell the PM if you want a separate repository instead.
7. Tell the teammate who owns `upstream` (TASK-005) before they edit `app.js`.
8. ~~**Spot spacing.**~~ **Decided D8 (10 km).** The guide's "at least 5 km apart" does nothing on the 0.05 degree grid (cell centres are already
   5.4 km apart), so the top 5 spots may be adjacent cells. The backend seat and the PM recommend 10 km in config.
9. ~~**Front-end fallback when the API is down.**~~ **Decided D9 (labelled demo path, never after a 200).** Show today's in-browser demo path clearly labelled "demo, not filtered"
   (the seat's default, only on a network error or a 5xx, never on a 200), or show nothing? The in-browser path has no
   legal, land or sea-state filter.
10. ~~**Boat classes this week:**~~ **Decided D10 (`small` in the UI).** `small` only, or `small` and `medium` (the guide gives thresholds for both; the maximum
    range for `medium` is not given).
11. Other backend decisions with defaults are listed in `backend/README.md` section 5 (15 items); silence means the default.
12. **Chlorophyll is nearly empty right now.** On 2026-11-26 the newest valid chlorophyll is 10 to 18 days old and the ingest
    filled only 12 of 200 cells (6%) even with the NOAA-20 fallback. The FSI then runs mostly on temperature, front, depth and
    moon, and confidence is low. Options for the demo: (a) show it honestly with the low confidence (PM default), (b) also run
    the demo on a recent date that has better chlorophyll coverage (the dry run found 2026-11-08 and 2026-11-11 had about 80% of
    water cells), labelled as a past date. Which one? New evidence (back-test): removing chlorophyll entirely changes the ranking little
    (Spearman 0.95, top 20% keeps 89%), so showing it honestly with low confidence costs the demo little.
13. **Week-to-week stability of the spots.** The back-test (REVIEW-004) found that maps one week apart agree little (mean Spearman 0.19;
    the top 20% of cells overlaps 25% against 20% for a random map) and that the temperature front causes most of it. Whether spots may
    move that much is a product decision. Options: accept it and say so in the demo (PM default), lower the front weight, or smooth
    the front over several days. The front itself is still unverified on real data (F-16).
    **Result (REVIEW-006, 2026-11-27):** week-to-week Spearman 0.190 now; 0.305 with the front weight 0.10; 0.420 with 0.05; 0.468 with no front. Smoothing the front over 3 days changes almost nothing. Calmer does not mean more accurate. **Owner decision needed:** keep 0.20 and say so in the demo (PM default), or lower the front weight to 0.10.
14. **More back-test requests?** The 250-request cap left 11 of 52 dates unfetched and no daily sample. Another budget is optional;
    it adds load on the public NOAA server and meter use. Default: no.

## 7. Review log

### REVIEW-001 — `refactor/frontend-structure` (`db85230..86519dd`), reviewed 2026-11-26 by the PM

Verdict: **approve for merge**, no behavior difference found. Method: the PM extracted the baseline `db85230` and the
branch `86519dd` with `git archive` into separate folders, served both, and compared them in a browser. The SWE's
own report was not relied on.

| Check | Result | Label |
| --- | --- | --- |
| `node --check` on all 23 files in `src/` and on the old `app.js` | all parse | MEASURED 2026-11-26 |
| Functions called from inline `on*=` handlers vs `window` exports | new version: 12 handler functions, all exported in `src/main.js`. Old version: the same 12 plus `$`, which appeared only in the unreachable photo-picker markup (see F-2) | MEASURED 2026-11-26 |
| 12 workspace screens (`show(...)`): text, inputs, images, handler counts | identical per screen (digits masked) | MEASURED 2026-11-26 |
| Fuel and price calculators with fixed inputs, digits **unmasked** | identical, e.g. 4,968 baht and 540.0 litres in both | MEASURED 2026-11-26 |
| Drill-down (`pickC`, `pickP`, `go`), layer toggles, `localStorage` write | identical text hashes, same `pr` entry | MEASURED 2026-11-26 |
| Computed styles (41 properties) + layout rectangles on 5 screens (survey, route, fuel, log, sos), 1280x800 | 0 differing elements on log and sos; on survey, route, fuel only the map popup `#pop` differs by 1–3 px, which follows a marker while the camera moves (timing, not CSS) | MEASURED 2026-11-26 |
| Initial globe screenshot, both versions | visually identical | MEASURED 2026-11-26 |
| Console and network on the new version | no errors on a fresh load; all local files 200 | MEASURED 2026-11-26 |
| Secrets scan on `src/`, `index.html`, `styles.css` | none; `src/config.js` states endpoints are key-less | MEASURED 2026-11-26 |
| Scope: `vercel.json`, `.gitignore` untouched; commits in English; no extra files committed | as expected | MEASURED 2026-11-26 |

Findings:

- **F-1 [Low] Hidden workspace is built lazily.** At load time the old code pre-built the hidden `#view` (12 `show(...)`
  targets in the DOM), the new code builds it on the first `show()` (7 targets from the bottom bar). Nothing visible
  differs once a screen is opened. Evidence: MEASURED 2026-11-26, DOM query right after load on both versions.
- **F-2 [Low] Dead code was removed.** The old `app.js` defined each workspace screen twice (lines 148–156 and
  170–175); the second definitions override the first, so the first set was never reachable (the old fish screen with
  an `<input type=file capture>` photo picker is in that set). The SWE removed them and said so in the commit message.
  The old code stays recoverable with `git show db85230:app.js`. If the AI team wants the photo-picker idea, start
  from there. Not a regression: the screen the user actually saw has no upload.

Not tested: a phone-width viewport, pixel-level comparison of the canvas globe (it animates), real pointer
drag/hover/click on globe markers, GPS (`pins`, `sos`), speech, whether the cloud-layer tiles render (GIBS ids are
unverified), the `sea`, `go`, `fish`, `data`, `price`, `bloom`, `pins` screens in the style comparison (their text and
inputs were compared), and a real Vercel deployment.

`QA: 2 findings (C/H/M/L = 0/0/0/2) - 2 reproduced - not tested: phone viewport, canvas pixels, pointer input, GPS/speech, GIBS tiles, Vercel deploy`

### REVIEW-002 — `feature/backend-contract` (`19cc7b6..93b82e0`), reviewed 2026-11-26 by the PM

Verdict: **approve for merge** as a design. Nothing is implemented, deployed or executed. Method: the PM exported the
branch with `git archive`, read all four files, and reproduced the arithmetic claims; the seat's report was not relied on.

| Check | Result | Label |
| --- | --- | --- |
| Scope: only new files under `backend/`; no `src/`, `index.html`, `styles.css` or root doc touched | confirmed (`git diff --name-only`) | MEASURED 2026-11-26 |
| Secrets scan of the four files | none; the matches are rules about secrets | MEASURED 2026-11-26 |
| Cell-id scheme `pelago-cell-v1`: all 9 test vectors in `db/schema.sql`, recomputed independently (Decimal, half-up) | all reproduced, including the edge, negative and out-of-range cases | MEASURED 2026-11-26 (Python only; the SQL function was not run) |
| Claim: float `floor((lat+90)/0.05)` is wrong on cell edges | reproduced: `(12.3+90)/0.05 = 2045.9999999999998`; 170 of 3000 latitudes (0.00 to 29.99) land in the wrong row | MEASURED 2026-11-26 |
| Claim: the "5 km apart" spot rule does nothing on a 0.05 degree grid | reproduced: neighbouring centres are 5.57 km (lat) and 5.43 km (lon) apart at 12.5 N | MEASURED 2026-11-26 |
| Contract vs `schema.sql` vs the front end (`spot.fsi`, `spot.signal`) and ARCHITECTURE.md A4/A5 | consistent on reading; field-to-column table covers every contract field | READ 2026-11-26 |
| `schema.sql` executed on PostgreSQL/PostGIS | not run at review time; **executed later the same day** with the owner's permission (`postgis/postgis:16-3.7`): applies cleanly, 42 of 42 checks pass after the F-3 fix | MEASURED 2026-11-26 |

Findings:

- **F-3 [Low] The database could not stop a recommendation that pointed at an unscored cell.** Reproduced on 2026-11-26 by executing the schema on PostgreSQL 16 + PostGIS 3.7 (the cell with no SST was accepted as a spot). Fixed on branch `feature/schema-verified`: a generated `scored` column on `fsi_daily` and a composite foreign key from `recommendations`; regression test G21 goes red on the old schema and green on the new one, and mutation test M4 shows the foreign key is what blocks it. While doing this a test flaw surfaced: the first version of G12/M2 used a cell that two guards refused, so removing one guard did not turn the test red; the test now uses a scored land cell. See `backend/README.md` section 7.
- **F-4 [Medium, fixed in this merge] `.env` was not ignored** in a public repository whose backend will need one
  (reported by the seat as F1, confirmed by the PM against `main`). Fixed with the root `.gitignore` rules, tested with
  `git check-ignore` (`.env`, `.env.local`, `backend/.env`, `*.pem` ignored; `.env.example` not ignored).
- **F-5 [Low, fixed in this merge] `vercel.json` serves the repository as static files**, so `backend/` would be published
  on the front end's domain by a CLI deploy. Fixed with `.vercelignore`. UNVERIFIED which deploy method the owner uses.
- The seat's own findings R1–R12 (design risks) and 15 owner decisions are in `backend/API_CONTRACT.md` section 11 and
  `backend/README.md` section 5. The most urgent ones are items 8 to 10 in section 6.

`QA: 3 findings (C/H/M/L = 0/0/1/2) - 3 reproduced or confirmed by reading - not tested at review time: schema execution (done later, see F-3), upstream datasets, Supabase behaviour`

### REVIEW-003 — `feature/backend-ingest` (`a439c39..73d2f00`), reviewed 2026-11-26 by the PM

Verdict: **approve for merge**. Method: the PM exported the branch with `git archive`, started its own throwaway PostGIS
container, ran the whole suite with the seat's virtual environment on that copy, mutated copies of the code, and queried the
public servers for the facts the seat reported. The seat's report was not relied on where a check was possible.

| Check | Result | Label |
| --- | --- | --- |
| Scope: 33 files, all under `backend/`; no `src/`, `index.html`, `styles.css` or root document touched | confirmed | MEASURED 2026-11-26 |
| Secrets and credentials scan of `backend/` | none; matches are rules, tests and docs about secrets | MEASURED 2026-11-26 |
| `pytest`, database tests forced on (`PELAGO_REQUIRE_DB=1`), fresh `postgis/postgis:16-3.7` container | **101 passed** (numpy 2.5.5, requests 2.34.2, psycopg 3.3.9, pytest 9.2.0) | MEASURED 2026-11-26 |
| PM's own mutation checks on copies: local date taken from UTC; config secret scan removed; `job_runs` error-code sanitiser removed; licence-route check removed; missing SST written as 0 | all 5 **red**; the unmutated control passed 101; the exported files' hashes were unchanged | MEASURED 2026-11-26 |
| SST `jplMURSST41` newest time | `2026-11-24T09:00:00Z`, as the seat reported | MEASURED 2026-11-26 |
| Chlorophyll newest time: `nesdisVHNchlaDaily` and NOAA-20 `nesdisVHNnoaa20chlaDaily` | `2026-11-15T12:00:00Z` and `2026-11-16T12:00:00Z`, as the seat reported | MEASURED 2026-11-26 |
| Licence text of the three ERDDAP datasets (chlorophyll, ETOPO, MUR SST) | "may be used and redistributed for free but is not intended for legal use", as the seat reported; whether that is enough for route B is a legal question the PM did not settle | MEASURED (text), UNVERIFIED (legal reading) |
| The seat's end-to-end run into a throwaway database: 200 cells, SST 136, chlorophyll 12, depth 126, waves and wind 200, no fake zeros | **not re-run by the PM** (the 5-hour usage meter was at 88%; it would also add load on the public servers) | REPORTED |
| Coverage numbers in the dry run (for example SST and waves/wind 100% of water cells) | not re-measured; consistent with the reported run | REPORTED |

Findings (the seat's list, re-numbered, plus the PM's):

- **F-6 [Medium] Chlorophyll is almost absent today.** Confirmed with the live checks above: the newest valid day is older than the 10-day limit for the primary, and the fallback fills 6% of cells. Not a bug: a data-supply fact that the design handles (weight 0, lower confidence). It decides how honest and how good the demo looks (open question 12).
- **F-7 [Low] `config_sha256` depends on line endings.** It hashes the file's raw bytes. The committed blob is LF, but this machine has `core.autocrlf=true`, so a Windows checkout is CRLF: the same file hashes to `5ec43777dc2e32c8` as LF and `1aefa71c6b2c3b12` as CRLF. Results and ETags would then differ between machines. Reproduced by the PM (hashing the real config file both ways).
- **F-8 [Low] Root `.gitignore` has no `.venv/`.** The README tells users to create the environment at the repository root (`..\.venv`), where `backend/.gitignore` does not apply. Confirmed with `git check-ignore .venv`: not ignored. The seat avoided it with a local exclude. Low because a committed virtual environment is large and noisy rather than secret.
- **F-9 [Low] ERDDAP dataset ids are legacy aliases.** MEASURED 2026-11-26: `nesdisVHNchlaDaily` and `nesdisVHNnoaa20chlaDaily` answer HTTP 302 and redirect to `noaacwNPPVIIRSchlaDaily` and `noaacwN20VIIRSchlaDaily` on `coastwatch.noaa.gov`, a different host. The ingest works only because `requests` follows redirects by default. `http_get` (`backend/ingest/fetchers/base.py`, lines 57 to 77) checks that the first URL starts with `https://` and never checks the final URL or host, so a downgrade or an unexpected host would be followed. The URLs are hard-coded NOAA addresses, so the actor would be a compromised or misconfigured upstream or a network attacker. Fix: use the canonical ids, pass `allow_redirects=False` or check the final URL against an https host allow-list, and add a test that goes red when the check is removed.
- **F-10 [Low] `wx_issued_at` is the retrieval time**, because Open-Meteo returns no forecast issue time (the seat's finding). The contract calls it the issue time; reword it and compute forecast age from retrieval time.
- **F-11 [Low] The attempt limit is 10 per day per variable and source** (schema constraint); an eleventh re-run of the same day fails with `attempt_limit`. Acceptable now; remember it in a demo rehearsal.
- **F-12 [Info] Values the masks must remove.** Waves and wind are stored for every cell including land, SST for 10 partly-land cells, and depth is NULL for land cells (the prototype used `max(0, -z)`). The mask task must handle all three.
- **F-13 [Info] The seat added the NOAA-20 fallback on its own** (reported by the seat); the owner chose to keep it (D11).

Not tested: Supabase itself, a scheduler, the API, the FSI, the masks, Open-Meteo for dates older than about 6 days, the NOAA-20 fallback on a clear-sky day, the physical correctness of the SST front computation on real data (the seat compared it only with a synthetic linear field), the attribution wording of each source.

`QA: 6 findings (C/H/M/L = 0/0/1/5) + 2 info - 3 reproduced by the PM (line-ending hash, .venv not ignored, redirects) and 2 confirmed live (chlorophyll dates, licence text) - not tested: end-to-end ingest re-run, Supabase, scheduler, API/FSI/masks`

### REVIEW-004 — `feature/fsi-v1` (`7651324..baedcde`) and `feature/backtest` (`..5e829f5`), reviewed 2026-11-26 by the PM

Verdict: **approve for merge** (both branches, `feature/backtest` contains `feature/fsi-v1`). Process: the seat first sent a design note; the PM checked its
claims against the repository, answered 9 points and added 3 (front percentile over water cells only; "future" measured against the end of the local
run date; no `chl_8day_fresh` key); the seat then built it. Review method: the PM exported the branch with `git archive`, ran the whole suite on its own
PostGIS container, mutated copies of the code, and re-hashed the config. The seat's report was not relied on where a check was possible.

| Check | Result | Label |
| --- | --- | --- |
| Scope: 26 files, all under `backend/` except a new root `.gitattributes` (2 lines, `backend/config/**/*.json text eol=lf`); `requirements.txt` unchanged; no `src/`, `index.html`, `styles.css`, `TASK.md` touched | confirmed | MEASURED 2026-11-26 |
| `pytest` with database tests forced on, fresh `postgis/postgis:16-3.7` container | **216 passed** (101 before this work + 115 new) | MEASURED 2026-11-26 |
| PM's own mutation checks on copies (10): no-SST scored as 0; trial area reaches `high`; future-dated observation accepted; bloom cut removed; unknown verification level fails open; front percentile over all cells; freshness missing from the numerator; percentile ties removed; depth score unclipped; recommendation pre-check removed | all 10 **red**; control passed 216; exported files' hashes unchanged | MEASURED 2026-11-26 |
| Formulas and rules read against API_CONTRACT 4.5/4.6, ARCHITECTURE A4/A5 and the prototype (`min(d/10,(200-d)/120)`, `1-0.6*illumination`, bloom cut, freshness shape) | consistent; every weight and threshold comes from the validated `fsi` config; division-by-zero cases are refused by `validate_fsi` | READ 2026-11-26 |
| `config_sha256` of `th-chonburi-coast.json` after the key additions | `46e87256a902eb47` (LF), as reported; the committed blob has no CRLF | MEASURED 2026-11-26 |
| Contract change `baedcde` (`*_invalid` codes) | one line, additive only | MEASURED 2026-11-26 |
| Network use in `backtest/`, `fsi/` | only ERDDAP through the ingest fetchers, request cap and 2 s pause in code, cache folder inside the repo is refused; no Open-Meteo, no Global Fishing Watch | READ 2026-11-26 |
| Secrets scan of the two branches' files | none | READ 2026-11-26 |
| The seat's own mutation logs (FSI 28 points, back-test 10 points, all red) and its live back-test run (250 requests, 41 of 52 dates) | **not re-run by the PM**; the numbers below come from the seat's report and `docs/fsi-backtest-report.md` (the cache of upstream values is in the seat's private scratch area and the PM did not search for it) | REPORTED |

What the back-test says (REPORTED by the seat, plain reading; **none of it is evidence of accuracy**):

- All 10 direction-of-response checks pass. FSI is compressed: median 73.5, p10 61, p90 84.
- The temperature front drives the ranking (spread 7.3 points; switching its weight off drops the rank correlation to 0.36) and is the main source of week-to-week change (stability 0.19 with it, 0.47 without it).
- Maps one week apart agree little: mean Spearman 0.19, top 20% overlap 25% (a random map would give 20%).
- Chlorophyll removed completely (today's demo situation): Spearman 0.95 with the full ranking, top 20% keeps 89%.
- Confidence `medium` for 26% of cells and `high` for none (the area is `trial`).

Findings:

- **F-14 [Low] A missing `regions` row cannot be recorded.** `job_runs` has a foreign key to `regions`, so `no_region` is only logged and returned as an exit code (`fsi/pipeline.py` lines 36 to 39). Read by the PM; the seat reproduced it.
- **F-15 [Low] Ranges live in code, not config.** The plausible value ranges (SST -2..40, chlorophyll 0..1000, depth 0..12000, gradient 0..100) are constants in `fsi/model.py` that mirror the schema CHECKs, and the rule `weights.sst > 0` lives in `fsi/config.py` rather than in `validate_fsi`. Acceptable now.
- **F-16 [Medium] The ranking rests on an unverified input.** The front (SST gradient) was checked only against a synthetic linear field (REVIEW-003) and now carries the largest share of the ranking and of its instability. Check it on one real SST field before the demo, and decide open question 13.
- **F-17 [Info] The spots can change a lot from week to week** (see above); a product question, not a defect.
- **F-18 [Info] The back-test is partial:** 41 of 52 dates (the 250-request cap stopped it before 2026-04-08; one date failed with `http_503` and was left out), no daily sample, nothing on hit rate with real catch data.
- **F-19 [Info] Handoff to the mask/pick seat:** `recommendations.fsi` and `.confidence` are copies; when the FSI changes, the pick step must run again (the FSI job fails with `recommendation_conflict` instead of leaving a stale copy). The seat showed that PostgreSQL itself blocks making a picked cell unscored (`scored` foreign key; the PM's earlier schema test showed the same mechanism for unscored cells).

Not tested: Supabase, a scheduler, the API, the land and EEZ masks (cells that ETOPO treats as water but are land are still scored), periods longer than 12 months, the 11 missing dates, daily results, `hit_rate` on real data, the seat's back-test cache and live run.

`QA: 4 findings (C/H/M/L = 0/0/1/3) + 3 info - 216 tests and 10 mutations reproduced by the PM, config hash re-measured - not tested: Supabase, scheduler, API, masks, the seat's live back-test run`

### REVIEW-005 — `fix/backend-hygiene` (CX-1, Codex), `main..d6e860c`, reviewed 2026-11-27 by the PM

Verdict: **do not merge yet; three follow-ups on the same branch (CX-1b in section 4.4).** The branch has 3 commits and
13 files, all under `backend/` plus `.gitignore` and `TASK.md`; no file outside the item's scope. Method: `git archive`
of `origin/fix/backend-hygiene` into a scratch folder, suite run, a search for every caller of `http_get`, live checks of
the dataset ids, and mutation checks on copies (source hashes unchanged afterwards).

| Check | Result | Label |
| --- | --- | --- |
| Suite on the branch (no database) | 202 passed, 15 skipped (the skipped ones need PostGIS; not run) | MEASURED 2026-11-27 |
| `.gitignore`, NOAA-20 wording, `wx_issued_at` wording (contract, README, schema comment) | present; the schema change is a comment only | READ 2026-11-27 |
| Redirect hardening in `http_get` (https only, no userinfo or odd port, host allowlist per source, at most 2 hops, `allow_redirects=False`) | matches F-9 as written; mutations M1 (host check removed), M5 (`allow_redirects=True`), M6 (scheme check removed) go **red** | MEASURED 2026-11-27 |
| Mutations M4 (empty allowlist not refused), M7 (config `hosts` validation removed), M8 (userinfo/port check removed) | stay **green**: those three guards have no test | MEASURED 2026-11-27 |
| New ERDDAP ids `noaacwNPPVIIRSchlaDaily` / `noaacwN20VIIRSchlaDaily` on `coastwatch.noaa.gov` | **could not be confirmed**: that host answered 502 on 4 requests (also its index page); the old ids now return 404 on `coastwatch.pfeg.noaa.gov`; the new ids are not in that server's catalogue search. `jplMURSST41` and `ETOPO_2022_v1_15s` still answer 200 | MEASURED 2026-11-27 |

Findings:

- **F-20 [Medium] The back-test breaks on every live request.** `PoliteHttp` (`backend/backtest/inputs.py:31`) defaults its
  inner function to `http_get`, which now refuses a call without `allowed_hosts` (`FetchError("bad_config")`). The back-test
  CLI builds it with no inner function (`backend/backtest/run.py:47`), and `registry.build` only supplies the allowlisted
  function when no `http` is passed. Reproduced: `PoliteHttp(pause_s=0)("https://coastwatch.pfeg.noaa.gov/erddap/info/index.json", 5)`
  raises `bad_config`. The tests inject a fake function, so they stay green. Ingest is not affected (it uses `registry.build`
  without `http`). Actor: anyone who re-runs the back-test online. MEASURED 2026-11-27.
- **F-21 [Low] Three new guards and two new error codes have no test** (M4, M7, M8 above; `redirect_limit`, `bad_redirect`
  have no direct test either).
- **F-22 [Medium, UNVERIFIED] The chlorophyll dataset change is not shown to work.** The report gives no evidence for the new
  ids or the new host; a new dataset can have a different layout (axes, descending latitude, pixel size), and the fetcher
  parses by that layout. What would settle it: one `.das` request and one small data request to the new dataset through the
  fetcher once `coastwatch.noaa.gov` answers, plus a fetcher test fixture taken from that reply. Note also that the area
  config now has `hosts`, so its `config_sha256` changes (expected, record the new value).

`QA: 3 findings (C/H/M/L = 0/0/2/1) - 3 reproduced (F-20, F-21 mutations; F-22 is UNVERIFIED) - not tested: PostGIS-backed tests (skipped), the live chlorophyll fetch (server 502), the other 4 mutation targets of the redirect loop`

### REVIEW-006 — `feature/fsi-checks` (AI-1, Claude AIE 01), `1679bb3..0b46063`, reviewed 2026-11-27 by the PM

Verdict: **approve for merge.** 3 commits, 7 files: new code under `backend/backtest/`, one report in `backend/docs/`,
two test files, and the seat's own three boxes in this file. `backend/fsi/`, `inputs.py`, `run.py` and the default weights
are untouched (config hash unchanged, REPORTED). Nothing raw or from the cache is in the diff.

| Check | Result | Label |
| --- | --- | --- |
| Suite on the branch (no database) | 221 passed, 15 skipped (PostGIS tests not run) | MEASURED 2026-11-27 |
| Mutations on copies of `variants.py` (source hashes unchanged afterwards): overlap guard removed, missing day counted as 0, front factor ignored, window-length guard removed | all **red** | MEASURED 2026-11-27 |
| Mutation: the "fewer than 3 common cells" skip removed | stays **green**: that guard has no test (Low) | MEASURED 2026-11-27 |
| Mutation: cache-outside-repository guard replaced by an undefined name | red, but by a `NameError`, so it proves nothing about that guard; the seat's own log lists a mutation for it | MEASURED 2026-11-27 (my mutation was poorly built) |
| Live numbers (gradient statistics on one MUR field; Spearman 0.190 / 0.305 / 0.420 / 0.468 for front weight 0.20 / 0.10 / 0.05 / 0; 3-day smoothing 0.238 to 0.252; chlorophyll-empty 0.130) | not re-run: they need the seat's request cache, which is outside this repository. The control (0.190, top 20% kept 25%) equals REVIEW-004 | REPORTED |

What the report supports, in my words: the front input is computed correctly (it agrees with an independent haversine
calculation) but its real size is small (median 0.022 degC/km, max 0.12), and `S_front` is a percentile inside the area, so it
gives the full weight of 0.20 to a weak gradient (F-23). Lowering the front weight makes the maps calmer; smoothing the
front over 3 days does not, because the gradient map itself has almost no agreement a week apart. **Calmer is not more
accurate**: "SST only" is also not calm (0.12). The owner decides the weight (open question 13).

Findings of the seat, kept as written: F-23 [Medium, design] percentile front gives a weak gradient full weight; F-24 [Low]
a cell's gradient may rest on few pixels (7 of 136 cells under half); F-25 [Low, UNVERIFIED] `fetch_field` reads the private
`_http`/`_sleep` of a fetcher to keep the allowlisted HTTP, so after `fix/backend-hygiene` is merged one field must be
fetched again to confirm it still works. PM addition: **F-26 [Low]** the `< 3 common cells` skip in `pair_metrics` has no test.

`QA: 4 findings (C/H/M/L = 0/0/1/3) - 1 reproduced (F-26; F-23 to F-25 are the seat's, REPORTED) - not tested: the live fetches and the seat's offline re-run (cache not in the repository), PostGIS tests, the front-end of any of this`

### REVIEW-007 — `feature/mask-and-pick` (TASK-010, mask seat), `a861e8d..3a357a2`, reviewed 2026-11-27 by the PM (first part)

Verdict so far: **no defect found in the part I could run; do not merge until the PostGIS part is run.** The branch is 2 commits,
28 files, all under `backend/` (new `masks/`, `pick/`, `compute/`, `legal.py`, `seastate.py`, 7 test files, one mutation log, one
small land layer). A trial merge into `main` (`git merge-tree`) has no conflicts. Method: `git archive` into a scratch folder,
suite run, 15 mutations on copies (source hashes unchanged afterwards), the layer hash and both licence statements re-checked
against the live pages.

| Check | Result | Label |
| --- | --- | --- |
| Suite without a database | 306 passed, 43 skipped (the skipped ones are the real-PostGIS tests) | MEASURED 2026-11-27 |
| Mutations on `legal.py` (land may be eligible; EEZ not required; a forbidden flag no longer blocks; red sea no longer blocks; missing or stale forecast no longer blocks; unknown layers always allowed; flag coercion allowed) | 7 of 7 **red**, each in a test that names the cause | MEASURED 2026-11-27 |
| Mutations on `pick/select.py` (spacing `>` instead of `>=`; spacing check removed; bbox check removed; non-finite FSI kept; duplicate cell ids kept; limit above 5) | 6 of 6 **red** | MEASURED 2026-11-27 |
| Mutations on `seastate.py` (red wave threshold `>`; a missing partner value softens danger; stale forecast treated as fresh) | 3 of 3 **red** | MEASURED 2026-11-27 |
| `land.geojson` sha256 and size | `1b8d828b...ffe99`, 3,621 bytes: equals `PROVENANCE.md` | MEASURED 2026-11-27 |
| Licence statements: Natural Earth "in the public domain"; Marine Regions "licensed under CC-BY since Maritime Boundaries version 11 (2019)", asks users "not to make our products available for download elsewhere", "no legal value" | the pages say so, so the choice not to commit the EEZ layer and to fetch it at build time is consistent with the provider's request | MEASURED 2026-11-27 |
| Real PostGIS tests (the "no recommended spot in a forbidden cell" foreign-key tests, idempotent pick, mask run) | **not run**: Docker Desktop was not running (`dockerDesktopLinuxEngine` pipe missing) | NOT TESTED |
| `masks/geo.py`, `masks/layers.py`, `fetch_eez.py` (point in polygon, EEZ buffer, holes treated as coast, redirect refusal) | read only the `legal.py`, `select.py`, `seastate.py` code; the geometry code has no mutation checks from me | NOT TESTED |

Notes for the owner and the next step (not defects):

- The sea-state rule uses `wx_issued_at`, which is now the retrieval time (REVIEW-005, F-10), so "stale forecast" means "the data
  we fetched is old", not "the forecast model run is old". That is a fair freshness proxy; say it that way in the demo.
- A cell with a missing wave or wind value is "yellow, not eligible" (conservative); danger is never softened by a missing
  partner value (mutation Z2 proves the test exists).
- The EEZ layer is fetched at build time from Marine Regions, so a fresh machine needs network access and the provider can
  change the data; the mask run stores the layer hash in `job_runs.detail`.

To finish this review: start Docker Desktop, then run the full suite with `PELAGO_REQUIRE_DB=1` against a throwaway PostGIS
container, plus 3 to 4 mutations of the database guards (the foreign key to an eligible mask row, the CHECK on
`cell_mask_daily`) and 2 to 3 mutations of the geometry code.

`QA: 0 findings (C/H/M/L) - 0 reproduced - not tested: the 43 PostGIS tests, the geometry modules, the live EEZ fetch`

### REVIEW-007, second part — `feature/mask-and-pick` on a real PostGIS, 2026-11-27 by the PM

Verdict: **approve for merge** (a clean trial merge into `main` was shown in the first part). The part that was missing is now run.

| Check | Result | Label |
| --- | --- | --- |
| Full suite on a throwaway PostGIS 16.x container (`PELAGO_REQUIRE_DB=1`, bound to 127.0.0.1, random password, container and password file removed afterwards) | **349 passed, 0 skipped** | MEASURED 2026-11-27 |
| `backend/db/tests/schema_test.sql` (guards G, mutations M) on the schema of the branch, which the branch did not change | 42 of 42 pass, including M2 (no mask FK: a non-eligible cell can be recommended) and M4 (no scored-row FK: a cell with no SST can be recommended), which prove those guards can go red | MEASURED 2026-11-27 |
| Database mutations on copies: eligibility CHECK on `cell_mask_daily` removed; recommendations FK to an eligible mask row removed | both **red**, in tests that name the cause | MEASURED 2026-11-27 |
| Geometry mutations on copies of `masks/geo.py`: land test inverted; EEZ border buffer inverted; outside the national waters not refused; coast tolerance 2 km to 0; islet holes not treated as coast | 5 of 5 **red** (the 4.8 km versus 5.2 km border test and the islet test fail for the right reason) | MEASURED 2026-11-27 |
| Not caught by the pytest suite: the FK to a scored FSI row removed (covered by the SQL test M4); the "complete needs every flag" CHECK removed; the "no border at all counts as inside" branch flipped | green | MEASURED 2026-11-27 |

Findings:

- **F-27 [Low] Two database guards and one geometry branch have no pytest test.** The "complete needs every flag" CHECK has two
  independent guards (this CHECK and `legal.legal_status`), and the scored-row FK is covered by `schema_test.sql`, so no real
  gap in the guarantee; the "empty border counts as inside the EEZ" branch (`masks/geo.py`, `WHEN ST_IsEmpty(border.geom) THEN TRUE`)
  is the one to add a test for. Actor: nobody in normal use (an area whose national waters have no border at all).
- **F-28 [Info] Not tested by me:** the live EEZ fetch from Marine Regions (`masks/fetch_eez.py`) and the redirect refusal there; the
  real Chonburi cell results (which cells are land or outside the buffer on the actual layers); the order mask, fsi, pick in a
  scheduled run.

For the demo: the area is still "trial: legal layers incomplete" because protected zones, closed seasons, disputed areas and boat-class
zones are not loaded; the mask removes land and cells outside the EEZ buffer, and red or unknown sea cells, and nothing else.

`QA: 2 findings (C/H/M/L = 0/0/0/1) + 1 info - 1 reproduced (F-27) - not tested: the live EEZ fetch, the real Chonburi layer results, a scheduled run`

### REVIEW-008 — `feature/fsi-test-gaps` (AI-2, Claude AIE 01), `1815713..b7a9382`, reviewed 2026-11-27 by the PM

Verdict: **approve for merge.** One commit, 3 files, tests and a mutation log only, no behaviour change (the branch was cut before
the documentation commit, so a plain diff against today's `main` shows the new docs as deleted; against the merge base the diff
is 3 files, +97 lines, and a trial merge into `main` is clean).

| Check | Result | Label |
| --- | --- | --- |
| Suite without a database | 327 passed, 47 skipped | MEASURED 2026-11-27 |
| Suite on a throwaway PostGIS (`PELAGO_REQUIRE_DB=1`, container and password file removed afterwards) | **374 passed, 0 skipped** | MEASURED 2026-11-27 |
| F-26 closed: the "fewer than 3 common cells" skip removed | the new test goes **red** (before: green) | MEASURED 2026-11-27 |
| F-27 closed: the "no border at all counts as inside the EEZ" branch flipped | the new test goes **red** (before: green); the file also holds a control showing a real border does refuse a cell, so the True comes from that branch | MEASURED 2026-11-27 |
| Source hashes after the mutations | unchanged | MEASURED 2026-11-27 |

`QA: 0 findings (C/H/M/L) - 0 reproduced - not tested: F-25 (the one-field fetch after the hygiene branch is merged), the three open owner decisions that touch FSI`

