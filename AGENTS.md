# AGENTS.md

Guidance for AI coding agents (Cursor, Claude Code/Desktop, Codex, etc.) using
this repository.

## What this repo does

`archdiagram` converts a JSON architecture or workflow **spec** into an editable
diagram. Service nodes use official vendor icons (Azure, AWS, GCP, Kubernetes);
workflow nodes use process, decision, data, start, and end shapes. Swim lanes
show ownership. Exports include `.pdf`, `.drawio`, `.vsdx`, `.svg`, `.html`, and
editable `.pptx`.

Your job as an agent: translate the user's natural-language architecture into
the JSON spec, then render it.

## Two ways to use it

1. **Skill** - read [skill/SKILL.md](skill/SKILL.md) and follow it. It contains
   the spec schema, catalog lookup, and render commands.
2. **MCP server** - run `python -m mcp_server.server` and call the tools
`validate_spec`, `render_diagram`, `search_catalog`, `list_catalog`,
`choose_template`, and `get_diagram_template`. A sample
   client config is in [examples/mcp.json](examples/mcp.json).

## Quick start

```bash
python -m tools.download_icons            # fetch vendor icons into ./icons
cd node && npm install && cd ..           # optional: PDF + crisp raster icons
python -m archdiagram.cli catalog search "kubernetes"
python -m archdiagram.cli render spec.json -f pdf -o out/arch.pdf
python -m archdiagram.cli templates list
python -m archdiagram.cli render examples/workflow_swimlane.json -f pptx -o out/workflow.pptx
```

## Conventions

- Core engine is **stdlib-only** (no third-party Python deps). Keep it that way.
- The `mcp` SDK is allowed **only** under `mcp_server/`.
- Node (`@resvg/resvg-js`, `pdfkit`, `svg-to-pdfkit`) is optional and confined to
  `node/` + `archdiagram/rasterize/`.
- Vendor icons are **not committed**; they are fetched by `tools/download_icons.py`.
- Tests use stdlib `unittest`: `python -m unittest discover -s tests`.


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

## Agent sync

Claude Code, Codex, Gemini CLI, Cursor, and VS Code Copilot share one skill library. Keep this section identical in every instruction file.

The library is `C:\Users\Bharath\globalskills`, private repo `bharathgnana/globalskills`.

- Personal skills are stored in `globalskills/shared`.
- Project skills are stored in `globalskills/projects/<project>/`. This repository's `.claude/skills`, `.codex/skills`, `.cursor/skills`, and `.agents/skills` directories point at that tree.

When this guidance changes, update all of these files together:

- `CLAUDE.md` (Claude Code)
- `AGENTS.md` (Codex)
- `GEMINI.md` (Gemini CLI)
- `.github/copilot-instructions.md` (VS Code Copilot)

Save skills only under `globalskills`.
