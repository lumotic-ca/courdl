#!/usr/bin/env bash
# Automated smoke for CourDL engine + Rust shell. Does not launch the GUI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "smoke: $*" >&2
  exit 1
}

echo "== engine pytest =="
if [[ ! -x engine/.venv/bin/pytest ]]; then
  fail "engine/.venv is missing. From repo root: python3 -m venv engine/.venv && engine/.venv/bin/pip install -e \".[dev]\""
fi
engine/.venv/bin/pytest

echo "== rust tests =="
if ! command -v cargo >/dev/null 2>&1; then
  fail "cargo is not on PATH"
fi
cargo test --manifest-path src-tauri/Cargo.toml
cargo check --manifest-path src-tauri/Cargo.toml

echo "== dialog commands stay async (macOS freeze regression) =="
grep -n "pub async fn pick_cookies_file" src-tauri/src/auth.rs >/dev/null \
  || fail "pick_cookies_file must be async"
grep -n "pub async fn pick_library_dir" src-tauri/src/library.rs >/dev/null \
  || fail "pick_library_dir must be async"
if grep -E -n "pub fn pick_cookies_file|pub fn pick_library_dir" src-tauri/src/*.rs >/dev/null; then
  fail "file pickers must not be sync commands"
fi

echo "== sidecar lookup covers macOS .app Resources =="
grep -n "Contents/Resources\|join(\"Resources\")" src-tauri/src/paths.rs >/dev/null \
  || fail "sidecar search must include macOS Resources"

echo "smoke: ok"
