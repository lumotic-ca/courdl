#!/usr/bin/env python3
"""Download a CourDL course-list manifest into per-certificate folders.

Manifest: a certificate title on its own line, then one https://www.coursera.org/learn/… URL per line.
Blank lines are ignored. Lines starting with # are comments.

Professional-certificate URLs are not expanded here. List each course URL, the same way Coursera
shows them separately and the same way the CourDL desktop app needs them today.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from courdl_engine.cookies import CookieError, check_cookies_file  # noqa: E402
from courdl_engine.download import DownloadError, download  # noqa: E402
from courdl_engine.slug import SlugError, slug_from_input  # noqa: E402

UNSAFE = "".join(chr(c) for c in range(32)) + '<>:"/\\|?*'


def safe_cert_name(title: str) -> str:
    text = "".join("_" if ch in UNSAFE else ch for ch in title.strip())
    text = " ".join(text.split()).strip(" ._")
    return text or "Untitled certificate"


def parse_manifest(path: Path) -> list[tuple[str, list[str]]]:
    groups: list[tuple[str, list[str]]] = []
    current = "Ungrouped"
    urls: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
            continue
        if urls:
            groups.append((current, urls))
            urls = []
        current = line
    if urls:
        groups.append((current, urls))
    return [(name, u) for name, u in groups if u]


def course_ready(dest: Path) -> bool:
    if not dest.is_dir():
        return False
    return any(dest.iterdir())


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, symlinks=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", type=Path, required=True, help="Course Links.txt style manifest")
    parser.add_argument("--outdir", type=Path, required=True, help="Parent folder for certificate dirs")
    parser.add_argument("--cookies", type=Path, required=True)
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--no-beautify", action="store_true")
    args = parser.parse_args(argv)

    skip = not args.no_skip_existing
    try:
        check_cookies_file(args.cookies.resolve())
        groups = parse_manifest(args.links.resolve())
    except (CookieError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    total = sum(len(urls) for _, urls in groups)
    print(f"Certificates: {len(groups)}  courses: {total}", flush=True)
    args.outdir.mkdir(parents=True, exist_ok=True)

    slug_cache: dict[str, Path] = {}
    ok = fail = skipped = copied = 0
    done = 0
    failures: list[str] = []

    for cert, urls in groups:
        cert_dir = args.outdir / safe_cert_name(cert)
        cert_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {cert} ===", flush=True)
        for url in urls:
            done += 1
            try:
                slug = slug_from_input(url)
            except SlugError as exc:
                fail += 1
                failures.append(f"{cert} {url}: {exc}")
                print(f"[{done}/{total}] FAIL parse {url}: {exc}", flush=True)
                continue
            dest = cert_dir / slug
            if skip and course_ready(dest):
                skipped += 1
                slug_cache.setdefault(slug, dest)
                print(f"[{done}/{total}] skip {cert_dir.name}/{slug}", flush=True)
                continue
            cached = slug_cache.get(slug)
            if cached and course_ready(cached) and cached.resolve() != dest.resolve():
                try:
                    copy_tree(cached, dest)
                    copied += 1
                    print(f"[{done}/{total}] copy {slug} -> {cert_dir.name}/", flush=True)
                    continue
                except OSError as exc:
                    print(f"[{done}/{total}] copy failed, will download: {exc}", flush=True)
            print(f"[{done}/{total}] download {slug} -> {cert_dir.name}/", flush=True)
            try:
                path = download(
                    args.cookies.resolve(),
                    cert_dir,
                    url,
                    skip_existing=skip,
                    no_beautify=args.no_beautify,
                )
                slug_cache[slug] = path
                ok += 1
            except (CookieError, SlugError, DownloadError, Exception) as exc:
                fail += 1
                msg = f"{cert} {slug}: {exc}"
                failures.append(msg)
                print(f"[{done}/{total}] FAIL {msg}", flush=True)

    summary = (
        f"\nDone. downloaded={ok} copied={copied} skipped={skipped} failed={fail} total={total}"
    )
    print(summary, flush=True)
    if failures:
        print("Failures:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
