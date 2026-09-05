"""JSONL progress for the Tauri shell. Human logs stay on stderr."""

from __future__ import annotations

import json
import sys
from typing import Any


def emit(
    phase: str,
    message: str,
    *,
    current: int | None = None,
    total: int | None = None,
    level: str = "info",
    **extra: Any,
) -> None:
    payload = {
        "courdl": True,
        "phase": phase,
        "message": message,
        "level": level,
    }
    if current is not None:
        payload["current"] = current
    if total is not None:
        payload["total"] = total
    payload.update(extra)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def log(message: str) -> None:
    sys.stderr.write(message.rstrip() + "\n")
    sys.stderr.flush()
