from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

PATH_SCHEMA_VERSION = "1"

UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MAX_COMPONENT = 180


def _short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:8]


def _split_stem_ext(name: str) -> tuple[str, str]:
    if name.endswith(".tar.gz"):
        return name[: -len(".tar.gz")], ".tar.gz"
    stem, ext = os.path.splitext(name)
    if ext and len(ext) <= 8:
        return stem, ext
    return name, ""


def sanitize_asset_name(name: str, *, used: set[str] | None = None) -> str:
    original = name or "asset"
    text = original.replace("\\", "/").split("/")[-1]
    text = text.split("?")[0].split("#")[0]
    try:
        text = unquote(text)
    except Exception:
        pass
    text = UNSAFE.sub("_", text)
    text = text.strip(" .")
    if not text:
        text = "asset"
    stem, ext = _split_stem_ext(text)
    stem = stem.strip(" .") or "asset"
    upper = stem.split(".")[0].upper()
    if upper in RESERVED:
        stem = f"_{stem}"
    if len(stem) + len(ext) > MAX_COMPONENT:
        keep = max(16, MAX_COMPONENT - len(ext) - 9)
        stem = f"{stem[:keep].rstrip(' .')}_{_short_hash(original)}"
    out = f"{stem}{ext}"
    used_set = used if used is not None else set()
    candidate = out
    n = 2
    while candidate.lower() in {u.lower() for u in used_set}:
        candidate = f"{stem}_{n}{ext}"
        n += 1
    used_set.add(candidate)
    return candidate


def sanitize_rel_component(name: str) -> str:
    if name in {".", ".."} or not name:
        return "asset"
    return sanitize_asset_name(name)


def sanitize_task_filename(filename: str, outdir: str | Path) -> str:
    root = Path(outdir).resolve()
    raw = Path(filename)
    try:
        rel = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    except Exception:
        rel = (root / sanitize_asset_name(raw.name)).resolve()
    try:
        rel.relative_to(root)
    except ValueError:
        rel = root / sanitize_asset_name(raw.name)
    parts = []
    used: set[str] = set()
    for i, part in enumerate(rel.relative_to(root).parts):
        if i < len(rel.relative_to(root).parts) - 1:
            parts.append(part)
        else:
            parts.append(sanitize_asset_name(part, used=used))
    return str(root.joinpath(*parts)) if parts else str(root)


def win_extended_path(path: str) -> str:
    if os.name != "nt":
        return path
    p = os.path.abspath(path)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def looks_contaminated(name: str) -> bool:
    leaf = name.replace("\\", "/").split("/")[-1]
    return any(ch in leaf for ch in '<>:"|?*') or "?" in leaf or "&hmac=" in leaf


def walk_sanitize_assets(obj, *, used: set[str] | None = None) -> dict[str, str]:
    """Rewrite Asset-like dicts in a crawled course object. Returns old->new names."""
    mapping: dict[str, str] = {}
    used_set = used if used is not None else set()

    def walk(node) -> None:
        if isinstance(node, dict):
            name = node.get("name")
            if isinstance(name, str) and node.get("url") and node.get("id"):
                new = sanitize_asset_name(name, used=used_set)
                if new != name:
                    mapping[name] = new
                    node["name"] = new
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    if mapping:
        olds = sorted(mapping, key=len, reverse=True)

        def rewrite(node) -> None:
            if isinstance(node, dict):
                html = node.get("html")
                if isinstance(html, str):
                    for old in olds:
                        html = html.replace(old, mapping[old])
                    node["html"] = html
                for value in node.values():
                    rewrite(value)
            elif isinstance(node, list):
                for item in node:
                    rewrite(item)

        rewrite(obj)
    return mapping


def sanitize_dl_tasks(tasks: list, outdir: str | Path) -> list:
    out = []
    for task in tasks:
        item = dict(task)
        fn = item.get("filename")
        if isinstance(fn, str):
            item["filename"] = sanitize_task_filename(fn, outdir)
        out.append(item)
    return out


def url_basename_safe(url: str) -> str:
    parsed = urlparse(url)
    leaf = (parsed.path or "").rstrip("/").split("/")[-1]
    return sanitize_asset_name(unquote(leaf) if leaf else "asset")
