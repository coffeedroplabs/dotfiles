# repo agent instructions

- This is a Nix + home-manager dotfiles repo for WSL Ubuntu. Keep it minimal.
- Never use the em dash. Use plain dash - instead.
- When writing commit messages, NEVER auto-add your agent name as co-author.
- Never manually modify CHANGELOG.md files or any files that are marked as auto-generated.
- Do not edit `home/.config/herdr/*.log` or `home/.config/herdr/session.json`. They are runtime artifacts, gitignored, and not config.
- `home/AGENTS.md` is the user-level agent policy symlinked into Claude, Codex, and opencode. The root `AGENTS.md` (this file) is for agents working on this repo itself.
- After changing `home.nix` or `flake.nix`, verify with `nix flake check --no-build` before declaring done.
- The WezTerm config at `home/.config/wezterm/wezterm.lua` runs on Windows-side WezTerm via a `dofile` loader in `C:\Users\<user>\.wezterm.lua`. Keep `default_prog` as `wsl.exe`. Do not add macOS-only options.
