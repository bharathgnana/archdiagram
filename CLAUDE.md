# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Cursor↔Claude live-review bridge

A reviewer running in **Cursor** watches the executing agent (**Claude**, in the
terminal) and steers it *without interrupting the chat*, via **bridge files**. This
convention works in every repo (a user-scope hook activates it automatically).

- **Bridge files are named `suggestions_*.md`** — e.g. `plans/suggestions_NN_<slug>.md`
  beside a plan, or a top-level `suggestions_<topic>.md`. The **Cursor reviewer owns**
  them (creates / rewrites / erases). The executor never deletes a reviewer's directives.
- **Claude polls** the relevant `suggestions_*.md` before starting a task and after
  every task/checkbox.
- **`## Open Directives` (`- [ ]`) are binding.** On conflict with the plan/spec body,
  the directive wins (the reviewer has fresher context).
- **Claude acknowledges** under `## Claude Acknowledgements`, ticking `- [ ]` → `- [x]`
  and referencing the code/tests that close each one. Blockers are surfaced there.
- **Automated — no manual nudge.** A user-scope `Stop` hook
  (`~/.claude/hooks/suggestions_watch.py`, wired in `~/.claude/settings.json`) runs at
  the end of every turn: if a `suggestions_*.md` changed and still has unchecked
  directives, it blocks the stop and re-injects them. It baselines on first sight,
  guards against loops, and fails open. Hooks load at session start, so restart an
  in-flight session (or run `/hooks`) if the bridge does not fire.
- **When you are the Cursor reviewer:** write `suggestions_*.md` with a
  `## Open Directives` list of short, testable `- [ ]` items plus a
  `## Claude Acknowledgements` heading, and reference the bridge file from the plan/spec.
