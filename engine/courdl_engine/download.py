from __future__ import annotations

import sys
from pathlib import Path

from courdl_engine import progress
from courdl_engine.beautify import beautify_tree, load_cookies
from courdl_engine.cookies import check_cookies_file
from courdl_engine.slug import slug_from_input


class DownloadError(RuntimeError):
    pass


def run_dl_coursera(cookies: Path, outdir: Path, slug: str) -> None:
    import dl_coursera_run

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


def download(
    cookies: Path,
    outdir: Path,
    raw_input: str,
    *,
    skip_existing: bool = False,
    no_beautify: bool = False,
) -> Path:
    check_cookies_file(cookies)
    slug = slug_from_input(raw_input)
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / slug
    progress.emit("resolve", f"Slug: {slug}", slug=slug)

    if skip_existing and dest.exists() and any(dest.iterdir()):
        progress.emit("skip", f"Already present, skipping download: {dest}")
        progress.log(f"Skip existing: {dest}")
    else:
        progress.emit("download", "Starting dl_coursera")
        progress.log(f"Downloading {slug} into {outdir}")
        run_dl_coursera(cookies, outdir, slug)
        progress.emit("download", "dl_coursera finished")

    if not dest.exists():
        raise DownloadError(f"Download finished but folder missing: {dest}")

    if not no_beautify:
        progress.emit("beautify", "Renaming folders and writing README files")
        sess = load_cookies(cookies)
        beautify_tree(dest, sess)
        progress.emit("beautify", f"Beautified {dest}")
        progress.log(f"Beautified {dest}")

    progress.emit("done", "Finished", path=str(dest))
    return dest
