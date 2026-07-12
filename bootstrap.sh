#!/usr/bin/env bash
# Fresh-machine bootstrap for WSL Ubuntu (Linux) or macOS.
# Installs Determinate Nix, symlinks this repo to ~/.dotfiles, and runs the
# first switch. On Linux also sets up apt prerequisites, zsh login shell,
# /etc/wsl.conf, and the Windows-side WezTerm loader.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
OS="$(uname -s)"

step() { printf "\n\033[1;34m==>\033[0m %s\n" "$*"; }

case "$OS" in
  Darwin)
    step "1/4  Determinate Nix"
    if command -v nix >/dev/null 2>&1; then
      echo "    nix already installed, skipping"
    else
      curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix \
        | sh -s -- install --no-confirm
      # shellcheck disable=SC1091
      . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
    fi

    step "2/4  symlink this repo to ~/.dotfiles"
    ln -sfn "$DIR" ~/.dotfiles

    step "3/4  personalize the configured username"
    # Do this before any sudo call: sudo resets $USER to root, so whoami has to
    # run as the real interactive user first.
    REAL_USER="$(whoami)"
    FLAKE_USER="$(sed -nE 's/^[[:space:]]*user = "([^"]+)";.*/\1/p' "$DIR/flake.nix" | head -n1)"
    if [ -z "$FLAKE_USER" ]; then
      echo "    Could not find the single \"user = \" line in flake.nix."
      echo "    Edit flake.nix yourself before continuing."
      exit 1
    elif [ "$FLAKE_USER" != "$REAL_USER" ]; then
      echo "    flake.nix is configured for user \"$FLAKE_USER\", but you are \"$REAL_USER\"."
      read -r -p "    Rewrite flake.nix's \"user = \" line to \"$REAL_USER\"? [y/N] " REPLY
      if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
        sed -i '' -E "s/^([[:space:]]*user = \")[^\"]+(\";.*)/\1${REAL_USER}\2/" "$DIR/flake.nix"
        echo "    Updated. Review the change with: git diff flake.nix"
      else
        echo "    Skipped. Edit the single \"user = \" line in flake.nix yourself before continuing."
        exit 1
      fi
    else
      echo "    flake.nix already matches \"$REAL_USER\", nothing to do."
    fi

    step "4/4  first darwin-rebuild switch (pinned to nix-darwin-26.05)"
    # darwin-rebuild doesn't exist yet on a fresh machine, so run it straight
    # from the flake this once. After this, rebuild.sh works normally.
    # sudo resets PATH to a secure default that excludes /nix/.../bin, so a
    # freshly installed nix would not be found under sudo even though it's
    # on PATH here. Resolve the absolute path first and invoke that instead.
    NIX_BIN="$(command -v nix)"
    sudo "$NIX_BIN" run github:nix-darwin/nix-darwin/nix-darwin-26.05#darwin-rebuild -- \
      switch --flake ~/.dotfiles#mac

    echo
    echo "Done. Use ./rebuild.sh for future changes."
    ;;

  Linux)
    WSL_DISTRO="${WSL_DISTRO:-Ubuntu}"
    WIN_USER="${WIN_USER:-$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')}"

    step "1/7  apt prerequisites"
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl build-essential zsh

    step "2/7  Determinate Nix"
    if ! command -v nix >/dev/null 2>&1; then
      sh <(curl -L https://determinate.systems/install) --no-confirm
      # shellcheck disable=SC1090
      . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
    else
      echo "nix already installed, skipping"
    fi

    step "3/7  symlink repo to ~/.dotfiles"
    ln -sfn "$DIR" ~/.dotfiles

    step "4/7  personalize the configured username"
    REAL_USER="$(whoami)"
    FLAKE_USER="$(sed -nE 's/^[[:space:]]*user = "([^"]+)";.*/\1/p' "$DIR/flake.nix" | head -n1)"
    if [ -z "$FLAKE_USER" ]; then
      echo "    Could not find the single \"user = \" line in flake.nix."
      echo "    Edit flake.nix yourself before continuing."
      exit 1
    elif [ "$FLAKE_USER" != "$REAL_USER" ]; then
      echo "    flake.nix is configured for user \"$FLAKE_USER\", but you are \"$REAL_USER\"."
      read -r -p "    Rewrite flake.nix's \"user = \" line to \"$REAL_USER\"? [y/N] " REPLY
      if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
        sed -i -E "s/^([[:space:]]*user = \")[^\"]+(\";.*)/\1${REAL_USER}\2/" "$DIR/flake.nix"
        echo "    Updated. Review the change with: git diff flake.nix"
        FLAKE_USER="$REAL_USER"
      else
        echo "    Proceeding with current user in flake.nix. If it doesn't match your username, the next step will fail."
      fi
    else
      echo "    flake.nix already matches \"$REAL_USER\", nothing to do."
    fi

    if [ "$FLAKE_USER" != "$REAL_USER" ]; then
      read -r -p "    Do you want to continue anyway (using $FLAKE_USER)? [y/N] " CONTINUE
      if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
        exit 1
      fi
    fi

    step "5/7  first home-manager switch"
    # Re-read in case it was updated above
    FLAKE_USER="$(sed -nE 's/^[[:space:]]*user = "([^"]+)";.*/\1/p' "$DIR/flake.nix" | head -n1)"
    nix run github:nix-community/home-manager/release-26.05#home-manager -- \
      switch --flake ~/.dotfiles#${FLAKE_USER}

    step "6/7  zsh as login shell"
    if [ "$(getent passwd "$(whoami)" | cut -d: -f7)" != "/usr/bin/zsh" ]; then
      chsh -s /usr/bin/zsh
    fi

    step "7/7  system + Windows-side config"
    # /etc/wsl.conf — personalize username before copying
    WSL_CONF_TMP=$(mktemp)
    sed "s/PLACEHOLDER_USERNAME/${REAL_USER}/" "$DIR/wsl.conf" > "$WSL_CONF_TMP"
    if ! sudo diff -q "$WSL_CONF_TMP" /etc/wsl.conf >/dev/null 2>&1; then
      sudo cp "$WSL_CONF_TMP" /etc/wsl.conf
      echo "wsl.conf updated. Run 'wsl --shutdown' from Windows to apply, then reopen."
    else
      echo "wsl.conf already in sync"
    fi
    rm -f "$WSL_CONF_TMP"

    # Windows-side WezTerm loader.
    # The \\wsl$\ share does not follow symlinks, so the loader must point at the
    # real file inside this repo (not ~/.config/wezterm, which is a home-manager
    # symlink into /nix/store). Using $DIR keeps it clone-location-agnostic.
    if [ -n "$WIN_USER" ]; then
      WIN_WEZTERM="/mnt/c/Users/$WIN_USER/.wezterm.lua"
      LINUX_PATH="$DIR/home/.config/wezterm/wezterm.lua"
      BACKSLASH_PATH=$(printf '%s' "$LINUX_PATH" | tr '/' '\\')
      printf 'return dofile(\n  [[\\\\wsl$\\%s%s]]\n)\n' "$WSL_DISTRO" "$BACKSLASH_PATH" > "$WIN_WEZTERM"
      echo "Windows WezTerm loader written to $WIN_WEZTERM"
      echo "Install Hack Nerd Font on Windows: see README.md"
    else
      echo "Could not detect Windows username; skip .wezterm.lua manually (see README.md)"
    fi

    echo
    echo "Done. Reopen your terminal (or 'wsl --shutdown' from Windows) to start zsh."
    ;;

  *)
    echo "Unsupported OS: $OS" >&2
    exit 1
    ;;
esac
