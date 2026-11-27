# CURSOR.md — notes for the Cursor editor and agent

The shared rules for every AI agent in this repository are in [`AGENTS.md`](AGENTS.md). Read it first; this file only adds
what is specific to Cursor. Do not copy rules from `AGENTS.md` here, so the two cannot drift apart.

- Project context: [`README.md`](README.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), current work in [`TASK.md`](TASK.md),
  requirements in [`PRD.md`](PRD.md), interfaces in [`API.md`](API.md).
- No Cursor-specific settings exist yet (no `.cursor/` folder, no Cursor rules). TBD: the owner may add some.
- The project path contains a space (`D:\Hackathon\CodeAgis 2026\Project`): quote it in every terminal command.
- Stage files by name; never `git add -A`. Never push to `upstream` or to `main` without the owner's word
  (`AGENTS.md` section 3).
