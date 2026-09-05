from __future__ import annotations

from pathlib import Path


class CookieError(ValueError):
    pass


def check_cookies_file(path: Path) -> dict:
    if not path.is_file():
        raise CookieError(f"Cookies file not found: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise CookieError("Cookies file is empty.")
    has_cauth = False
    coursera_rows = 0
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, _path, _secure, _exp, name, value = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
        if "coursera.org" not in domain.lower():
            continue
        coursera_rows += 1
        if name == "CAUTH" and value.strip() and value.strip() != "replace-with-real-value":
            has_cauth = True
    if coursera_rows == 0:
        raise CookieError("No .coursera.org cookies found. Export Netscape cookies from a logged-in Coursera session.")
    if not has_cauth:
        raise CookieError("Missing CAUTH cookie for .coursera.org. Re-export cookies while logged in.")
    return {"ok": True, "courseraCookieRows": coursera_rows, "hasCauth": True}
