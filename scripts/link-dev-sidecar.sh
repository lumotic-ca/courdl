#!/usr/bin/env bash
# Create a Linux/macOS sidecar stub so `tauri dev` can spawn courdl-engine.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE="$ROOT/engine"
BIN="$ROOT/src-tauri/binaries"
mkdir -p "$BIN"
PY="${COURDL_PYTHON:-$ENGINE/.venv/bin/python3}"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi
TRIPLE="$(rustc -vV 2>/dev/null | awk '/host:/{print $2}')"
if [[ -z "$TRIPLE" ]]; then
  TRIPLE="$(uname -m)-unknown-linux-gnu"
  [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]] && TRIPLE="aarch64-apple-darwin"
  [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "x86_64" ]] && TRIPLE="x86_64-apple-darwin"
fi
DEST="$BIN/courdl-engine-$TRIPLE"
cat > "$DEST" << EOF
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$ENGINE\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$PY" -m courdl_engine "\$@"
EOF
chmod +x "$DEST"
echo "Wrote $DEST"
