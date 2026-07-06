# dotfiles

My personal WSL Ubuntu setup, managed with Nix and home-manager. One repo, one command, and a fresh WSL install ends up configured the same way every time.

## What you get

Running the switch builds:

- Nix user packages (ripgrep, fd, fzf, jq, lazygit, Neovim, Hack Nerd Font)
- Shell (zsh, aliases, starship prompt)
- Git identity and GitHub CLI
- Editor (Neovim config, lazy.nvim)
- Terminal (WezTerm config, run from Windows-side WezTerm)
- Agent configs (Claude, Codex, opencode all share one `AGENTS.md`)
- WSL system config (`/etc/wsl.conf` with systemd, default user)
- Windows-side WezTerm loader (`C:\Users\<you>\.wezterm.lua`)

## Prerequisites

- WSL2 with Ubuntu 24.04 (Noble) or similar.
- Windows-side WezTerm installed.
- Sudo access inside WSL.

## Fresh-machine setup

On a brand new WSL Ubuntu install, from a bare clone of this repo:

```sh
git clone https://github.com/yashjeetbajwadev/dotfiles.git
cd dotfiles
```

Before you run it: open the config files and change the values listed in "Make it yours" below (username, home path, git identity, Windows username). `bootstrap.sh` applies the config to your machine, so do this first.

```sh
./bootstrap.sh
```

`bootstrap.sh` does these things, in order:

1. Installs apt prerequisites (`ca-certificates`, `curl`, `build-essential`, `zsh`).
2. Installs Determinate Nix, if it isn't already installed.
3. Symlinks this repo to `~/.dotfiles`. This has to happen before the first build, because `home.nix` points at config files through `~/.dotfiles`.
4. Runs the first `home-manager switch`.
5. Sets zsh as the login shell via `chsh`.
6. Writes `/etc/wsl.conf` and the Windows-side WezTerm loader (`C:\Users\<you>\.wezterm.lua`).

After that, `home-manager` exists and you're on the normal workflow below. Reopen your terminal (or run `wsl --shutdown` from Windows) so systemd and zsh take effect.

### Install Hack Nerd Font on Windows

WezTerm on Windows needs the font installed on the Windows side. From PowerShell:

```powershell
$zip = "$env:TEMP\hack.zip"
$dir = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"
Invoke-WebRequest "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/Hack.zip" -OutFile $zip
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Expand-Archive $zip -DestinationPath $dir -Force
Get-ChildItem "$dir\HackNerdFont*.ttf" | ForEach-Object { New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts" -Name "$($_.BaseName) (TrueType)" -Value $_.FullName -PropertyType String -Force | Out-Null }
```

### Validate without applying

Once Nix is installed (`bootstrap.sh` step 2 handles that), you can check that the config builds without touching your system:

```sh
nix flake check --no-build
nix build .#homeConfigurations.yashjeetbajwa.activationPackage --dry-run
```

## Daily use

Edit the config files in place, then apply:

```sh
./rebuild.sh
```

That's it. No separate build-and-copy step.

## Make it yours

This repo is mine. If you clone it, change these before you run `bootstrap.sh`:

- **Username and home path** `yashjeetbajwa` / `/home/yashjeetbajwa`, in `flake.nix:26` and `home.nix:8-9`.
- **Git identity**, in `home.nix:48-51` (`yashjeetbajwadev` / `12064392+yashjeetbajwadev@users.noreply.github.com`).
- **Home-manager configuration name** `yashjeetbajwa`, in `flake.nix:26` and `rebuild.sh:7` (the `#yashjeetbajwa` at the end of the flake reference). Both have to match.
- **WSL distro name**, in `bootstrap.sh` (the `WSL_DISTRO` default, used to build the Windows WezTerm loader path). Defaults to `Ubuntu`.
- **Windows username**, in `bootstrap.sh` (auto-detected via `cmd.exe`; override with `WIN_USER=...` if detection fails).
- **Default WSL user**, in `wsl.conf` and `flake.nix`/`home.nix` (must match the Linux username).

**Heads-up:**

- `home/AGENTS.md` is my personal agent policy, and `home.nix` installs it for Claude, Codex, and opencode. If you clone this repo, you'd silently inherit my agent instructions - edit or delete `home/AGENTS.md` if you don't want that.
- The `cc` and `co` shell aliases in `home.nix` are high-agency shortcuts: `claude --dangerously-skip-permissions` and `codex --full-auto`. They're convenient for me, but know what they do before you use them.

## Repo tour

- `flake.nix` - the entry point. Wires up nixpkgs, home-manager, and herdr, and declares the `yashjeetbajwa` home configuration.
- `home.nix` - user-level config: shell, git, gh, packages, and the symlinks described below.
- `bootstrap.sh` - first-run setup. Installs prerequisites, Nix, and applies the config.
- `rebuild.sh` - re-applies the config after the first switch. Run this every time you make a change.
- `wsl.conf` - system-level WSL config (systemd, default user), copied to `/etc/wsl.conf` by `bootstrap.sh`.
- `home/` - the actual config files that get symlinked into place (Neovim, WezTerm, herdr, Claude settings, the shared `AGENTS.md`).

## How the symlinks work

The files under `home/` are the real files - editing them here is editing your live config, no rebuild needed to see the change in your editor. `home.nix` uses `mkOutOfStoreSymlink` to point paths like `~/.config/nvim` straight at `home/.config/nvim` in this repo (via `~/.dotfiles`), so the two never drift out of sync. You only run `./rebuild.sh` when you change something that isn't just a symlinked file, like a package list.

The WezTerm config is a special case: it lives in the repo and is symlinked into `~/.config/wezterm` inside WSL, but the actual WezTerm process runs on Windows. Because the `\\wsl$\` share does not follow symlinks, a tiny loader at `C:\Users\<you>\.wezterm.lua` does a `dofile` directly at the real file inside this repo (not the symlink). `bootstrap.sh` writes this loader for you using the repo's actual path, so it stays correct no matter where you clone.

## Notes

- The first time you launch `nvim`, it bootstraps [lazy.nvim](https://github.com/folke/lazy.nvim) by cloning plugins from GitHub. That needs network access once; after that it's offline.
- `bootstrap.sh` writes `/etc/wsl.conf` with `systemd=true`. If your WSL didn't have systemd enabled, run `wsl --shutdown` from Windows and reopen to apply.

## License

This repo is licensed under MIT No Attribution. See `LICENSE`.
