#!/usr/bin/env bash
# Prepare the demo scratch directories and launch the desktop app.
# Pass --no-launch to only print the paths.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR="$ROOT_DIR/demo"
WORK_DIR="$DEMO_DIR/work"

# Output directories and the FASTQ stubs cannot be committed (git stores no
# empty directories), so create them on demand.
mkdir -p "$WORK_DIR"/{rnaseq-results,sarek-results,viralrecon-results,scrnaseq-results,cache,fastq}
for sample in CTRL_1 CTRL_2 TREAT_1 TREAT_2; do
  : > "$WORK_DIR/fastq/${sample}_R1_001.fastq.gz"
  : > "$WORK_DIR/fastq/${sample}_R2_001.fastq.gz"
done

cat <<EOF
Demo inputs      $DEMO_DIR
Scratch outputs  $WORK_DIR

In the desktop app, click Choose and select:
  Samplesheet       $DEMO_DIR/rnaseq-samplesheet.csv
  Output directory  $WORK_DIR/rnaseq-results
then set the revision to 3.18.0 and press "Validate & plan".

CLI equivalents, no app required:
  PYTHONPATH=src python3 -m helixsh.cli trace-summary --file $DEMO_DIR/trace.txt
  PYTHONPATH=src python3 -m helixsh.cli samplesheet-validate --file $DEMO_DIR/sarek-samplesheet.csv --pipeline sarek
  PYTHONPATH=src python3 -m helixsh.cli samplesheet-generate --fastq-dir $WORK_DIR/fastq --pipeline rnaseq --out $WORK_DIR/generated.csv
EOF

if [ "${1:-}" = "--no-launch" ]; then
  exit 0
fi

if ! command -v node >/dev/null 2>&1; then
  echo "error: node is not on PATH; install Node $(cat "$ROOT_DIR/.nvmrc") first." >&2
  exit 1
fi

# package.json requires >=22.12 and Electron 43 will not start on older Node,
# so fail here with the fix rather than deep inside npm.
node_major="$(node -p 'process.versions.node.split(".")[0]')"
node_minor="$(node -p 'process.versions.node.split(".")[1]')"
if [ "$node_major" -lt 22 ] || { [ "$node_major" -eq 22 ] && [ "$node_minor" -lt 12 ]; }; then
  echo >&2
  echo "error: Node $(node -v) is too old; the desktop app needs >=22.12.0." >&2
  echo "       With nvm:  nvm install && nvm use     (.nvmrc pins $(cat "$ROOT_DIR/.nvmrc"))" >&2
  exit 1
fi

if [ ! -d "$ROOT_DIR/node_modules/electron" ]; then
  echo
  echo "Installing npm dependencies…"
  (cd "$ROOT_DIR" && npm install)
fi

echo
echo "Launching the desktop app…"
cd "$ROOT_DIR" && npm run desktop:dev
