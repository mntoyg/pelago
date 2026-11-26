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
- Hosting: the front end is on Vercel; decide whether the backend is Vercel functions or a separate service.

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

## 6. Open questions for the owner

1. ~~Merge `refactor/frontend-structure` into `main`~~ — done 2026-11-26. ~~Merge the first docs~~ — done.
2. The build guide (G) and the function spec (S) give different phases for fuel/route, admin dashboard, fish ID, fish
   price, bloom warning, SOS, voice and go/no-go (table in `ARCHITECTURE.md`, A3). Which one is authoritative? The PM
   used S, the newer one.
3. Is this hackathon entry the front-end prototype, the backend/AI core (Part A, Phase 0–1), or both? It decides what
   the next tasks are.
4. Commercial or non-profit (route A or B in the guide)? It decides which data sources are allowed; the prototype's
   Open-Meteo use is non-commercial only.
5. Backend: which language and host? Is a database allowed, and which one? (The guide recommends Python, FastAPI,
   PostgreSQL + PostGIS, Redis; none of it is decided for us.)
6. AI: which model approach for fish ID (hosted API, open model, on-device), and is there a data set?
7. Is the hackathon deadline known? The PM will plan backwards from it.
8. Do you want the reference documents (the three Thai files) stored in this public repository? The PM kept them out and
   only summarised them.

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
