#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
ARTIFACT="$DIST_DIR/helixsh.pyz"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

python -m zipapp "$ROOT_DIR/src" -m "helixsh.cli:main" -p "/usr/bin/env python3" -o "$ARTIFACT"
chmod +x "$ARTIFACT"

echo "Built local deployment artifact: $ARTIFACT"
echo "Run with: $ARTIFACT doctor"
