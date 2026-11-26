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
| Backend, AI | not started | waiting for the owner's decisions in section 6 |

## 3. Done

| ID | What | Evidence |
| --- | --- | --- |
| TASK-000 | Forked `orapin67855-coder/pelago` to `mntoyg/pelago`, cloned, set `origin` and `upstream` | MEASURED 2026-11-26: `git remote -v`, GitHub shows `isFork: true` |
| TASK-001 | Fixed `index.html` asset paths (`css/styles.css`, `js/app.js` did not exist, so the page had no styles or script) | MEASURED 2026-11-26: after the fix `styles.css` and `app.js` return 200 and the page renders. Pushed as `db85230` |
| TASK-002 | Front-end restructure by SWE 01: `app.js` split into `src/` ES modules, `styles.css` sectioned with CSS variables, README structure section. UI and features unchanged | Reviewed by the PM, see REVIEW-001. Merged into `main` at `86519dd` (fast-forward, pushed to `origin`, MEASURED 2026-11-26: `git ls-remote origin main` = `86519dd`) |
| TASK-006 | `ARCHITECTURE.md` and a new `README.md` from the team's three reference documents (build guide 2026-11-21, function spec 2026-11-24, data sources 2026-11-25), plus a gap analysis of this prototype against them | MEASURED 2026-11-26: the PM read all three documents, including the two figures that have no text layer (system layers, 5-phase plan), and checked each statement about the prototype against the code. While doing so it found and fixed two wrong lines the PM had written earlier in `AGENTS.md` and `TASK.md`: the catch journal does not save anything (only price reports and pins are saved in `localStorage`). Merged into `main` on 2026-11-26 |
| TASK-007 | Backend API contract, draft PostGIS schema and service layout (design only) by the first backend seat | Reviewed by the PM, see REVIEW-002. Merged into `main` on 2026-11-26 (fast-forward from `feature/backend-contract` `93b82e0`). Root `.gitignore` now ignores `.env*` and key files; new `.vercelignore` keeps `backend/` and env files out of CLI deploys |
| TASK-008 | Backend daily ingest for `th-chonburi-coast` by the second backend seat: dry run of the public sources, area config, one fetcher per source behind a swappable interface, aggregation onto the 0.05 degree grid, writer, 101 tests, mutation log | Reviewed by the PM, see REVIEW-003. Branch `feature/backend-ingest` at `73d2f00`; merge pending the owner's go-ahead |

## 4. Next up

### 4.0 Progress checklist (`[x]` = done and checked by the PM, `[ ]` = not done)

Updated 2026-11-26. "Checked" means the PM reproduced the evidence, not only read the seat's report (REVIEW-001 to REVIEW-003).

Foundations

- [x] Fork, clone, remotes (`origin`, `upstream`); asset-path fix (TASK-000, TASK-001)
- [x] Front-end restructure into `src/` modules, UI unchanged (TASK-002, REVIEW-001)
- [x] Agent guides and this board (`AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `TASK.md`)
- [x] `ARCHITECTURE.md` and `README.md` from the three reference documents (TASK-006)
- [x] Owner decisions D1 to D11 recorded (section 6)
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
- [ ] Land mask and EEZ mask, and the test "no recommended spot in a forbidden cell" (deliverable 3)
- [ ] FSI v1 on the server: six sub-scores, confidence, explanation (deliverable 4)
- [ ] API (FastAPI) reading the database (deliverable 1)
- [ ] Back-test report (deliverable 5)
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
- [ ] `.gitattributes` with `eol=lf` for `backend/config/**/*.json`, or hash a canonical JSON, so `config_sha256` is the same on every machine (F-7)
- [ ] Use the canonical ERDDAP dataset ids and do not follow redirects blindly (F-9)
- [ ] Fix the two lines that still say "owner may remove it" about the NOAA-20 fallback (D11)
- [ ] Reword `wx_issued_at` in the contract: it is the retrieval time, not a forecast issue time (F-10)

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
    water cells), labelled as a past date. Which one?

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
