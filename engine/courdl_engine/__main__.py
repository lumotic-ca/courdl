from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import dl_coursera

from courdl_engine import ENGINE_VERSION, DL_COURSERA_PIN
from courdl_engine.beautify import beautify_tree, load_cookies
from courdl_engine.catalog import CatalogError, resolve_product
from courdl_engine.cookies import CookieError, check_cookies_file
from courdl_engine.download import DownloadError, download
from courdl_engine.slug import SlugError


def _cmd_version(_args: argparse.Namespace) -> int:
    print(
        json.dumps(
            {
                "engine": ENGINE_VERSION,
                "dl_coursera": getattr(dl_coursera, "app_version", DL_COURSERA_PIN),
                "dl_coursera_pin": DL_COURSERA_PIN,
            }
        )
    )
    return 0


def _cmd_check_cookies(args: argparse.Namespace) -> int:
    try:
        info = check_cookies_file(args.file.resolve())
    except CookieError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(info))
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    try:
        product = resolve_product(args.input)
    except (SlugError, CatalogError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(product, ensure_ascii=False, indent=2 if args.pretty else None))
    sys.stdout.flush()
    return 0


def _cmd_download(args: argparse.Namespace) -> int:
    try:
        dest = download(
            args.cookies.resolve(),
            args.outdir.resolve(),
            args.input,
            skip_existing=args.skip_existing,
            no_beautify=args.no_beautify,
        )
    except (CookieError, SlugError, DownloadError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1
    print(str(dest))
    return 0


def _cmd_beautify(args: argparse.Namespace) -> int:
    root = args.path.resolve()
    cookies = args.cookies.resolve() if args.cookies else None
    try:
        if cookies:
            check_cookies_file(cookies)
        sess = load_cookies(cookies) if cookies else None
        beautify_tree(root, sess)
    except CookieError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Beautified {root}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="courdl-engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("version")
    p_ver.set_defaults(func=_cmd_version)

    p_ck = sub.add_parser("check-cookies")
    p_ck.add_argument("--file", type=Path, required=True)
    p_ck.set_defaults(func=_cmd_check_cookies)

    p_res = sub.add_parser("resolve")
    p_res.add_argument("--input", required=True)
    p_res.add_argument("--pretty", action="store_true")
    p_res.set_defaults(func=_cmd_resolve)

    p_dl = sub.add_parser("download")
    p_dl.add_argument("--cookies", type=Path, required=True)
    p_dl.add_argument("--outdir", type=Path, required=True)
    p_dl.add_argument("--input", required=True)
    p_dl.add_argument("--skip-existing", action="store_true")
    p_dl.add_argument("--no-beautify", action="store_true")
    p_dl.set_defaults(func=_cmd_download)

    p_bf = sub.add_parser("beautify")
    p_bf.add_argument("--path", type=Path, required=True)
    p_bf.add_argument("--cookies", type=Path)
    p_bf.set_defaults(func=_cmd_beautify)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
