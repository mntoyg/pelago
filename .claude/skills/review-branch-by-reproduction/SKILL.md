---
name: review-branch-by-reproduction
description: Review a teammate's or another AI's branch by reproducing its claims (export the branch, run the suite, mutate guards on copies, re-measure external facts) and record the result in TASK.md before any merge. Use when a branch is reported done.
---

# Review a branch by reproduction (Pelago Asia PM loop)

Verified on this project (REVIEW-001 to REVIEW-007, 2026-11-26/27). A report from another chat is a claim until you re-run it.

## Steps

1. **Scope first.** `git fetch origin`, then `git log --oneline main..origin/<branch>` and `git diff --stat main origin/<branch>`. Anything outside the
   task's folders is a finding. Check a trial merge: `git merge-tree --write-tree --name-only origin/main origin/<branch>` (exit 0 = no conflicts).
2. **Export, do not check out.** Extract into an empty scratch folder: `git archive origin/<branch> | tar -x -C <scratch>/<name>`. Run Python from there with
   its own `backend/` as the working directory so you test that tree, not another one.
3. **Run the suite.** Quote the counts (passed / skipped). A skipped database test proves nothing: run it on a throwaway PostGIS
   (`postgis/postgis:16-3.7`, bind `127.0.0.1`, random password kept out of the repo, `PELAGO_REQUIRE_DB=1`, `PELAGO_TEST_ADMIN_URL`), and remove the
   container and the password file afterwards. Docker Desktop must be running.
4. **Mutate on copies.** For every new guard, copy the exported tree, replace one expression (`str.replace(old, new, 1)`), run the suite with `-x`, record the
   file hash before and after, and expect RED in a test that names the cause. A mutation that fails by `NameError` proves nothing: build it so the
   code still runs. GREEN means the guard has no test: report it, with its severity and who could trigger it.
5. **Re-measure what the report asserts about the outside world** (a dataset id, a licence page, a hash) with a small request; label it MEASURED with the date.
   Numbers that need someone's private cache stay REPORTED.
6. **Search the neighbours.** When you find one defect, grep every caller of the changed function. (Example: a new allowlist argument broke a second caller that
   defaulted to the old function; the tests had injected a fake.)
7. **Record before merging.** In `TASK.md`: a row in section 3, the checklist boxes, a `REVIEW-00N` block with a verdict, a table of checks labelled
   MEASURED / RECORDED / REPORTED / READ, findings with severity, and the `QA:` line. Commit on a local branch, name files when staging, then ask the owner
   one question: merge and push?
8. **Merge only on the owner's word.** `git merge --ff-only` where possible (otherwise a merge commit), run the suite on the merged tree, `git push origin main`,
   then show that `git ls-remote origin main` equals `git rev-parse HEAD`. Never push to `upstream`, never force-push.

## Pitfalls seen

- Git Bash rewrites `/tmp/...` arguments to `docker exec`; set `MSYS_NO_PATHCONV=1`.
- A running Claude chat's scratch folders are off limits; ask for the evidence in the report instead.
- A hidden browser pane throttles timers; freeze the render loop before measuring a screen.
