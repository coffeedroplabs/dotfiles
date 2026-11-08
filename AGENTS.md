# repo agent instructions

- This is a Nix + home-manager dotfiles repo for WSL Ubuntu and macOS. Keep it minimal.
- Never use the em dash. Use plain dash - instead.
- When writing commit messages, NEVER auto-add your agent name as co-author.
- Never manually modify CHANGELOG.md files or any files that are marked as auto-generated.
- Do not edit `home/.config/herdr/*.log` or `home/.config/herdr/*.sock` or `home/.config/herdr/session.json`. They are runtime artifacts, gitignored, and not config.
- `home/AGENTS.md` is the user-level agent policy symlinked into Claude, Codex, and Antigravity. The root `AGENTS.md` (this file) is for agents working on this repo itself.
- After changing `home.nix` or `flake.nix`, verify with `nix flake check --no-build` before declaring done.
- `configuration.nix` is macOS-only (nix-darwin system config). `wsl.conf` is Linux-only. `home.nix` is shared and branches on `pkgs.stdenv.hostPlatform.isDarwin`.
- `homebrew.onActivation.cleanup = "zap"` in `configuration.nix` is intentional. It forces declaring every Homebrew package in the Nix config. Do not soften it to `uninstall` or `none`.
- The WezTerm config at `home/.config/wezterm/wezterm.lua` branches on `wezterm.target_triple` for Windows (wsl.exe default_prog), macOS (blur + RESIZE), and Linux (TITLE | RESIZE). On Windows-side WezTerm, a `dofile` loader in `C:\Users\<user>\.wezterm.lua` reads it from the WSL filesystem.

## Deliberate decisions in this repo

- `homebrew.onActivation.cleanup = "zap"` in `configuration.nix` is intentional. It forces declaring every Homebrew package in the Nix config. Do not soften it to `uninstall` or `none`.
- The config files under `home/` are symlinked (not copied) via `mkOutOfStoreSymlink`. Editing them here edits live config without a rebuild.
- `home/AGENTS.md` is shared across Claude, Codex, and Antigravity via symlinks in `home.nix`.
- The `cc` and `co` shell aliases are high-agency shortcuts (`claude --dangerously-skip-permissions` and `codex --full-auto`). They are deliberate.
- Git identity is not set declaratively. Set it manually with `git config --global`.
- The `deepseek-executor` MCP server is registered by `home.activation.deepseekExecutorMcp` in `home.nix`. `~/.claude.json` is Claude's mutable state, so change the spec there instead of running `claude mcp add` by hand. Server tests: `uv run --script home/.config/claude-mcp/deepseek-executor/test_server.py`; after changing its dependencies, `uv lock --script server.py`. The delegation workflow is the `/deepseek-run` skill in `home/.claude/skills/deepseek-run/`. Each executor call appends a line to `~/.local/state/deepseek-executor/calls.jsonl` (outcome, tokens, effort, duration).

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
