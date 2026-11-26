# CLAUDE.md — notes for Claude Code sessions

Read [`AGENTS.md`](AGENTS.md) first (rules, remotes, conventions, how to verify, how to report) and
[`TASK.md`](TASK.md) (the current plan). This file only adds what is specific to Claude Code.

## Seats

- **PM chat**: plans, assigns, reviews, keeps `TASK.md`. Does not implement large changes itself and does not edit the
  working tree while a SWE chat is working in it.
- **"Pelago SWE NN" chats**: implement exactly one assigned task on its own branch, verify it themselves, push to
  `origin`, report back. Out-of-scope findings go in the report; they are not fixed on the side.
- Language: talk to the owner in Thai; write code, comments, commit messages and repo documents in English.

## Working rules

1. Start by reading `AGENTS.md`, `TASK.md` and the part of `README.md` ("Project structure") you need. The source is
   small and split into modules under `src/`; open the one file you need instead of the whole tree.
2. Keep a task list for anything that edits files or runs more than one command, and update it as steps finish.
3. Verify before you claim. Run the checks in `AGENTS.md` section 7 yourself and quote the output. A teammate's or
   another chat's report is a claim until you re-run it. A local model's output is a draft, never evidence, and
   verification is never delegated to a local model.
4. Stage files by name (`git add <file>`), never `git add -A` or `git add .`. Throwaway files such as
   `.claude/launch.json` (used to start a preview server) must not be committed; delete them when you are done.
5. Commit messages end with the attribution line your environment requires. Push with the remote named, then
   print `git ls-remote origin <branch>` and report that SHA. Never push to `upstream`, never push to `main` without
   the owner's word, never force-push.
6. Do not weaken permission modes, hooks or safety settings, and do not touch user-level configuration (`~/.claude`).

## Browser checks (built-in browser pane)

- Serve with `python -m http.server <port>` (the preview tool can start it from `.claude/launch.json`). ES modules do
  not load from `file://`; a `file://` page in the pane is a static snapshot and proves nothing about the app.
- Compare against a baseline by extracting the old commit with `git archive <sha>` into a scratch folder and serving
  it on another port. Compare computed values, not only screenshots.
- A hidden pane throttles timers, and two live globes in one page can hang the tab. Freeze the render loop and run
  one screen per call; if a call times out, close the tab and reopen it before retrying.
- Read the console and the network list after loading. Zero errors and all local files 200 is the bar.

## Handing work between chats

- A brief names the branch, the files or area, the constraints, what "done" looks like, and the report format
  (`AGENTS.md` section 8). One writer per folder at a time.
- Send follow-ups to the chat that already has the context instead of starting a new one.
- If the task or its scope looks wrong, stop and tell the PM before doing it.
