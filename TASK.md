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

## 4. Next up

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

### Still open

1. Exact submission date and format (a live demo? a video? a pitch?). The plan assumes about 2026-12-03.
2. Where the FastAPI service runs, and who creates that account (section 4.1, owner actions).
3. **Legal data gap.** The guide's rule is "no complete legal-zone data = do not recommend". For the Chonburi coast we
   will have land and EEZ but **not** closed seasons or protected zones this week. Options: show spots clearly marked
   "trial: legal layers incomplete, not for real use" (PM's proposal, matches the prototype's honest labelling), or
   show no spots for the area. Which one for the demo?
4. Demo area: the Chonburi coast (proposed), or another?
5. Global Fishing Watch token for the back-test: will the owner register one (internal use only)?
6. Repository layout for the backend: a `backend/` folder in this repository (PM's proposal; Vercel keeps serving the
   static front end), or a separate repository.
7. Tell the teammate who owns `upstream` (TASK-005) before they edit `app.js`.

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
