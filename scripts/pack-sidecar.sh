#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE="$ROOT/engine"
OUT="${1:-$ROOT/src-tauri/binaries}"
mkdir -p "$OUT"
cd "$ENGINE"
python -m PyInstaller --noconfirm --clean courdl-engine.spec
EXE="dist/courdl-engine"
if [[ -f dist/courdl-engine.exe ]]; then
  EXE="dist/courdl-engine.exe"
fi
TRIPLE="${CARGO_CFG_TARGET_TRIPLE:-}"
if [[ -z "$TRIPLE" ]]; then
  if command -v rustc >/dev/null; then
    TRIPLE="$(rustc -vV | awk '/host:/{print $2}')"
  else
    TRIPLE="x86_64-pc-windows-msvc"
  fi
fi
if [[ "$EXE" == *.exe ]]; then
  DEST="$OUT/courdl-engine-$TRIPLE.exe"
else
  DEST="$OUT/courdl-engine-$TRIPLE"
fi
cp "$EXE" "$DEST"
echo "Sidecar: $DEST"
