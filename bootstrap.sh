#!/usr/bin/env bash
# Fresh-machine bootstrap for WSL Ubuntu.
# Installs prerequisites, Determinate Nix, symlinks this repo to ~/.dotfiles,
# runs the first home-manager switch, sets zsh as login shell, writes /etc/wsl.conf,
# and installs the Windows-side WezTerm loader + Hack Nerd Font.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
WSL_DISTRO="${WSL_DISTRO:-Ubuntu}"
WIN_USER="${WIN_USER:-$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')}"

step() { printf "\n\033[1;34m==>\033[0m %s\n" "$*"; }

step "1/6  apt prerequisites"
sudo apt-get update
sudo apt-get install -y ca-certificates curl build-essential zsh

step "2/6  Determinate Nix"
if ! command -v nix >/dev/null 2>&1; then
  sh <(curl -L https://determinate.systems/install) --no-confirm
  # shellcheck disable=SC1090
  . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
else
  echo "nix already installed, skipping"
fi

step "3/6  symlink repo to ~/.dotfiles"
ln -sfn "$DIR" ~/.dotfiles

step "4/6  first home-manager switch"
home-manager switch --flake ~/.dotfiles#yashjeetbajwa

step "5/6  zsh as login shell"
if [ "$(getent passwd "$(whoami)" | cut -d: -f7)" != "/usr/bin/zsh" ]; then
  chsh -s /usr/bin/zsh
fi

step "6/6  system + Windows-side config"
# /etc/wsl.conf
if ! sudo diff -q "$DIR/wsl.conf" /etc/wsl.conf >/dev/null 2>&1; then
  sudo cp "$DIR/wsl.conf" /etc/wsl.conf
  echo "wsl.conf updated. Run 'wsl --shutdown' from Windows to apply, then reopen."
else
  echo "wsl.conf already in sync"
fi

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
