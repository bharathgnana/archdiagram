# Agent instructions

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
