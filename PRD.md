# PRD.md — Pelago Asia product requirements

Status: **skeleton written 2026-11-27 by the PM** from `AGENTS.md`, `ARCHITECTURE.md` and `TASK.md`. It records what the team and the
owner have decided; anything marked **TBD** is not decided and needs the owner. The three Thai reference documents (build guide
2026-11-21, function spec 2026-11-24, data sources 2026-11-25) are not stored in the repository (decision D7); `ARCHITECTURE.md`
summarises them, and the function spec wins where they differ (D2).

## 1. Problem

Small-scale fishers in Asian waters have little accessible, Thai-language guidance on where fish are likely to be, whether the sea is safe
to go out in, and what a trip costs in fuel. Public satellite and forecast data exist but are not packaged for them.

## 2. Users

- Primary: Thai-speaking small-scale fishers (boat class `small` in the UI this week, decision D10).
- Secondary: hackathon judges and the team. TBD: other user groups and countries (out of scope this week).

## 3. Goals (this submission, about 2026-12-03; exact date TBD)

1. A Thai-language web prototype with a fish-suitability index (FSI), sea conditions, fuel cost and small tools (decision D1).
2. A backend and AI core for one area, `th-chonburi-coast`: daily ingest, server-side FSI v1 with confidence and explanation, a safety
   filter, a pick step, an API, and a back-test report (D1, D4, D6).
3. Honesty: demo data is labelled, unknown data means "do not recommend", legal incompleteness is labelled, and no accuracy is claimed
   that has not been measured.

## 4. Non-goals this week

Real fish identification (the screen stays a labelled mock-up, D6); chat apps and sign-up; tides; catch log and price server; mangroves;
admin dashboard; official-warning feed; other countries or areas; any claim that FSI predicts catches (no catch logs exist).

## 5. Requirements

| ID | Requirement | Status (2026-11-27) | Where |
| --- | --- | --- | --- |
| R1 | The prototype shows the globe, FSI spots and the small tools, with demo data labelled | built (prototype) | `src/`, TASK-002 |
| R2 | Daily ingest of sea-surface temperature, chlorophyll, depth, waves and wind onto a 0.05 degree grid for the area | built, reviewed | TASK-008 |
| R3 | FSI v1 on the server with sub-scores, confidence and a per-cell explanation | built, reviewed | TASK-009 |
| R4 | Safety filter: land mask, EEZ with a 5 km buffer, sea state, "unknown means do not recommend"; other legal layers not loaded, so the area is labelled trial | built, reviewed, merged | TASK-010 |
| R5 | Pick 3 to 5 spots at least 10 km apart (D8) | built, reviewed, merged | TASK-010 |
| R6 | A read-only HTTP API serving the spots, areas, freshness and health | not built | `backend/API_CONTRACT.md`, TASK 4.3 CX-2 |
| R7 | The front end reads the API; only a network error or a 5xx falls back to the labelled demo path, never after a 200 (D9) | in progress | TASK 4.5 FE-1 |
| R8 | A back-test of coverage and sanity checks, stating that it is not evidence of accuracy | built, partial | TASK-009, REVIEW-004, REVIEW-006 |
| R9 | A daily scheduled run and a deployment (database host, API host) | not built; needs owner accounts | TASK 4.0 |
| R10 | A red-team review pass and a demo script | not done | TASK 4.0 |

## 6. Acceptance criteria (the ones that can be checked today)

- No recommended spot is ever in a land, outside-EEZ, unknown-legal, red-sea or no-forecast cell: the pick step and the database
  constraints are tested on a real PostGIS (`backend/tests/test_mask_pick_db.py`, `backend/db/tests/schema_test.sql`).
- Spots are at least 10 km apart by great-circle distance (`backend/tests/test_pick_select.py`).
- With no API configured the front end behaves as before (the 12 screens compare equal to the baseline).
- Every guard above has a test that goes red when the guard is removed (mutation logs in `backend/docs/`).

## 7. Open questions

All open owner decisions are in `TASK.md` section 6 (submission date and format, where FastAPI runs, the legal-incomplete label, empty
chlorophyll, the front weight, more back-test budget). They are not repeated here so the two files cannot disagree.
