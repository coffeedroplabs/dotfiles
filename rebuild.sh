#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ln -sfn "$DIR" ~/.dotfiles

FLAKE_USER="$(sed -nE 's/^[[:space:]]*user = "([^"]+)";.*/\1/p' "$DIR/flake.nix" | head -n1)"
case "$(uname -s)" in
  Darwin) exec sudo darwin-rebuild switch --flake ~/.dotfiles#mac ;;
  Linux)  home-manager switch --flake ~/.dotfiles#"$FLAKE_USER" ;;
  *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
