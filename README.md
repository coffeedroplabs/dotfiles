<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Stargazers][stars-shield]][stars-url]
[![Last commit][last-commit-shield]][commits-url]
[![License: MIT-0][license-shield]][license-url]
[![Platforms][platform-shield]][prerequisites-url]
[![nixpkgs 26.05][nixpkgs-shield]][nixpkgs-url]

<!-- PROJECT HEADER -->
<div align="center">
  <h3 align="center">dripfiles</h3>

  <p align="center">
    One command turns a fresh Mac or WSL Ubuntu machine into the same agent-ready dev setup, every time.
    <br />
    <a href="#getting-started"><strong>Get started »</strong></a>
    <br />
    <br />
    <a href="https://github.com/coffeedroplabs/dripfiles/issues/new?labels=bug">Report Bug</a>
    &middot;
    <a href="https://github.com/coffeedroplabs/dripfiles/issues/new?labels=enhancement">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#what-you-get">What you get</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#make-it-yours">Make it yours</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li>
      <a href="#usage">Usage</a>
      <ul>
        <li><a href="#daily-workflow">Daily workflow</a></li>
        <li><a href="#how-the-symlinks-work">How the symlinks work</a></li>
        <li><a href="#shell">Shell</a></li>
        <li><a href="#neovim">Neovim</a></li>
        <li><a href="#herdr">herdr</a></li>
        <li><a href="#ai-agents">AI agents</a></li>
      </ul>
    </li>
    <li><a href="#heads-up">Heads-Up</a></li>
    <li><a href="#project-structure">Project Structure</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

dripfiles is my personal machine setup, published so you can borrow from it or start your own. It is a single Nix flake:

* On **macOS** it drives nix-darwin, home-manager and Homebrew (through nix-homebrew).
* On **WSL Ubuntu** it drives standalone home-manager.

Both get the same shell, editor, terminal and AI-agent setup. Why it is built this way:

* **Reproducible.** Every input is pinned in `flake.lock` (nixpkgs 26.05). `./bootstrap.sh` takes a bare machine to a finished one.
* **Edit in place.** Config files are live symlinks back into this repo, so editing a file here edits your real config. No rebuild needed.
* **Agent-first.** One policy file drives Claude Code, Codex and Antigravity. Session hooks, "turn finished" notifications and a context-budget statusline come wired up, plus an MCP server that lets Claude hand bulk file writes to DeepSeek.

### What you get

Every row applies to both macOS and WSL, except the two system rows at the end.

| Area | What you get |
| --- | --- |
| Packages | ripgrep, fd, fzf, jq, lazygit, Neovim, awscli2, flyctl, Node.js 26, pnpm, uv, cursor-cli, Hack Nerd Font |
| Shell | zsh with autosuggestions and syntax highlighting, starship prompt, git aliases, a `wt` worktree helper |
| Editor | Neovim on lazy.nvim: rose-pine moon, snacks picker, oil, Neogit + diffview, gitsigns blame, which-key, a Windows clipboard bridge under WSL |
| Terminal | WezTerm with Tokyo Night and Hack Nerd Font: blurred and translucent on macOS, opens straight into WSL on Windows |
| Workspace | [herdr][herdr-url] agent multiplexer with tmux-style `Ctrl+B` keys, worktree shortcuts and a chime when an agent finishes |
| AI agents | One shared `AGENTS.md` for Claude Code, Codex and Antigravity, session hooks, desktop notifications, a Claude statusline with a 300k-token budget |
| DeepSeek | `deepseek-executor` MCP server, the `/deepseek-run` skill, and `claude-deepseek` (Claude Code on DeepSeek's API) |
| GitHub | `gh` CLI, set up as the git credential helper |
| macOS system | Dark mode, fast key repeat, auto-hidden menu bar and Dock, Finder list view, clean desktop, tap to click. Homebrew casks: WezTerm, Claude Code. Brews: herdr |
| WSL system | `/etc/wsl.conf` with systemd and your default user, zsh as login shell, the Windows-side WezTerm loader |

### Built With

[![Nix][nix-shield]][nix-url]
[![Determinate Nix][determinate-shield]][determinate-url]
[![home-manager][home-manager-shield]][home-manager-url]
[![nix-darwin][nix-darwin-shield]][nix-darwin-url]
[![nix-homebrew][nix-homebrew-shield]][nix-homebrew-url]
[![Neovim][neovim-shield]][neovim-url]
[![WezTerm][wezterm-shield]][wezterm-url]
[![herdr][herdr-shield]][herdr-url]
[![zsh][zsh-shield]][zsh-url]
[![Starship][starship-shield]][starship-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

* **macOS:** an Apple Silicon Mac. On an Intel Mac, change `aarch64-darwin` to `x86_64-darwin` in both `configuration.nix` (`hostPlatform`) and `flake.nix` (`system`).
* **WSL:** WSL2 running Ubuntu 24.04 (Noble) or similar on x86_64, sudo access inside WSL, and [WezTerm][wezterm-url] installed on the Windows side.

Optional extras. The repo manages their config, but not the tools themselves:

| Tool | What uses it | How to get it |
| --- | --- | --- |
| Claude Code | The `cc` alias, Claude settings, the DeepSeek MCP registration | macOS: installed for you as a Homebrew cask<br>WSL: `curl -fsSL https://claude.ai/install.sh \| bash` |
| Codex | The `co` alias, Codex hooks | `npm i -g @openai/codex` |
| Antigravity | Antigravity hooks and MCP servers | [antigravity.google](https://antigravity.google) |
| `*-axi` CLIs | SessionStart hooks in Claude Code and Codex | `npm i -g gh-axi chrome-devtools-axi lavish-axi` |
| DeepSeek API key | `deepseek-executor` and `claude-deepseek` | [platform.deepseek.com](https://platform.deepseek.com) |

The shell already has `~/.npm-global/bin` on `PATH`. Point npm at it once, before the global installs: `npm config set prefix ~/.npm-global`.

### Make it yours

This repo is set up for my machines. Review these before you run `bootstrap.sh`, because it applies the config right away:

* **Username.** The single `user = "yashjeetbajwa"` line in `flake.nix`. `bootstrap.sh` detects your username and offers to rewrite it. Everything else (`configuration.nix`, `home.nix`, home directory paths) is threaded from that one variable.
* **Host label** `mac`, in three places that have to match: the `darwinConfigurations."mac"` name in `flake.nix`, the `#mac` in `rebuild.sh`, and the `#mac` in the first-switch command in `bootstrap.sh`.
* **CPU architecture.** See [Prerequisites](#prerequisites).
* **WSL distro name.** Defaults to `Ubuntu`, in two places: `WSL_DISTRO` in `bootstrap.sh` (builds the Windows WezTerm loader path) and `config.default_domain = "WSL:Ubuntu"` in `home/.config/wezterm/wezterm.lua`.
* **Windows username.** `bootstrap.sh` detects it through `cmd.exe`. Override with `WIN_USER=...` if detection fails.
* **Personal choices.** My agent policy in `home/AGENTS.md`, the package list in `home.nix`, the Homebrew `brews` and `casks` in `configuration.nix`, Claude's model and plugin settings in `home/.claude/settings.json`, and the Neon and Cloudflare MCP servers. Swap in your own.

**Git identity.** The repo deliberately does not set your git name or email. Git will stop your first commit and ask for them (`git config --global user.name "Your Name"` and `git config --global user.email you@example.com`). To manage them declaratively, add this to `home.nix`:

```nix
programs.git = {
  enable = true;
  settings.user = {
    name = "Your Name";
    email = "you@example.com";
  };
};
```

### Installation

1. Get your own copy: click **[Use this template][template-url]** for a fresh repo without my history, or clone this one:
   ```sh
   git clone https://github.com/coffeedroplabs/dripfiles.git
   cd dripfiles
   ```
2. Work through [Make it yours](#make-it-yours) and the [Heads-Up](#heads-up), especially the Homebrew cleanup warning.
3. Run the bootstrap. It detects your OS:
   ```sh
   ./bootstrap.sh
   ```
   <details>
     <summary>What it does on macOS (4 steps)</summary>

   1. Installs Determinate Nix, if it isn't already installed.
   2. Symlinks this repo to `~/.dotfiles`.
   3. Checks the `user` in `flake.nix` against your macOS username, and offers to fix it if they differ.
   4. Runs the first `darwin-rebuild switch`, fetching `darwin-rebuild` from the nix-darwin 26.05 branch and applying this repo's locked flake. From then on, `darwin-rebuild` is installed and you're on the [daily workflow](#daily-workflow).
   </details>
   <details>
     <summary>What it does on WSL Ubuntu (7 steps)</summary>

   1. Installs apt prerequisites (`ca-certificates`, `curl`, `build-essential`, `zsh`).
   2. Installs Determinate Nix, if it isn't already installed.
   3. Symlinks this repo to `~/.dotfiles`. This has to happen before the first build, because `home.nix` points at config files through `~/.dotfiles`.
   4. Checks the `user` in `flake.nix` against your username, and offers to fix it if they differ.
   5. Runs the first `home-manager switch`, fetching `home-manager` from the release-26.05 branch and applying this repo's locked flake.
   6. Sets zsh as your login shell with `chsh`.
   7. Writes `/etc/wsl.conf` and the Windows-side WezTerm loader (`C:\Users\<you>\.wezterm.lua`).
   </details>
4. **WSL only:** reopen your terminal (or run `wsl --shutdown` from Windows) so systemd and zsh take effect.
5. **WSL only:** install Hack Nerd Font on Windows, because WezTerm runs on the Windows side.
   <details>
     <summary>PowerShell snippet</summary>

   ```powershell
   $zip = "$env:TEMP\hack.zip"
   $dir = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"
   Invoke-WebRequest "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/Hack.zip" -OutFile $zip
   New-Item -ItemType Directory -Force -Path $dir | Out-Null
   Expand-Archive $zip -DestinationPath $dir -Force
   Get-ChildItem "$dir\HackNerdFont*.ttf" | ForEach-Object { New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts" -Name "$($_.BaseName) (TrueType)" -Value $_.FullName -PropertyType String -Force | Out-Null }
   ```
   </details>
6. **Optional:** connect the agent extras.
   ```sh
   # Let herdr track Claude Code and Codex sessions (the hooks call the scripts these install)
   herdr integration install claude
   herdr integration install codex

   # Give the DeepSeek executor and claude-deepseek your API key
   cd ~/.config/claude-mcp/deepseek-executor
   cp .env.example .env && chmod 600 .env
   $EDITOR .env
   ```

**Check without applying.** Once Nix is installed, you can confirm the config evaluates without touching your system:

```sh
nix flake check --no-build
nix build .#darwinConfigurations.mac.system --dry-run                    # macOS
nix build .#homeConfigurations.<your-user>.activationPackage --dry-run   # WSL
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE -->
## Usage

### Daily workflow

* **Changed a config file under `home/`?** Nothing to do. It's already live.
* **Changed packages, system defaults, `home.nix` or `flake.nix`?** Apply it:
  ```sh
  ./rebuild.sh
  ```
* **Want newer packages?** Bump the pinned inputs, then apply:
  ```sh
  nix flake update && ./rebuild.sh
  ```

### How the symlinks work

The files under `home/` are the real files. `home.nix` uses `mkOutOfStoreSymlink` to point paths like `~/.config/nvim` straight at `home/.config/nvim` in this repo (through `~/.dotfiles`), so the two never drift apart. `rebuild.sh` re-creates `~/.dotfiles` every time, so the repo can live anywhere.

WezTerm on Windows is the exception. The config lives in this repo, but WezTerm runs on Windows, and the `\\wsl$\` share does not follow symlinks. So a tiny loader at `C:\Users\<you>\.wezterm.lua` runs `dofile` on the real file inside the repo. `bootstrap.sh` writes it with the repo's actual path. On macOS, WezTerm reads `~/.config/wezterm` directly.

### Shell

| Command | What it does |
| --- | --- |
| `Ctrl+F` | Accept the autosuggestion |
| `..` | `cd ..` |
| `add` | `git add .` |
| `push` / `pull` | `git push` / `git pull` |
| `m` | `git switch main` |
| `wt new <branch>` | Create or check out a worktree at `.worktrees/<branch>` and `cd` into it |
| `wt rm <branch>` | Remove that worktree, and its branch if it is merged |
| `wt ls` | List worktrees |
| `cc` | `claude --dangerously-skip-permissions` |
| `co` | `codex --full-auto` |
| `agent` | Cursor's agent CLI (`cursor-agent`) |
| `claude-deepseek` | Claude Code running on DeepSeek's Anthropic-compatible API |
| `dsh` | DeepSeek's `dsh` CLI, launched with `--expose-internals` to work around a plugin crash in 0.1.1-rc.2 |

### Neovim

The leader key is `Space`. On first launch, lazy.nvim clones its plugins from GitHub. That needs network once, then it works offline.

| Key | Action |
| --- | --- |
| `<leader>f` | Find files |
| `<leader>s` | Search text (grep) |
| `<leader>b` | Buffers |
| `<leader>e` | File browser (oil) |
| `<leader>g` | Neogit |
| `<leader>w` | Save |
| `gd` | Go to definition (when a language server is attached) |
| `Ctrl+A` | Select all |
| `p` (visual) | Paste over a selection without overwriting the clipboard |

### herdr

The prefix is `Ctrl+B`, tmux style. Press the prefix, then:

| Key | Action |
| --- | --- |
| `h` `j` `k` `l` | Focus pane left / down / up / right |
| `"` / `%` | Split horizontally / vertically |
| `c` / `&` | New tab / close tab |
| `w` | Workspace picker |
| `g` | Go to |
| `y` | Copy mode |
| `Shift+G` / `o` / `Shift+X` | New / open / remove worktree |

### AI agents

**One policy, three agents.** `home/AGENTS.md` is symlinked to `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` and `~/.gemini/config/AGENTS.md` (plus `GEMINI.md`), so every agent follows the same rules.

**Claude Code** (`home/.claude/settings.json`):
* Opus as the main model (Opus 5.5 at `xhigh` effort, auto-compacting at 200k tokens), Sonnet for subagents, thinking always on, auto memory on.
* SessionStart hooks report the session to herdr and print usage hints from `gh-axi`, `chrome-devtools-axi` and `lavish-axi`.
* The Stop hook runs `agent-notify-done`, which shows a herdr notification with a chime, a macOS notification, or `notify-send` on desktop Linux.
* A statusline that shows how close the session is to a 300k-token budget. It turns yellow at 75% and red at 90%:
  ```text
  Opus 5.5 | dripfiles (main) | ctx 84.2k/300k (28%)
  ```
* The WorkHunt plugin from the [coffeedroplabs/workhunt-claude-plugin](https://github.com/coffeedroplabs/workhunt-claude-plugin) marketplace.

**DeepSeek executor** (`home/.config/claude-mcp/deepseek-executor/`): an MCP server that lets Claude orchestrate while DeepSeek writes large, mechanical files.
* Tools: `implement_file_with_deepseek` (new file or full rewrite) and `patch_file_with_deepseek` (SEARCH/REPLACE edits). Both refuse paths outside a git work tree and return the diff plus an `Undo:` command.
* Every switch registers it with Claude Code automatically (`home.activation.deepseekExecutorMcp` in `home.nix`). It re-registers only when the spec changed.
* The `/deepseek-run` skill decides when delegating is worth it: roughly 80+ lines of mechanical code.
* Each call appends outcome, tokens, effort and duration to `~/.local/state/deepseek-executor/calls.jsonl`.
* Tests: `uv run --script home/.config/claude-mcp/deepseek-executor/test_server.py`

**`claude-deepseek`** runs Claude Code itself on DeepSeek's Anthropic-compatible API: the 1M-token context, max effort, and the executor tools turned off, since DeepSeek delegating to DeepSeek only adds a round trip.

**Codex** (`home/.codex/`): hooks turned on (the same SessionStart and Stop behavior as Claude) and the Neon MCP server.

**Antigravity** (`home/.gemini/`): herdr session reporting, turn-finished notifications, and the Neon and Cloudflare MCP servers.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- HEADS-UP -->
## Heads-Up

* **Homebrew cleanup is set to `zap`.** Every switch on macOS removes any Homebrew package or cask that isn't listed in `brews` or `casks` in `configuration.nix`. If you already use Homebrew, add everything you want to keep before your first `bootstrap.sh` or `rebuild.sh`. This is deliberate: it forces every package to be declared.
* **You inherit my agent policy.** `home/AGENTS.md` becomes the global instructions for Claude Code, Codex and Antigravity. Edit or empty it if you don't want that.
* **High-agency aliases.** `cc` is `claude --dangerously-skip-permissions` and `co` is `codex --full-auto`. On top of that, `skipDangerousModePermissionPrompt` in Claude's settings skips the confirmation for bypass mode. Know what these do before you use them.
* **DeepSeek data handling.** According to DeepSeek's privacy policy, the first-party API may use inputs for training and stores data in the PRC. Opting out of training is done by email. The executor sends the files you list as context.
* **Unfree packages are allowed** (`allowUnfree = true`), for `cursor-cli`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- PROJECT STRUCTURE -->
## Project Structure

```text
dripfiles/
├── flake.nix            # entry point: inputs, the Linux home config, the "mac" darwin config
├── flake.lock           # pinned inputs
├── home.nix             # shared user config: packages, shell, symlinks
├── configuration.nix    # macOS only: system defaults and Homebrew
├── wsl.conf             # WSL only: copied to /etc/wsl.conf by bootstrap.sh
├── bootstrap.sh         # first run on a fresh machine
├── rebuild.sh           # applies changes after the first run
├── AGENTS.md            # instructions for agents working on this repo
└── home/                # the live config files, symlinked into ~
    ├── AGENTS.md        # global agent policy for Claude Code, Codex and Antigravity
    ├── .claude/         # Claude Code settings, statusline, /deepseek-run skill
    ├── .codex/          # Codex config and hooks
    ├── .gemini/         # Antigravity hooks and MCP servers
    ├── .config/
    │   ├── nvim/        # Neovim
    │   ├── wezterm/     # WezTerm
    │   ├── herdr/       # herdr
    │   └── claude-mcp/  # the DeepSeek executor MCP server and its tests
    └── .local/bin/      # agent-notify-done, claude-deepseek
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

dripfiles is a personal setup, so the best way to use it is to make it yours with **[Use this template][template-url]**. Bug reports and fixes are welcome, especially for anything that breaks on a fresh machine.

1. Fork the project
2. Create your branch (`git checkout -b fix/fresh-machine-bug`)
3. Commit your changes (`git commit -m "fix: describe the fix"`)
4. Push to the branch (`git push origin fix/fresh-machine-bug`)
5. Open a pull request

Before you open it, run `nix flake check --no-build`, plus the executor tests if you touched `deepseek-executor`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the MIT No Attribution License (MIT-0). Copy anything you like, no credit required. See [`LICENSE`](LICENSE) for the full text.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Maintained by [yashjeetbajwadev](https://github.com/yashjeetbajwadev) at [coffeedroplabs](https://github.com/coffeedroplabs).

Project link: [https://github.com/coffeedroplabs/dripfiles](https://github.com/coffeedroplabs/dripfiles)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [Best-README-Template](https://github.com/othneildrew/Best-README-Template), the structure of this README
* [nix-darwin][nix-darwin-url], [home-manager][home-manager-url], [nix-homebrew][nix-homebrew-url] and the [Determinate Nix installer][determinate-url]
* [herdr][herdr-url], the agent multiplexer
* [lazy.nvim](https://github.com/folke/lazy.nvim), [snacks.nvim](https://github.com/folke/snacks.nvim), [which-key.nvim](https://github.com/folke/which-key.nvim), [oil.nvim](https://github.com/stevearc/oil.nvim), [Neogit](https://github.com/NeogitOrg/neogit), [gitsigns.nvim](https://github.com/lewis6991/gitsigns.nvim) and [Rosé Pine](https://github.com/rose-pine/neovim)
* [WezTerm][wezterm-url], [Tokyo Night](https://github.com/enkia/tokyo-night-vscode-theme) and [Nerd Fonts](https://www.nerdfonts.com)
* [Shields.io](https://shields.io) for the badges

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
[stars-shield]: https://img.shields.io/github/stars/coffeedroplabs/dripfiles.svg?style=for-the-badge
[stars-url]: https://github.com/coffeedroplabs/dripfiles/stargazers
[last-commit-shield]: https://img.shields.io/github/last-commit/coffeedroplabs/dripfiles.svg?style=for-the-badge
[commits-url]: https://github.com/coffeedroplabs/dripfiles/commits/main
[license-shield]: https://img.shields.io/badge/license-MIT--0-blue.svg?style=for-the-badge
[license-url]: https://github.com/coffeedroplabs/dripfiles/blob/main/LICENSE
[platform-shield]: https://img.shields.io/badge/platform-macOS%20%7C%20WSL2-lightgrey.svg?style=for-the-badge
[prerequisites-url]: #prerequisites
[nixpkgs-shield]: https://img.shields.io/badge/nixpkgs-26.05-5277C3.svg?style=for-the-badge&logo=nixos&logoColor=white
[nixpkgs-url]: https://github.com/NixOS/nixpkgs/tree/nixos-26.05
[template-url]: https://github.com/new?template_name=dripfiles&template_owner=coffeedroplabs
[nix-shield]: https://img.shields.io/badge/Nix-5277C3?style=for-the-badge&logo=nixos&logoColor=white
[nix-url]: https://nixos.org
[determinate-shield]: https://img.shields.io/badge/Determinate%20Nix-0F172A?style=for-the-badge&logo=nixos&logoColor=white
[determinate-url]: https://determinate.systems
[home-manager-shield]: https://img.shields.io/badge/home--manager-41439A?style=for-the-badge&logo=nixos&logoColor=white
[home-manager-url]: https://github.com/nix-community/home-manager
[nix-darwin-shield]: https://img.shields.io/badge/nix--darwin-000000?style=for-the-badge&logo=apple&logoColor=white
[nix-darwin-url]: https://github.com/nix-darwin/nix-darwin
[nix-homebrew-shield]: https://img.shields.io/badge/nix--homebrew-FBB040?style=for-the-badge&logo=homebrew&logoColor=black
[nix-homebrew-url]: https://github.com/zhaofengli/nix-homebrew
[neovim-shield]: https://img.shields.io/badge/Neovim-57A143?style=for-the-badge&logo=neovim&logoColor=white
[neovim-url]: https://neovim.io
[wezterm-shield]: https://img.shields.io/badge/WezTerm-4E49EE?style=for-the-badge&logo=wezterm&logoColor=white
[wezterm-url]: https://wezterm.org
[herdr-shield]: https://img.shields.io/badge/herdr-1E1E2E?style=for-the-badge
[herdr-url]: https://github.com/ogulcancelik/herdr
[zsh-shield]: https://img.shields.io/badge/zsh-F15A24?style=for-the-badge&logo=zsh&logoColor=white
[zsh-url]: https://www.zsh.org
[starship-shield]: https://img.shields.io/badge/Starship-DD0B78?style=for-the-badge&logo=starship&logoColor=white
[starship-url]: https://starship.rs
