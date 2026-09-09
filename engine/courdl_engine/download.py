from __future__ import annotations

import sys
from pathlib import Path

from courdl_engine import progress
from courdl_engine.beautify import beautify_tree, load_cookies, safe_name
from courdl_engine.catalog import CatalogError, resolve_product
from courdl_engine.cookies import check_cookies_file
from courdl_engine.slug import slug_from_input


class DownloadError(RuntimeError):
    pass


def _patch_dl_coursera(workers: int):
    import dl_coursera
    import dl_coursera_run
    from dl_coursera.Downloader import DownloaderBuiltin
    from dl_coursera.lib.TaskScheduler import TaskScheduler

    orig_download = dl_coursera_run.download
    orig_version = dl_coursera_run.get_latest_app_version
    n = max(1, int(workers))

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

    dl_coursera_run.download = download_parallel
    dl_coursera_run.get_latest_app_version = lambda: dl_coursera.app_version
    return orig_download, orig_version


def run_dl_coursera(cookies: Path, outdir: Path, slug: str, workers: int = 4) -> None:
    import dl_coursera_run

    orig_download, orig_version = _patch_dl_coursera(workers)
    argv = [
        "dl_coursera",
        "--cookies",
        str(cookies),
        "--outdir",
        str(outdir),
        slug,
    ]
    old = sys.argv
    try:
        sys.argv = argv
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
        dl_coursera_run.download = orig_download
        dl_coursera_run.get_latest_app_version = orig_version


def _course_ready(dest: Path) -> bool:
    return dest.is_dir() and any(dest.iterdir())


def download_one(
    cookies: Path,
    outdir: Path,
    slug: str,
    *,
    skip_existing: bool = False,
    no_beautify: bool = False,
    workers: int = 4,
) -> Path:
    dest = outdir / slug
    if skip_existing and _course_ready(dest):
        progress.emit("skip", f"Already present, skipping download: {dest}")
        progress.log(f"Skip existing: {dest}")
        return dest

    progress.emit("download", "Starting dl_coursera", slug=slug)
    progress.log(f"Downloading {slug} into {outdir}")
    run_dl_coursera(cookies, outdir, slug, workers=workers)
    progress.emit("download", "dl_coursera finished", slug=slug)

    if not dest.exists():
        raise DownloadError(f"Download finished but folder missing: {dest}")

    if not no_beautify:
        progress.emit("beautify", "Renaming folders and writing README files")
        sess = load_cookies(cookies)
        beautify_tree(dest, sess)
        progress.emit("beautify", f"Beautified {dest}")
        progress.log(f"Beautified {dest}")
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
    workers: int = 4,
) -> Path:
    check_cookies_file(cookies)
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        product = resolve_product(raw_input)
    except CatalogError as exc:
        raise DownloadError(str(exc)) from exc

    courses = product.get("courses") or []
    kind = product.get("kind") or "course"
    progress.emit(
        "resolve",
        f"{product.get('name') or product.get('slug')} ({kind}, {len(courses)} course(s))",
        kind=kind,
        slug=product.get("slug"),
        current=0,
        total=len(courses) or 1,
    )
    for course in courses:
        progress.log(f"  {course.get('name')} -> {course.get('url')}")

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
        progress.emit("done", "Finished", path=str(dest))
        return dest

    root = outdir / safe_name(product.get("name") or product.get("slug") or "certificate")
    root.mkdir(parents=True, exist_ok=True)
    total = len(courses)
    for i, course in enumerate(courses, start=1):
        slug = course["slug"]
        progress.emit(
            "course",
            course.get("name") or slug,
            current=i,
            total=total,
            slug=slug,
        )
        download_one(
            cookies,
            root,
            slug,
            skip_existing=skip_existing,
            no_beautify=no_beautify,
            workers=workers,
        )
    _write_product_readme(root, product)
    progress.emit("done", f"Finished {total} courses", path=str(root), current=total, total=total)
    return root
