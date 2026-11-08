{ config, pkgs, lib, user, ... }:

let
  dotfiles = "${config.home.homeDirectory}/.dotfiles";
  isDarwin = pkgs.stdenv.hostPlatform.isDarwin;
in

{
  home.username = user;
  home.homeDirectory = if isDarwin then "/Users/${user}" else "/home/${user}";
  home.stateVersion = "24.11";
  home.packages = with pkgs; [
    # cli i use constantly
    ripgrep   # fast search
    fd        # fast find
    fzf       # fuzzy finder
    jq        # json on the command line
    lazygit
    awscli2   # aws cli, including sso login
    flyctl    # fly.io cli
    neovim
    nodejs_26  # Node.js 26
    pnpm       # Package manager
    cursor-cli # cursor agent - provides `cursor-agent` (alias `agent` added below)
    uv         # runs the deepseek-executor MCP server (registered below)
    # the font everything renders in
    nerd-fonts.hack
  ] ++ lib.optionals (!isDarwin) [
    home-manager  # mac uses darwin-rebuild, not the home-manager CLI
    herdr         # mac installs herdr via Homebrew (see configuration.nix)
  ];
  fonts.fontconfig.enable = true;
  home.sessionVariables.EDITOR = "nvim";

  # Paths for user-installed tooling outside the Nix store (sourced for every shell).
  home.sessionPath = [
    "$HOME/.local/bin"      # pipx and custom agent tools
    "$HOME/.npm-global/bin" # npm global prefix (e.g. gnhf)
  ];

  home.sessionVariables.DOTNET_ROOT = "$HOME/.dotnet"; # .NET SDK user install

  programs.zsh = {
    enable = true;
    autosuggestion.enable = true;      # ghost text from history
    syntaxHighlighting.enable = true;  # commands turn green when valid
    initContent = ''
      bindkey '^f' autosuggest-accept

      export PATH="$HOME/.dotnet:$HOME/.dotnet/tools:$PATH"

      # Also add npm-global here so it resolves in every interactive shell even
      # when the HM session-vars guard has already fired in an inherited env.
      # typeset -U path dedupes against the sessionPath entry.
      export PATH="$HOME/.npm-global/bin:$PATH"

      # dsh 0.1.1-rc.2 always mounts cordis-plugin-hmr to watch its patch files,
      # and that plugin throws unless Node runs with --expose-internals, a flag
      # Node refuses to read from NODE_OPTIONS. Invoke its entry point directly.
      dsh() {
        local entry="$HOME/.npm-global/lib/node_modules/@deepseek-ai/dsh/lib/bin.js"
        if [[ -f $entry ]]; then
          node --expose-internals "$entry" "$@"
        else
          command dsh "$@"
        fi
      }

      wt() {
        case "''${1:-}" in
          new|add)
            local branch="$2"
            [ -n "$branch" ] || { echo "Usage: wt new <branch>"; return 1; }
            local repo_root
            repo_root=$(git rev-parse --show-toplevel) || return 1
            local wt_dir="$repo_root/.worktrees/$branch"
            mkdir -p "$repo_root/.worktrees"
            if git show-ref --verify --quiet "refs/heads/$branch"; then
              git worktree add "$wt_dir" "$branch"
            else
              git worktree add -b "$branch" "$wt_dir" HEAD
            fi
            cd "$wt_dir"
            ;;
          rm|remove)
            local branch="$2"
            [ -n "$branch" ] || { echo "Usage: wt rm <branch>"; return 1; }
            local repo_root
            repo_root=$(git rev-parse --show-toplevel) || return 1
            local wt_dir="$repo_root/.worktrees/$branch"
            git worktree remove "$wt_dir" && git branch -d "$branch" 2>/dev/null || true
            ;;
          ls|list)
            git worktree list
            ;;
          *)
            echo "Usage: wt [new <branch> | rm <branch> | ls]"
            ;;
        esac
      }
    '';
    shellAliases = {
      ".." = "cd ..";
      add = "git add .";
      push = "git push";
      pull = "git pull";
      m = "git switch main";
      cc = "claude --dangerously-skip-permissions";
      co = "codex --full-auto";
    };
  };

  programs.gh = {
    enable = true;

    gitCredentialHelper.enable = true;
  };

  programs.starship = {
    enable = true;
    settings = {
      add_newline = false;
      format = "$directory$git_branch$git_status$cmd_duration$line_break$character";
      character = {
        success_symbol = "[❯](purple)";
        error_symbol = "[❯](red)";
      };
      cmd_duration.format = "[$duration]($style) ";
    };
  };

  # Edit-in-place: the real file stays in my repo, ~/.config just points at it.
  home.file.".config/wezterm".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.config/wezterm";
  home.file.".config/nvim".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.config/nvim";
  home.file.".config/herdr".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.config/herdr";
  home.file.".config/claude-mcp/deepseek-executor/server.py".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.config/claude-mcp/deepseek-executor/server.py";
  # uv looks for the lock next to the script path it is given, i.e. next to this symlink.
  home.file.".config/claude-mcp/deepseek-executor/server.py.lock".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.config/claude-mcp/deepseek-executor/server.py.lock";
  home.file.".config/claude-mcp/deepseek-executor/.env.example".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.config/claude-mcp/deepseek-executor/.env.example";
  home.file.".claude/settings.json".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.claude/settings.json";
  home.file.".claude/hooks/statusline-context.sh".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.claude/hooks/statusline-context.sh";

  home.file.".claude/CLAUDE.md".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/AGENTS.md";
  home.file.".claude/commands/deepseek-run.md".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.claude/commands/deepseek-run.md";
  home.file.".codex/AGENTS.md".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/AGENTS.md";
  home.file.".gemini/config/AGENTS.md".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/AGENTS.md";
  home.file.".gemini/config/GEMINI.md".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/AGENTS.md";

  home.file.".codex/config.toml".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.codex/config.toml";
  home.file.".codex/hooks.json".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.codex/hooks.json";
  home.file.".gemini/config/mcp_config.json".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.gemini/config/mcp_config.json";
  home.file.".gemini/config/hooks.json".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.gemini/config/hooks.json";
  home.file.".gemini/hooks/herdr-agent-state.sh".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.gemini/hooks/herdr-agent-state.sh";

  home.file.".local/bin/agent-notify-done".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.local/bin/agent-notify-done";
  home.file.".local/bin/claude-deepseek".source =
    config.lib.file.mkOutOfStoreSymlink "${dotfiles}/home/.local/bin/claude-deepseek";

  # cursor-cli only installs `cursor-agent`; upstream installer also provides `agent` alias
  home.file.".local/bin/agent".source = "${pkgs.cursor-cli}/bin/cursor-agent";

  # ~/.claude.json is Claude Code's mutable state, so it can't be a symlink; register through
  # the CLI instead, and only when the spec differs so live sessions' state isn't rewritten
  # on every switch. The profile path to uv survives uv upgrades and doesn't depend on PATH.
  home.activation.deepseekExecutorMcp =
    let
      spec = builtins.toJSON {
        type = "stdio";
        command = "${config.home.profileDirectory}/bin/uv";
        args = [
          "run"
          "--script"
          "${config.home.homeDirectory}/.config/claude-mcp/deepseek-executor/server.py"
        ];
        env = { };
      };
      jq = "${pkgs.jq}/bin/jq";
    in
    lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      # Activation runs with a minimal PATH. Linux uses the native installer, macOS the Homebrew cask.
      claude=""
      for candidate in "$HOME/.local/bin/claude" /opt/homebrew/bin/claude; do
        if [ -x "$candidate" ]; then claude="$candidate"; break; fi
      done
      if [ -z "$claude" ]; then
        echo "deepseek-executor: claude not installed yet, skipping MCP registration"
      elif [ "$(${jq} -cS '.mcpServers["deepseek-executor"] // empty' "$HOME/.claude.json" 2>/dev/null)" \
          != "$(${jq} -cS . <<< ${lib.escapeShellArg spec})" ]; then
        run --silence "$claude" mcp remove --scope user deepseek-executor || true
        run "$claude" mcp add-json --scope user deepseek-executor ${lib.escapeShellArg spec}
      fi
    '';
}
