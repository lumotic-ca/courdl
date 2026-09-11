from __future__ import annotations

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from courdl_engine import progress
from courdl_engine.adaptive import AdaptiveGate, looks_rate_limited
from courdl_engine.beautify import beautify_tree, load_cookies, safe_name
from courdl_engine.catalog import CatalogError, resolve_product
from courdl_engine.cookies import check_cookies_file
from courdl_engine.slug import slug_from_input

_CRAWL_LOCK = threading.Lock()
_PROGRESS_LOCK = threading.Lock()


def _emit(*args, **kwargs) -> None:
    with _PROGRESS_LOCK:
        progress.emit(*args, **kwargs)


def _log(message: str) -> None:
    with _PROGRESS_LOCK:
        progress.log(message)


class DownloadError(RuntimeError):
    pass


_PATCH_LOCK = threading.Lock()
_PATCHED = False
_tls = threading.local()


def _course_ready(dest: Path) -> bool:
    if not dest.is_dir():
        return False
    for path in dest.rglob("*"):
        if not path.is_file() or ".cache" in path.parts:
            continue
        if path.suffix.lower() in {".mp4", ".srt", ".html", ".htm"}:
            return True
    return False


class _SpecProbeResponse:
    def __init__(self, inner):
        self._inner = inner

    def json(self):
        data = self._inner.json()
        if isinstance(data, dict) and not data.get("elements"):
            data = dict(data)
            data.pop("elements", None)
        return data

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _ensure_patches() -> None:
    global _PATCHED
    import dl_coursera
    import dl_coursera_run
    from dl_coursera.Downloader import DownloaderBuiltin
    from dl_coursera.lib.TaskScheduler import TaskScheduler

    with _PATCH_LOCK:
        if _PATCHED:
            return
        orig_get = requests.Session.get
        orig_crawl = dl_coursera_run.crawl

        def get_patched(self, url, *args, **kwargs):
            resp = orig_get(self, url, *args, **kwargs)
            if "onDemandSpecializations.v1" in str(url):
                return _SpecProbeResponse(resp)
            return resp

        def crawl_locked(cookies_file, slug, outdir):
            dest = Path(outdir) / slug
            pkl = Path(dl_coursera_run._file_pkl_crawl(outdir, slug))
            if pkl.exists() and not _course_ready(dest):
                pkl.unlink(missing_ok=True)
                Path(dl_coursera_run._file_json_gather(outdir, slug)).unlink(missing_ok=True)
            with _CRAWL_LOCK:
                return orig_crawl(cookies_file, slug, outdir)

        def download_parallel(dl_tasks, slug, outdir):
            file_json = dl_coursera_run._file_json_download_dl_tasks_failed(outdir, slug)
            if Path(file_json).exists():
                import json

                with open(file_json, encoding="UTF-8") as ifs:
                    dl_tasks = json.load(ifs)
            if len(dl_tasks) == 0:
                return
            from tqdm import tqdm
            import json

            n = max(1, int(getattr(_tls, "file_workers", 2)))
            with TaskScheduler() as ts:
                with tqdm(
                    desc="Downloading...",
                    bar_format="{bar:31} [{percentage:3.0f}%] {n_fmt}/{total_fmt} {desc}",
                    total=len(dl_tasks),
                ) as bar:

                    def _hook_done():
                        bar.update(1)
                        bar.refresh()

                    def _hook_retry():
                        bar.refresh()

                    ts.start(n_worker=n, hook_done=_hook_done, hook_retry=_hook_retry)
                    dl_tasks_failed = DownloaderBuiltin(dl_tasks=dl_tasks, ts=ts).download()

            with open(file_json, "w", encoding="UTF-8") as ofs:
                json.dump(dl_tasks_failed, ofs, indent=4)

        orig_parse = argparse.ArgumentParser.parse_args

        def parse_args_tls(self, args=None, namespace=None):
            if args is None:
                av = getattr(_tls, "argv", None)
                if av:
                    args = list(av[1:])
            return orig_parse(self, args, namespace)

        requests.Session.get = get_patched
        dl_coursera_run.crawl = crawl_locked
        dl_coursera_run.download = download_parallel
        dl_coursera_run.get_latest_app_version = lambda: dl_coursera.app_version
        argparse.ArgumentParser.parse_args = parse_args_tls
        _PATCHED = True


def run_dl_coursera(cookies: Path, outdir: Path, slug: str, workers: int = 2) -> None:
    import dl_coursera_run

    _tls.file_workers = max(1, int(workers))
    _tls.argv = [
        "dl_coursera",
        "--cookies",
        str(cookies),
        "--outdir",
        str(outdir),
        slug,
    ]
    _ensure_patches()
    try:
        dl_coursera_run.main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code not in (0, None):
            raise DownloadError(f"dl_coursera exited with code {code}") from exc
    except Exception as exc:
        name = type(exc).__name__
        msg = str(exc) or name
        if "CookiesExpired" in name or "expired" in msg.lower():
            raise DownloadError(
                "Coursera cookies expired. Export a fresh Netscape cookies.txt while logged in."
            ) from exc
        if "NotFound" in name:
            raise DownloadError(f"Course or certificate not found: {slug}") from exc
        raise DownloadError(msg) from exc


def download_one(
    cookies: Path,
    outdir: Path,
    slug: str,
    *,
    skip_existing: bool = False,
    no_beautify: bool = False,
    workers: int = 2,
) -> Path:
    dest = outdir / slug
    if skip_existing and _course_ready(dest):
        _emit("skip", f"Already present, skipping download: {dest}")
        _log(f"Skip existing: {dest}")
        return dest

    _emit("download", "Starting dl_coursera", slug=slug)
    _log(f"Downloading {slug} into {outdir}")
    run_dl_coursera(cookies, outdir, slug, workers=workers)
    _emit("download", "dl_coursera finished", slug=slug)

    if not dest.exists():
        raise DownloadError(f"Download finished but folder missing: {dest}")
    if not _course_ready(dest):
        raise DownloadError(
            f"Download finished but no lecture files (mp4, srt, or html) in {dest}"
        )

    if not no_beautify:
        cache = dest / ".cache" / "crawl.json"
        if not cache.is_file():
            raise DownloadError(f"No crawl.json under {dest}")
        _emit("beautify", "Renaming folders and writing README files")
        sess = load_cookies(cookies)
        try:
            beautify_tree(dest, sess)
        except SystemExit as exc:
            raise DownloadError(str(exc) or f"Beautify failed for {dest}") from exc
        _emit("beautify", f"Beautified {dest}")
        _log(f"Beautified {dest}")
    return dest


def _write_product_readme(root: Path, product: dict) -> None:
    lines = [
        f"# {product.get('name') or product.get('slug')}",
        "",
        "Courses in syllabus order:",
        "",
    ]
    for i, course in enumerate(product.get("courses") or [], start=1):
        name = course.get("name") or course.get("slug")
        slug = course.get("slug")
        url = course.get("url") or f"https://www.coursera.org/learn/{slug}"
        lines.append(f"{i}. [{name}]({slug}/) (`{url}`)")
    lines.append("")
    (root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def download(
    cookies: Path,
    outdir: Path,
    raw_input: str,
    *,
    skip_existing: bool = False,
    no_beautify: bool = False,
    workers: int = 2,
    jobs: int = 5,
    jobs_min: int = 3,
    adaptive: bool = True,
) -> Path:
    check_cookies_file(cookies)
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        product = resolve_product(raw_input)
    except CatalogError as exc:
        raise DownloadError(str(exc)) from exc

    courses = product.get("courses") or []
    kind = product.get("kind") or "course"
    jobs = max(1, min(10, int(jobs)))
    jobs_min = max(1, min(jobs, int(jobs_min)))
    workers = max(1, min(8, int(workers)))
    _emit(
        "resolve",
        f"{product.get('name') or product.get('slug')} ({kind}, {len(courses)} course(s))",
        kind=kind,
        slug=product.get("slug"),
        current=0,
        total=len(courses) or 1,
    )
    for course in courses:
        _log(f"  {course.get('name')} -> {course.get('url')}")

    if kind == "course" or len(courses) <= 1:
        slug = courses[0]["slug"] if courses else slug_from_input(raw_input)
        dest = download_one(
            cookies,
            outdir,
            slug,
            skip_existing=skip_existing,
            no_beautify=no_beautify,
            workers=workers,
        )
        _emit("done", "Finished", path=str(dest))
        return dest

    root = outdir / safe_name(product.get("name") or product.get("slug") or "certificate")
    root.mkdir(parents=True, exist_ok=True)
    total = len(courses)
    low = jobs_min if adaptive else jobs
    gate = AdaptiveGate(high=jobs, low=low, recover_after=4)
    extra = f"; slows to {gate.low} on rate limits" if adaptive and gate.low < gate.high else ""
    _log(
        f"Certificate download: up to {gate.high} courses at once, "
        f"{workers} file workers each{extra}"
    )
    done_n = 0
    done_lock = threading.Lock()
    errors: list[str] = []

    def work(course: dict) -> None:
        nonlocal done_n
        slug = course["slug"]
        name = course.get("name") or slug
        gate.enter()
        saw_429 = False
        try:
            last: BaseException | None = None
            for attempt in range(1, 4):
                try:
                    _emit("course", name, current=done_n, total=total, slug=slug)
                    download_one(
                        cookies,
                        root,
                        slug,
                        skip_existing=skip_existing,
                        no_beautify=no_beautify,
                        workers=workers,
                    )
                    last = None
                    break
                except Exception as exc:
                    last = exc
                    saw_429 = saw_429 or looks_rate_limited(exc)
                    if attempt == 3:
                        raise
                    wait = min(8 * attempt, 24)
                    _log(f"{slug}: retry {attempt}/3 in {wait}s ({exc})")
                    time.sleep(wait)
            if last:
                raise last
        finally:
            limit = gate.leave(rate_limited=saw_429)
            if saw_429:
                _log(f"Coursera rate limit. Concurrent courses now {limit}.")
            with done_lock:
                done_n += 1
                n = done_n
            _emit("course", name, current=n, total=total, slug=slug)

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futs = [pool.submit(work, course) for course in courses]
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as exc:
                errors.append(str(exc))
    if errors:
        raise DownloadError(
            f"{len(errors)} course(s) failed: " + "; ".join(errors[:5])
        )
    _write_product_readme(root, product)
    _emit("done", f"Finished {total} courses", path=str(root), current=total, total=total)
    return root
