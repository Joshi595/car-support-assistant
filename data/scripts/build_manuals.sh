#!/usr/bin/env bash
# Render the owner-manual sources to PDF with a headless Chromium browser (Edge or Chrome, both free).
# Usage: bash data/scripts/build_manuals.sh [path-to-browser]
set -euo pipefail
cd "$(dirname "$0")"
BROWSER="${1:-/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe}"
for src in manuals/*.html; do
  out="$(cd ../brand/global/en && pwd -W 2>/dev/null || pwd)/$(basename "${src%.html}").pdf"
  "$BROWSER" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$out" "file:///$(pwd -W 2>/dev/null || pwd)/$src"
  echo "built $out"
done
