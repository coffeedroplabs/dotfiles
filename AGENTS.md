# repo agent instructions

- This is a Nix + home-manager dotfiles repo for WSL Ubuntu and macOS. Keep it minimal.
- Never use the em dash. Use plain dash - instead.
- When writing commit messages, NEVER auto-add your agent name as co-author.
- Never manually modify CHANGELOG.md files or any files that are marked as auto-generated.
- Do not edit `home/.config/herdr/*.log` or `home/.config/herdr/*.sock` or `home/.config/herdr/session.json`. They are runtime artifacts, gitignored, and not config.
- `home/AGENTS.md` is the user-level agent policy symlinked into Claude, Codex, and opencode. The root `AGENTS.md` (this file) is for agents working on this repo itself.
- After changing `home.nix` or `flake.nix`, verify with `nix flake check --no-build` before declaring done.
- `configuration.nix` is macOS-only (nix-darwin system config). `wsl.conf` is Linux-only. `home.nix` is shared and branches on `pkgs.stdenv.hostPlatform.isDarwin`.
- `homebrew.onActivation.cleanup = "zap"` in `configuration.nix` is intentional. It forces declaring every Homebrew package in the Nix config. Do not soften it to `uninstall` or `none`.
- The WezTerm config at `home/.config/wezterm/wezterm.lua` branches on `wezterm.target_triple` for Windows (wsl.exe default_prog), macOS (blur + RESIZE), and Linux (TITLE | RESIZE). On Windows-side WezTerm, a `dofile` loader in `C:\Users\<user>\.wezterm.lua` reads it from the WSL filesystem.
