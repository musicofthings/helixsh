#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${HOME}/.local/share/helixsh"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$APP_DIR"

"$ROOT_DIR/scripts/package_local.sh"
cp "$ROOT_DIR/dist/helixsh.pyz" "$INSTALL_DIR/helixsh.pyz"

cat > "$BIN_DIR/helixsh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/.local/share/helixsh/helixsh.pyz" "$@"
SH
chmod +x "$BIN_DIR/helixsh"

cat > "$APP_DIR/helixsh.desktop" <<'DESKTOP'
[Desktop Entry]
Name=Helixsh
Comment=Clinical genomics AI shell
Type=Application
Terminal=true
Exec=/bin/bash -lc 'helixsh doctor'
Categories=Science;Utility;
DESKTOP

echo "Installed helixsh desktop launcher and CLI wrapper."
echo "Ensure ${HOME}/.local/bin is in PATH, then run: helixsh --help"
