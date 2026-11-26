# CODEX.md — notes for Codex sessions

Codex reads [`AGENTS.md`](AGENTS.md) automatically; it holds the rules, remotes, conventions, verification steps and
report format that apply to you. Read [`TASK.md`](TASK.md) for the current plan. This file only adds what is specific
to Codex.

## Environment

- Windows 11, PowerShell. The project path contains a space (`D:\Hackathon\CodeAgis 2026\Project`): always quote it.
- Tools you can rely on: `git`, `node` (use `node --check <file>` for syntax), `python` (`python -m http.server <port>`
  as the static server), `tar` (for `git archive <sha> | tar -x -C <dir>`).
- There is no package manager step and no test runner. Do not add `package.json`, a bundler or dependencies without the
  owner's approval.

## Working rules

1. Keep context small. The code is split into modules under `src/`; read `README.md` ("Project structure") and then only
   the file or two you need.
2. Do the work yourself and verify it yourself. Tests that assert "refused" or "no error" prove nothing if several
   guards would produce the same result: after you add a guard or a test, remove the guard once, confirm the check
   goes red, restore it from a saved copy, and say so in the report.
3. Network may be restricted in your sandbox. The page's live-data calls (NASA GIBS, Esri, NOAA ERDDAP, Open-Meteo)
   can then fail; `fetchSpotSignal` records a failed source in `sourceStatus` instead of throwing. If you cannot reach
   the network, say which checks you could not run rather than reporting them as passed.
4. Localhost sockets may also be blocked in a sandbox. If you cannot serve and load the page, report that as "not
   tested: page load", and still run `node --check` and the static handler check.
5. Commit on your own branch with English messages, push with the remote named (`git push origin <branch>`), and report
   `git ls-remote origin <branch>`. Never push to `upstream` or to `main`, never force-push, never bypass hooks.
6. Stage files by name. Do not commit scratch files, logs, raw model output, `.env` files or anything under a user
   profile folder.
7. Anything found outside your assigned scope goes in the report with `file:line` and a severity, not into the diff.

## Report

Use the format in `AGENTS.md` section 8: branch, pushed SHA, commits, what changed, evidence labelled
MEASURED / RECORDED / REPORTED, findings not fixed, and what you did not test. Reports to the owner are in Thai (code
and identifiers stay in English).
