from __future__ import annotations

import json
from pathlib import Path

# Cookie-Editor and similar tools prefix HttpOnly Netscape rows with this.
# Python's MozillaCookieJar (and dl_coursera) treat those lines as comments.
HTTPONLY_PREFIXES = ("#httponly_", "#httponly:")


class CookieError(ValueError):
    pass


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if not data.strip():
        raise CookieError("Cookies file is empty.")
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16")
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _strip_httponly_prefix(domain: str) -> str:
    raw = domain.strip()
    lower = raw.lower()
    for prefix in HTTPONLY_PREFIXES:
        if lower.startswith(prefix):
            return raw[len(prefix) :]
    return raw


def _rows_from_netscape(text: str) -> list[tuple[str, str, str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("#") and not lower.startswith("#httponly"):
            continue
        if lower.startswith("#httponly"):
            stripped = _strip_httponly_prefix(stripped)
        parts = stripped.split("\t")
        if len(parts) < 7:
            continue
        domain = _strip_httponly_prefix(parts[0])
        flag, path, secure, exp, name, value = parts[1:7]
        if not domain or not name:
            continue
        rows.append((domain, flag, path, secure, exp, name, value))
    return rows


def _cookie_dict_list(payload: object) -> list[dict] | None:
    if isinstance(payload, dict):
        for key in ("cookies", "Cookie", "Items"):
            inner = payload.get(key)
            if isinstance(inner, list):
                payload = inner
                break
        else:
            return None
    if not isinstance(payload, list) or not payload:
        return None
    if not all(isinstance(item, dict) for item in payload):
        return None
    return payload


def _rows_from_json(text: str) -> list[tuple[str, str, str, str, str, str, str]] | None:
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    items = _cookie_dict_list(payload)
    if not items:
        return None
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for item in items:
        name = str(item.get("name") or item.get("Name") or "")
        value = str(item.get("value") or item.get("Value") or "")
        domain = str(item.get("domain") or item.get("Domain") or "")
        path = str(item.get("path") or item.get("Path") or "/")
        if not name or not domain:
            continue
        secure = item.get("secure", item.get("Secure", False))
        exp = item.get("expirationDate") or item.get("expires") or item.get("Expires") or 0
        try:
            exp_s = str(int(float(exp)))
        except (TypeError, ValueError):
            exp_s = "0"
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        secure_s = "TRUE" if secure in (True, "TRUE", "true", 1, "1") else "FALSE"
        rows.append((domain, flag, path, secure_s, exp_s, name, value))
    return rows or None


def _to_netscape(rows: list[tuple[str, str, str, str, str, str, str]]) -> str:
    lines = [
        "# Netscape HTTP Cookie File",
        "# Normalized by CourDL. HttpOnly markers stripped so dl_coursera can read CAUTH.",
    ]
    for domain, flag, path, secure, exp, name, value in rows:
        lines.append("\t".join([domain, flag, path, secure, exp, name, value]))
    return "\n".join(lines) + "\n"


def parse_cookie_rows(text: str) -> list[tuple[str, str, str, str, str, str, str]]:
    json_rows = _rows_from_json(text)
    if json_rows:
        return json_rows
    return _rows_from_netscape(text)


def ensure_netscape_cookies(path: Path) -> list[tuple[str, str, str, str, str, str, str]]:
    """Parse cookies and rewrite the file as classic Netscape so MozillaCookieJar works."""
    text = _read_text(path)
    rows = parse_cookie_rows(text)
    if not rows:
        raise CookieError(
            "No cookies found. Export Netscape cookies.txt or Cookie-Editor JSON from a logged-in Coursera session."
        )
    normalized = _to_netscape(rows)
    if normalized != text.replace("\r\n", "\n"):
        path.write_text(normalized, encoding="utf-8")
    return rows


def check_cookies_file(path: Path) -> dict:
    if not path.is_file():
        raise CookieError(f"Cookies file not found: {path}")
    rows = ensure_netscape_cookies(path)
    has_cauth = False
    coursera_rows = 0
    for domain, _flag, _path, _secure, _exp, name, value in rows:
        if "coursera.org" not in domain.lower():
            continue
        coursera_rows += 1
        if name == "CAUTH" and value.strip() and value.strip() != "replace-with-real-value":
            has_cauth = True
    if coursera_rows == 0:
        raise CookieError(
            "No .coursera.org cookies found. Export cookies while logged in to Coursera (Cookie-Editor Netscape or JSON)."
        )
    if not has_cauth:
        raise CookieError(
            "Missing CAUTH cookie for .coursera.org. Re-export cookies while logged in. Cookie-Editor HttpOnly rows are OK."
        )
    return {"ok": True, "courseraCookieRows": coursera_rows, "hasCauth": True}
