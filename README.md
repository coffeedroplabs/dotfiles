# dotfiles

My personal setup for WSL Ubuntu and macOS, managed with Nix. One repo, one command, and a fresh machine ends up configured the same way every time.

## What you get

Running the switch builds:

- Nix user packages (ripgrep, fd, fzf, jq, lazygit, Neovim, Hack Nerd Font)
- Shell (zsh, aliases, starship prompt)
- GitHub CLI
- Editor (Neovim config with rose-pine moon theme, lazy.nvim)
- Terminal (WezTerm config with rose-pine moon theme, branched per platform)
- Agent configs (Claude, Codex, opencode all share one `AGENTS.md`)
- On macOS: system settings (dark mode, key repeat, dock, Finder, trackpad), Homebrew apps (casks and CLI tools)
- On WSL: system config (`/etc/wsl.conf` with systemd, default user), Windows-side WezTerm loader

## Prerequisites

- macOS: Apple Silicon Mac by default. Intel Mac: change `hostPlatform` in `configuration.nix` to `x86_64-darwin`.
- WSL: WSL2 with Ubuntu 24.04 (Noble) or similar, Windows-side WezTerm installed, sudo access inside WSL.
- Agent CLIs (optional, for the `cc`/`co` aliases): `claude` and `codex` are not managed by this repo. Install them separately, e.g. `npm i -g @anthropic-ai/claude-code @openai/codex`. The repo only manages their config files.

## Fresh-machine setup

On a brand new machine, from a bare clone of this repo:

```sh
git clone https://github.com/CoffeeDrop-Studio/dotfiles.git
cd dotfiles
```

Before you run it: review "Make it yours" below.
Change the host label or CPU architecture if needed, and read the Homebrew cleanup warning.
`bootstrap.sh` applies the config to your machine, so do this first.

```sh
./bootstrap.sh
```

`bootstrap.sh` detects your OS and branches:

**macOS** does four things, in order:

1. Installs Determinate Nix, if it isn't already installed.
2. Symlinks this repo to `~/.dotfiles`.
3. Checks the `user` configured in `flake.nix` against your actual macOS username, and offers to fix it for you if they differ.
4. Runs the first `darwin-rebuild switch`. It fetches the `darwin-rebuild` tool from the nix-darwin 26.05 release branch, then applies this repo's locked flake config.

After that, `darwin-rebuild` exists and you're on the normal workflow below.

**WSL Ubuntu** does six things, in order:

1. Installs apt prerequisites (`ca-certificates`, `curl`, `build-essential`, `zsh`).
2. Installs Determinate Nix, if it isn't already installed.
3. Symlinks this repo to `~/.dotfiles`. This has to happen before the first build, because `home.nix` points at config files through `~/.dotfiles`.
4. Runs the first `home-manager switch`. It fetches the `home-manager` tool from the home-manager 26.05 release branch, then applies this repo's locked flake config.
5. Sets zsh as the login shell via `chsh`.
6. Writes `/etc/wsl.conf` and the Windows-side WezTerm loader (`C:\Users\<you>\.wezterm.lua`).

After that, reopen your terminal (or run `wsl --shutdown` from Windows) so systemd and zsh take effect.

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

Once Nix is installed (`bootstrap.sh` handles that), you can check that the config builds without touching your system:

```sh
nix flake check --no-build
```

On macOS you can also dry-run the darwin build:

```sh
nix build .#darwinConfigurations.mac.system --dry-run
```

On WSL:

```sh
nix build .#homeConfigurations.yashjeetbajwa.activationPackage --dry-run
```

## Daily use

Edit the config files in place, then apply:

```sh
./rebuild.sh
```

That's it. No separate build-and-copy step.

## Make it yours

This repo is mine.
If you clone it, review these before you run `bootstrap.sh`:

- **Username**: run `./bootstrap.sh` (it detects your macOS username and offers to set it) OR change the single `user = "yashjeetbajwa"` line in `flake.nix`.
  Everything else (`configuration.nix`, `home.nix`, home directory paths) is threaded from that one variable.
- **Host label** `"mac"`, in three places: `flake.nix` (the `darwinConfigurations."mac"` name), `rebuild.sh:5` (the `#mac` at the end of the flake reference), and `bootstrap.sh`'s first-switch command (also `#mac`).
  All three have to match.
- **CPU architecture**, `hostPlatform` in `configuration.nix` (see Prerequisites above).
- **WSL distro name**, in `bootstrap.sh` (the `WSL_DISTRO` default, used to build the Windows WezTerm loader path). Defaults to `Ubuntu`.
- **Windows username**, in `bootstrap.sh` (auto-detected via `cmd.exe`; override with `WIN_USER=...` if detection fails).

**Git identity:** this config deliberately does not set your git name or email.
Git will stop your first commit and tell you to set them (`git config --global user.name "Your Name"` and `git config --global user.email you@example.com`).
If you'd rather manage that declaratively, add this back to `home.nix` with your own identity:

```nix
programs.git = {
  enable = true;
  settings.user = {
    name = "Your Name";
    email = "you@example.com";
  };
};
```

**Homebrew cleanup warning:** `configuration.nix` sets `homebrew.onActivation.cleanup = "zap"`.
That means every time you switch, Homebrew removes any package or cask on your machine that isn't listed in the `brews` and `casks` arrays in `configuration.nix`.
If you already have Homebrew stuff installed that isn't in that list, the first switch will uninstall it.
Read through `brews` and `casks` before you run `bootstrap.sh` or `rebuild.sh` for the first time, and add anything you want to keep.

**Heads-up:**

- `home/AGENTS.md` is my personal agent policy, and `home.nix` installs it for Claude, Codex, and opencode.
  If you clone this repo, you'd silently inherit my agent instructions - edit or delete `home/AGENTS.md` if you don't want that.
- The `cc` and `co` shell aliases in `home.nix` are high-agency shortcuts: `claude --dangerously-skip-permissions` and `codex --full-auto`.
  They're convenient for me, but know what they do before you use them.

## Repo tour

- `flake.nix` - the entry point.
  Wires up nixpkgs (Linux + macOS), nix-darwin, home-manager, nix-homebrew, and herdr.
  Declares the `yashjeetbajwa` home configuration (Linux) and the `mac` darwin configuration.
- `configuration.nix` - macOS system-level config: macOS defaults, Homebrew. Linux ignores this.
- `home.nix` - user-level config: shell, gh, packages, and the symlinks described below.
  Shared across both platforms; branches on `pkgs.stdenv.hostPlatform.isDarwin`.
- `bootstrap.sh` - first-run setup. Detects OS and installs prerequisites, Nix, and applies the config.
  On macOS, also detects your username and offers to rewrite `flake.nix` for you.
- `rebuild.sh` - re-applies the config after the first switch. Run this every time you make a change.
- `wsl.conf` - system-level WSL config (systemd, default user), copied to `/etc/wsl.conf` by `bootstrap.sh`. macOS ignores this.
- `home/` - the actual config files that get symlinked into place (Neovim, WezTerm, herdr, Claude settings, the shared `AGENTS.md`).

## How the symlinks work

The files under `home/` are the real files - editing them here is editing your live config, no rebuild needed to see the change in your editor.
`home.nix` uses `mkOutOfStoreSymlink` to point paths like `~/.config/nvim` straight at `home/.config/nvim` in this repo (via `~/.dotfiles`), so the two never drift out of sync.
You only run `./rebuild.sh` when you change something that isn't just a symlinked file, like a package list or a system default.

The WezTerm config is a special case: it lives in the repo and is symlinked into `~/.config/wezterm` inside WSL, but the actual WezTerm process may run on Windows.
Because the `\\wsl$\` share does not follow symlinks, a tiny loader at `C:\Users\<you>\.wezterm.lua` does a `dofile` directly at the real file inside this repo (not the symlink).
`bootstrap.sh` writes this loader for you using the repo's actual path, so it stays correct no matter where you clone.
On macOS, WezTerm reads `~/.config/wezterm` directly.

## Notes

- The first time you launch `nvim`, it bootstraps [lazy.nvim](https://github.com/folke/lazy.nvim) by cloning plugins from GitHub. That needs network access once; after that it's offline.
- Neovim and WezTerm both use the rose-pine moon theme. Neovim uses a transparent background on macOS, Windows, and WSL so it matches the terminal setup.
- On WSL, `bootstrap.sh` writes `/etc/wsl.conf` with `systemd=true`. If your WSL didn't have systemd enabled, run `wsl --shutdown` from Windows and reopen to apply.
- On macOS, `herdr` comes from Homebrew. On WSL, it comes from the `herdr` flake input overlay.

## License

This repo is licensed under MIT No Attribution. See `LICENSE`.
