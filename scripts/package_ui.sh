#!/usr/bin/env bash
# Build installable helixsh desktop packages for the current platform.
#
# Output (relative to repo root):
#   Linux  → ui/src-tauri/target/release/bundle/deb/*.deb
#             ui/src-tauri/target/release/bundle/appimage/*.AppImage
#   macOS  → ui/src-tauri/target/release/bundle/dmg/*.dmg
#   Windows→ ui/src-tauri/target/release/bundle/nsis/*.exe
#
# Usage:
#   ./scripts/package_ui.sh           # release build
#   ./scripts/package_ui.sh --debug   # debug build (faster, larger binary)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UI_DIR="$REPO_ROOT/ui"

debug=false
if [[ "${1:-}" == "--debug" ]]; then
  debug=true
fi

echo "==> helixsh desktop packaging"
echo "    repo:  $REPO_ROOT"
echo "    debug: $debug"

# --- Prerequisites ----------------------------------------------------------
check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    echo "ERROR: '$1' not found. $2" >&2
    exit 1
  fi
}

check_cmd node   "Install Node.js 18+ from https://nodejs.org"
check_cmd cargo  "Install Rust from https://rustup.rs"
check_cmd npx    "Comes with Node.js"

# Linux-specific system deps check
if [[ "$(uname)" == "Linux" ]]; then
  for lib in libwebkit2gtk-4.1-dev libgtk-3-dev; do
    if ! dpkg -s "$lib" &>/dev/null 2>&1; then
      echo "WARNING: $lib may not be installed. Run:"
      echo "  sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev libgtk-3-dev libgdk-pixbuf-2.0-dev"
      echo "Continuing anyway…"
    fi
  done
fi

# --- Install JS dependencies -------------------------------------------------
echo "==> Installing npm dependencies…"
(cd "$UI_DIR" && npm ci --silent)

# --- Build -------------------------------------------------------------------
echo "==> Building helixsh desktop (bundle)…"

if $debug; then
  (cd "$UI_DIR" && npx tauri build --debug)
else
  (cd "$UI_DIR" && npx tauri build)
fi

# --- Report artifacts --------------------------------------------------------
BUNDLE_DIR="$UI_DIR/src-tauri/target/$(if $debug; then echo debug; else echo release; fi)/bundle"

echo ""
echo "==> Build complete. Artifacts:"
find "$BUNDLE_DIR" \
  \( -name "*.deb" -o -name "*.AppImage" -o -name "*.dmg" -o -name "*.exe" -o -name "*.msi" \) \
  -exec ls -lh {} \; 2>/dev/null || echo "    (no bundles found — check build output above)"

echo ""
echo "Install instructions:"
case "$(uname)" in
  Linux)
    echo "  deb:      sudo dpkg -i <file>.deb"
    echo "  AppImage: chmod +x <file>.AppImage && ./<file>.AppImage"
    ;;
  Darwin)
    echo "  dmg:      open <file>.dmg  (drag helixsh to /Applications)"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    echo "  exe:      double-click the NSIS installer"
    ;;
esac
