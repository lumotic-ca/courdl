from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import threading
from pathlib import Path

import requests

from courdl_engine import progress
from courdl_engine.beautify import (
    apply_certificate_order,
    beautify_tree,
    find_existing_course_dir,
    load_cookies,
    numbered_course,
    safe_name,
    save_product,
)
from courdl_engine.catalog import CatalogError, resolve_product
from courdl_engine.cookies import check_cookies_file
from courdl_engine.paths import (
    PATH_SCHEMA_VERSION,
    sanitize_asset_name,
    sanitize_dl_tasks,
    url_basename_safe,
    walk_sanitize_assets,
    win_extended_path,
)
from courdl_engine.slug import slug_from_input


class DownloadError(RuntimeError):
    pass


_CRAWL_LOCK = threading.Lock()
_PATCH_LOCK = threading.Lock()
_PATCHED = False
_tls = threading.local()


def _emit(*args, **kwargs) -> None:
    progress.emit(*args, **kwargs)


def _log(message: str) -> None:
    progress.log(message)


def _failed_tasks_file(dest: Path) -> Path:
    return dest / ".cache" / "download.dl_tasks_failed.json"


def _path_schema_file(outdir: Path, slug: str) -> Path:
    return Path(outdir) / slug / ".cache" / "courdl-path-schema"


def _bust_stale_path_cache(outdir: Path, slug: str) -> None:
    import dl_coursera_run

    marker = _path_schema_file(outdir, slug)
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == PATH_SCHEMA_VERSION:
        return
    cache = Path(outdir) / slug / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    Path(dl_coursera_run._file_pkl_crawl(outdir, slug)).unlink(missing_ok=True)
    Path(dl_coursera_run._file_json_gather(outdir, slug)).unlink(missing_ok=True)
    _failed_tasks_file(Path(outdir) / slug).unlink(missing_ok=True)
    marker.write_text(PATH_SCHEMA_VERSION + "\n", encoding="utf-8")


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
    from dl_coursera.define import Asset as CourseraAsset
    from dl_coursera.lib import misc as dl_misc

    with _PATCH_LOCK:
        if _PATCHED:
            return
        orig_get = requests.Session.get
        orig_crawl = dl_coursera_run.crawl
        orig_gather = dl_coursera_run.gather_dl_tasks
        orig_download = dl_coursera_run.download
        orig_dl = DownloaderBuiltin._dl
        orig_asset_init = CourseraAsset.__init__

        def asset_init(self, id_, url, name):
            orig_asset_init(self, id_, url, sanitize_asset_name(str(name or "asset")))

        def get_patched(self, url, *args, **kwargs):
            resp = orig_get(self, url, *args, **kwargs)
            if "onDemandSpecializations.v1" in str(url):
                return _SpecProbeResponse(resp)
            return resp

        def crawl_sanitized(cookies_file, slug, outdir):
            dest = Path(outdir) / slug
            _bust_stale_path_cache(Path(outdir), slug)
            pkl = Path(dl_coursera_run._file_pkl_crawl(outdir, slug))
            if pkl.exists() and not _course_ready(dest):
                pkl.unlink(missing_ok=True)
                Path(dl_coursera_run._file_json_gather(outdir, slug)).unlink(missing_ok=True)
            with _CRAWL_LOCK:
                soc = orig_crawl(cookies_file, slug, outdir)
            walk_sanitize_assets(soc)
            pkl.parent.mkdir(parents=True, exist_ok=True)
            with open(pkl, "wb") as ofs:
                pickle.dump(soc, ofs)
            _path_schema_file(Path(outdir), slug).write_text(
                PATH_SCHEMA_VERSION + "\n", encoding="utf-8"
            )
            return soc

        def gather_sanitized(outdir, soc):
            walk_sanitize_assets(soc)
            tasks = orig_gather(outdir, soc)
            return sanitize_dl_tasks(tasks, outdir)

        def builtin_dl(self, *, url, filename):
            return orig_dl(self, url=url, filename=win_extended_path(filename))

        def download_safe(dl_tasks, slug, outdir):
            dest = Path(outdir) / slug
            tasks = sanitize_dl_tasks(dl_tasks, dest)
            orig_download(tasks, slug, outdir)
            failed_path = _failed_tasks_file(dest)
            if failed_path.is_file():
                try:
                    failed = json.loads(failed_path.read_text(encoding="utf-8"))
                except Exception:
                    failed = []
                if failed:
                    _log(
                        f"{len(failed)} extra file(s) failed under {dest}. "
                        "Lecture videos can still be complete."
                    )
                    _emit(
                        "warn",
                        f"{len(failed)} extra file(s) failed. Lectures may still be OK.",
                        slug=slug,
                        failed=len(failed),
                        level="warn",
                    )

        orig_parse = argparse.ArgumentParser.parse_args

        def parse_args_tls(self, args=None, namespace=None):
            if args is None:
                av = getattr(_tls, "argv", None)
                if av:
                    args = list(av[1:])
            return orig_parse(self, args, namespace)

        CourseraAsset.__init__ = asset_init
        dl_misc.url_basename = url_basename_safe
        requests.Session.get = get_patched
        dl_coursera_run.crawl = crawl_sanitized
        dl_coursera_run.gather_dl_tasks = gather_sanitized
        DownloaderBuiltin._dl = builtin_dl
        dl_coursera_run.download = download_safe
        dl_coursera_run.get_latest_app_version = lambda: dl_coursera.app_version
        argparse.ArgumentParser.parse_args = parse_args_tls
        _PATCHED = True


def run_dl_coursera(cookies: Path, outdir: Path, slug: str) -> None:
    import dl_coursera_run

    os.environ["TQDM_DISABLE"] = "1"
    _tls.argv = [
        "dl_coursera",
        "--cookies",
        str(cookies),
        "--outdir",
        str(outdir),
        slug,
    ]
    _ensure_patches()
    old = sys.argv
    try:
        sys.argv = list(_tls.argv)
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
    finally:
        sys.argv = old


def download_one(
    cookies: Path,
    outdir: Path,
    slug: str,
    *,
    skip_existing: bool = False,
    no_beautify: bool = False,
) -> Path:
    dest = outdir / slug
    existing = find_existing_course_dir(outdir, slug)
    _emit("dest", f"Writing {dest}", path=str(existing or dest), slug=slug)
    if skip_existing and existing and _course_ready(existing):
        _emit("skip", f"Already present, skipping download: {existing}")
        _log(f"Skip existing: {existing}")
        return existing

    _emit("download", "Starting dl_coursera", slug=slug)
    _log(f"Downloading {slug} into {outdir}")
    run_dl_coursera(cookies, outdir, slug)
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
    used: set[str] = set()
    for i, course in enumerate(product.get("courses") or [], start=1):
        name = course.get("name") or course.get("slug")
        slug = course.get("slug")
        folder = numbered_course(i, name or "course", used)
        url = course.get("url") or f"https://www.coursera.org/learn/{slug}"
        lines.append(f"{i}. [{name}]({folder}/README.md) (`{url}`)")
    lines.append("")
    (root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def download(
    cookies: Path,
    outdir: Path,
    raw_input: str,
    *,
    skip_existing: bool = False,
    no_beautify: bool = False,
) -> Path:
    check_cookies_file(cookies)
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        product = resolve_product(raw_input)
    except CatalogError as exc:
        raise DownloadError(str(exc)) from exc

    courses = product.get("courses") or []
    kind = product.get("kind") or "course"
    _emit(
        "resolve",
        f"{product.get('name') or product.get('slug')} ({kind}, {len(courses)} course(s))",
        kind=kind,
        slug=product.get("slug"),
        current=0,
        total=len(courses) or 1,
    )

    if kind == "course" or len(courses) <= 1:
        slug = courses[0]["slug"] if courses else slug_from_input(raw_input)
        dest = download_one(
            cookies,
            outdir,
            slug,
            skip_existing=skip_existing,
            no_beautify=no_beautify,
        )
        _emit("done", "Finished", path=str(dest))
        return dest

    root = outdir / safe_name(product.get("name") or product.get("slug") or "certificate")
    root.mkdir(parents=True, exist_ok=True)
    total = len(courses)
    _log(f"Certificate download: {total} courses, one at a time")
    for i, course in enumerate(courses, start=1):
        slug = course["slug"]
        name = course.get("name") or slug
        _emit("course", name, current=i, total=total, slug=slug)
        download_one(
            cookies,
            root,
            slug,
            skip_existing=skip_existing,
            no_beautify=no_beautify,
        )
    apply_certificate_order(root, courses)
    save_product(root, product)
    _write_product_readme(root, product)
    _emit("done", f"Finished {total} courses", path=str(root), current=total, total=total)
    return root
