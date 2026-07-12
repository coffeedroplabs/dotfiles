# global agent instructions

- Never use the em dash "-". Use plain dash "-" instead
- When writing commit messages, NEVER auto-add your agent name as co-author
- Never manually modify CHANGELOG.md files or any files that are marked as auto-generated
- When making technical decisions, do not give much weight to development cost.
  Instead, prefer quality, simplicity, robustness, scalability, and long term maintainability.
- When doing bug fixes, always start with reproducing the bug in an E2E setting as closely aligned with how an end user would experience it as possible.
  This makes sure you find the real problem so your fix will actually solve it.
- When end-to-end testing a product, be picky about the UI you see and be obsessed with pixel perfection.
  If something clearly looks off, even if it is not directly related to what you are doing, try to get it fixed along the way.
- Apply that same high standard to engineering excellence: lint, test failures, and test flakiness.
  If you see one, even if it is not caused by what you are working on right now, still get it fixed.

## Deliberate decisions in this repo

- `homebrew.onActivation.cleanup = "zap"` in `configuration.nix` is intentional. It forces declaring every Homebrew package in the Nix config. Do not soften it to `uninstall` or `none`.
- The config files under `home/` are symlinked (not copied) via `mkOutOfStoreSymlink`. Editing them here edits live config without a rebuild.
- `home/AGENTS.md` is shared across Claude, Codex, and opencode via symlinks in `home.nix`.
- The `cc` and `co` shell aliases are high-agency shortcuts (`claude --dangerously-skip-permissions` and `codex --full-auto`). They are deliberate.
- Git identity is not set declaratively. Set it manually with `git config --global`.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
