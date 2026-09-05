#!/usr/bin/env bash
# Download an enrolled Coursera course, specialization, or professional certificate.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/.venv/bin/python3"
DL="$ROOT/.venv/bin/dl_coursera"
COOKIES="${COOKIES:-$ROOT/cookies.txt}"
OUTDIR="${OUTDIR:-$ROOT/courses}"

if [[ ! -x "$DL" ]]; then
  echo "dl_coursera is not installed. Expected $DL" >&2
  exit 1
fi

if [[ ! -f "$COOKIES" ]]; then
  echo "Missing cookies file: $COOKIES" >&2
  echo "Export Netscape cookies from a logged-in Coursera session. See $ROOT/README.md" >&2
  exit 1
fi

chmod 600 "$COOKIES" 2>/dev/null || true

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <slug-or-coursera-url>" >&2
  echo "Example: $0 https://www.coursera.org/learn/process-modeling" >&2
  echo "Example: $0 https://www.coursera.org/professional-certificates/microsoft-visio-workflow-design-and-automation" >&2
  exit 1
fi

INPUT="$1"
SLUG="$("$PY" - <<'PY' "$INPUT"
import re, sys
value = sys.argv[1].strip().rstrip("/")
m = re.search(
    r"coursera\.org/(?:learn|specializations|professional-certificates)/([^/?#]+)",
    value,
)
print(m.group(1) if m else value.split("/")[-1])
PY
)"

if [[ -z "$SLUG" ]]; then
  echo "Could not parse a Coursera slug from: $INPUT" >&2
  exit 1
fi

mkdir -p "$OUTDIR"
DEST="$OUTDIR/$SLUG"

# Drop the old standalone copy when pulling the full certificate tree.
if [[ -d "$OUTDIR/process-modeling" && "$SLUG" == "microsoft-visio-workflow-design-and-automation" ]]; then
  rm -rf "$OUTDIR/process-modeling"
fi

"$DL" --cookies "$COOKIES" --outdir "$OUTDIR" "$SLUG"
"$PY" "$ROOT/beautify.py" --cookies "$COOKIES" "$DEST"
