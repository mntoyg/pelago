# Copilot instructions — Pelago Asia

The rules for every AI agent are in [`AGENTS.md`](../AGENTS.md); follow it. This file is a short pointer and adds nothing
that differs from it.

Essentials (same as `AGENTS.md`):

- Static front end in `src/` (ES modules, no build step, no new dependencies without the owner's approval). Python backend in
  `backend/` (FastAPI and PostgreSQL/PostGIS are the plan; see `ARCHITECTURE.md`).
- All FSI values and spots shown by the prototype are demo data and the UI says so. Do not present demo data as real and do not
  change what the UI promises.
- Anything that decides "go / don't go" must show its inputs and limits. Unknown legal or sea-state data means "do not recommend".
- No secrets, tokens, `.env` files or raw data dumps in this public repository.
- Verify before you claim: run the checks in `AGENTS.md` section 7 and the backend tests (`backend/README.md`), and remove a guard once to
  confirm its test goes red.
- Code, comments, commit messages and repository documents are in English.
