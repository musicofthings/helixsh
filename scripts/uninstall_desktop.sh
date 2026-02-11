#!/usr/bin/env bash
set -euo pipefail

rm -f "$HOME/.local/bin/helixsh"
rm -f "$HOME/.local/share/applications/helixsh.desktop"
rm -rf "$HOME/.local/share/helixsh"

echo "Uninstalled helixsh desktop assets."
