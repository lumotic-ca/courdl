#!/usr/bin/env python3
"""Download a CourDL course-list manifest into per-certificate folders.

Resumable. Parallel course jobs (default 4, max 10) plus per-course file workers (default 3).
Writes outdir/_batch-state.json. Touch outdir/_batch.stop to halt after the current certificate.

Manifest: certificate title on its own line, then one /learn/ URL per line.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from courdl_engine.cookies import CookieError, check_cookies_file  # noqa: E402
from courdl_engine.download import DownloadError, _course_ready as course_ready, download  # noqa: E402
from courdl_engine.slug import SlugError, slug_from_input  # noqa: E402

UNSAFE = "".join(chr(c) for c in range(32)) + '<>:"/\\|?*'
STATE_NAME = "_batch-state.json"
STOP_NAME = "_batch.stop"


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


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, symlinks=True)


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {
            "completedCerts": [],
            "completedCourses": [],
            "failed": [],
            "nextCert": None,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "completedCerts": [],
            "completedCourses": [],
            "failed": [],
            "nextCert": None,
        }


def save_state(path: Path, state: dict) -> None:
    state["updatedAt"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def stop_requested(outdir: Path) -> bool:
    return (outdir / STOP_NAME).is_file()


def key_for(cert: str, slug: str) -> str:
    return f"{safe_cert_name(cert)}/{slug}"


def download_with_retry(cookies: Path, cert_dir: Path, url: str, skip: bool, no_beautify: bool, workers: int):
    last = None
    for attempt in range(1, 4):
        try:
            return download(
                cookies,
                cert_dir,
                url,
                skip_existing=skip,
                no_beautify=no_beautify,
                workers=workers,
            )
        except (CookieError, DownloadError, Exception) as exc:
            last = exc
            wait = min(8 * attempt, 24)
            print(f"  retry {attempt}/3 in {wait}s: {exc}", flush=True)
            time.sleep(wait)
    raise last


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--cookies", type=Path, required=True)
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--no-beautify", action="store_true")
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Concurrent course downloads (1-10). Default 4. Stay at 4-6 to avoid Coursera 429s.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="File download threads inside each course. Default 3.",
    )
    args = parser.parse_args(argv)

    jobs = max(1, min(10, args.jobs))
    workers = max(1, min(8, args.workers))
    skip = not args.no_skip_existing
    outdir = args.outdir.resolve()
    state_path = outdir / STATE_NAME
    cookies = args.cookies.resolve()

    try:
        check_cookies_file(cookies)
        groups = parse_manifest(args.links.resolve())
    except (CookieError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    outdir.mkdir(parents=True, exist_ok=True)
    state = load_state(state_path)
    completed_certs = set(state.get("completedCerts") or [])
    completed_courses = set(state.get("completedCourses") or [])
    failures: list[str] = list(state.get("failed") or [])

    total = sum(len(urls) for _, urls in groups)
    print(
        f"Certificates: {len(groups)}  courses: {total}  jobs={jobs}  workers={workers}",
        flush=True,
    )
    if completed_certs:
        print(f"Resuming. Completed certs: {len(completed_certs)}", flush=True)

    lock = threading.Lock()
    slug_cache: dict[str, Path] = {}
    ok = skipped = copied = fail = 0

    def cache_put(slug: str, path: Path) -> None:
        with lock:
            slug_cache.setdefault(slug, path)

    def cache_get(slug: str) -> Path | None:
        with lock:
            return slug_cache.get(slug)

    def mark_course(cert: str, slug: str) -> None:
        completed_courses.add(key_for(cert, slug))
        state["completedCourses"] = sorted(completed_courses)
        save_state(state_path, state)

    def one_course(cert: str, url: str, idx: int) -> str:
        nonlocal ok, skipped, copied, fail
        cert_dir = outdir / safe_cert_name(cert)
        cert_dir.mkdir(parents=True, exist_ok=True)
        try:
            slug = slug_from_input(url)
        except SlugError as exc:
            with lock:
                fail += 1
                failures.append(f"{cert} {url}: {exc}")
                state["failed"] = failures
                save_state(state_path, state)
            print(f"[{idx}/{total}] FAIL parse {url}: {exc}", flush=True)
            return "fail"
        dest = cert_dir / slug
        k = key_for(cert, slug)
        if skip and course_ready(dest):
            cache_put(slug, dest)
            with lock:
                skipped += 1
                completed_courses.add(k)
                state["completedCourses"] = sorted(completed_courses)
                save_state(state_path, state)
            print(f"[{idx}/{total}] skip {cert_dir.name}/{slug}", flush=True)
            return "skip"
        cached = cache_get(slug)
        if cached and course_ready(cached) and cached.resolve() != dest.resolve():
            try:
                copy_tree(cached, dest)
                cache_put(slug, dest)
                with lock:
                    copied += 1
                mark_course(cert, slug)
                print(f"[{idx}/{total}] copy {slug} -> {cert_dir.name}/", flush=True)
                return "copy"
            except OSError as exc:
                print(f"[{idx}/{total}] copy failed, will download: {exc}", flush=True)
        print(f"[{idx}/{total}] download {slug} -> {cert_dir.name}/", flush=True)
        try:
            path = download_with_retry(
                cookies, cert_dir, url, skip, args.no_beautify, workers
            )
            cache_put(slug, path)
            with lock:
                ok += 1
            mark_course(cert, slug)
            return "ok"
        except (CookieError, SlugError, DownloadError, Exception) as exc:
            with lock:
                fail += 1
                failures.append(f"{cert} {slug}: {exc}")
                state["failed"] = failures
                save_state(state_path, state)
            print(f"[{idx}/{total}] FAIL {cert} {slug}: {exc}", flush=True)
            return "fail"

    global_i = 0
    stopped = False
    for cert, urls in groups:
        if safe_cert_name(cert) in completed_certs or cert in completed_certs:
            global_i += len(urls)
            print(f"\n=== {cert} (already complete) ===", flush=True)
            continue
        if stop_requested(outdir):
            state["nextCert"] = cert
            save_state(state_path, state)
            print(f"\nStop requested before {cert}. Resume from here.", flush=True)
            stopped = True
            break

        cert_dir = outdir / safe_cert_name(cert)
        cert_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {cert} ===", flush=True)
        state["nextCert"] = cert
        save_state(state_path, state)

        pending: list[tuple[int, str]] = []
        for url in urls:
            global_i += 1
            pending.append((global_i, url))

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futs = [pool.submit(one_course, cert, url, idx) for idx, url in pending]
            for fut in as_completed(futs):
                fut.result()

        completed_certs.add(safe_cert_name(cert))
        state["completedCerts"] = sorted(completed_certs)
        remaining = [name for name, _ in groups if safe_cert_name(name) not in completed_certs]
        state["nextCert"] = remaining[0] if remaining else None
        save_state(state_path, state)
        print(f"Finished certificate: {cert}", flush=True)

        if stop_requested(outdir):
            print("Stop requested. Checkpoint saved.", flush=True)
            stopped = True
            break

    summary = (
        f"\nDone. downloaded={ok} copied={copied} skipped={skipped} failed={fail} "
        f"stopped={stopped} total={total}"
    )
    print(summary, flush=True)
    print(f"State: {state_path}", flush=True)
    if failures:
        print("Failures:", file=sys.stderr)
        for line in failures[-20:]:
            print(f"  {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
