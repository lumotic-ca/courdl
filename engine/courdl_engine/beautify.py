#!/usr/bin/env python3
"""Rename dl_coursera output and write a table of contents.

Keeps syllabus order numbers. Uses Coursera display names instead of truncated
slugs. Fetches module descriptions when cookies are available.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import requests

UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
DASHES = re.compile(r"[\u2010-\u2015\u2212]")
WS = re.compile(r"\s+")
UNTITLED = re.compile(r"^(untitled|untitled-lesson|untitled lesson)$", re.I)


def slug_from_url_or_slug(value: str) -> str:
    value = value.strip().rstrip("/")
    m = re.search(
        r"coursera\.org/(?:learn|specializations|professional-certificates)/([^/?#]+)",
        value,
    )
    if m:
        return m.group(1)
    return value.split("/")[-1]


def safe_name(text: str, max_len: int = 80) -> str:
    text = DASHES.sub("-", text or "")
    text = WS.sub(" ", text).strip()
    text = UNSAFE.sub("", text)
    text = text.replace("@", " ")
    text = WS.sub(" ", text).strip(" ._")
    if len(text) > max_len:
        text = text[:max_len].rstrip(" .-")
    return text or "untitled"


def numbered(index: int, title: str) -> str:
    return f"{index:02d} - {safe_name(title)}"


def load_cookies(path: Path) -> requests.Session | None:
    if not path.is_file():
        return None
    cj = MozillaCookieJar()
    cj.load(str(path), ignore_discard=True, ignore_expires=True)
    sess = requests.Session()
    sess.cookies.update(cj)
    sess.headers["User-Agent"] = "Mozilla/5.0 (compatible; coursera-offline/1.0)"
    return sess


def fetch_enrichment(sess: requests.Session, slug: str) -> dict:
    out = {"description": "", "modules": {}}
    try:
        r = sess.get(
            "https://www.coursera.org/api/onDemandCourses.v1",
            params={"q": "slug", "slug": slug, "fields": "name,description"},
            timeout=30,
        )
        el = (r.json().get("elements") or [{}])[0]
        if el.get("slug") == slug:
            out["description"] = (el.get("description") or "").strip()
    except Exception:
        pass
    try:
        r = sess.get(
            "https://www.coursera.org/api/onDemandCourseMaterials.v2/",
            params={
                "q": "slug",
                "slug": slug,
                "includes": "modules,lessons,items",
                "fields": (
                    "moduleIds,"
                    "onDemandCourseMaterialModules.v1(name,slug,description,timeCommitment,lessonIds),"
                    "onDemandCourseMaterialLessons.v1(name,slug,elementIds),"
                    "onDemandCourseMaterialItems.v2(name,slug,contentSummary,isLocked,itemLockedReasonCode)"
                ),
                "showLockedItems": "true",
            },
            timeout=30,
        )
        linked = r.json().get("linked") or {}
        for mod in linked.get("onDemandCourseMaterialModules.v1") or []:
            out["modules"][mod.get("id")] = {
                "description": (mod.get("description") or "").strip(),
                "name": mod.get("name") or "",
            }
        skipped = []
        for item in linked.get("onDemandCourseMaterialItems.v2") or []:
            t = (item.get("contentSummary") or {}).get("typeName")
            if t in ("lecture", "supplement"):
                continue
            skipped.append(
                {
                    "name": item.get("name") or item.get("slug") or "item",
                    "type": t or "unknown",
                    "locked": bool(item.get("isLocked")),
                    "moduleId": item.get("moduleId"),
                }
            )
        out["skipped"] = skipped
    except Exception:
        out.setdefault("skipped", [])
    return out


def old_dir_name(index: int, slug: str) -> str:
    slug = slug or "untitled"
    if len(slug) > 40:
        slug = slug[:40]
    return f"{index:02d}@{slug}"


def resolve_course_dir(root: Path, index: int, course: dict) -> Path:
    slug = (course.get("slug") or "").strip()
    name = course.get("name") or slug or "course"
    candidates = [
        root / numbered(index, name),
        root / f"{index:02d}@{slug}",
        root / old_dir_name(index, slug),
        root / slug,
    ]
    for path in candidates:
        if path.is_dir():
            return path
    prefix = f"{index:02d}@"
    slug_key = slug[:40]
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not child.name.startswith(prefix):
            continue
        suffix = child.name[len(prefix) :]
        if slug.startswith(suffix) or suffix.startswith(slug_key) or slug_key.startswith(suffix):
            return child
    raise FileNotFoundError(f"No course folder for {index:02d}: {slug or name}")


def flatten_untitled_lessons(module_dir: Path) -> None:
    if not module_dir.is_dir():
        return
    for child in list(module_dir.iterdir()):
        if not child.is_dir():
            continue
        stem = child.name.split("@", 1)[-1]
        label = child.name.split(" - ", 1)[-1] if " - " in child.name else stem
        if not UNTITLED.match(label.replace("-", " ")) and not UNTITLED.match(stem.replace("-", " ")):
            continue
        for item in list(child.iterdir()):
            dest = module_dir / item.name
            if dest.exists():
                continue
            shutil.move(str(item), str(dest))
        if not any(child.iterdir()):
            child.rmdir()


def rename_path(src: Path, dest: Path) -> Path:
    if src == dest:
        return src
    if not src.exists():
        return dest if dest.exists() else src
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dest)
    return dest


def rename_media(item_dir: Path, title: str) -> None:
    if not item_dir.is_dir():
        return
    videos = sorted(item_dir.glob("[0-9][0-9]@.mp4"))
    for i, mp4 in enumerate(videos, start=1):
        base = numbered(i, title) if len(videos) == 1 else numbered(i, f"{title} ({i})")
        rename_path(mp4, item_dir / f"{base}.mp4")
        srt = mp4.with_suffix(".srt")
        if srt.exists():
            rename_path(srt, item_dir / f"{base}.srt")
    for html in sorted(item_dir.glob("[0-9][0-9]@*.html")):
        rename_path(html, item_dir / f"{numbered(1, title)}.html")


def skipped_label(kind: str) -> str:
    return {
        "ungradedAssignment": "practice assignment",
        "staffGraded": "graded project",
        "quiz": "quiz",
        "exam": "exam",
        "notebook": "notebook",
        "programming": "programming assignment",
        "gradedProgramming": "graded programming assignment",
        "discussionPrompt": "discussion",
        "ungradedLab": "lab",
    }.get(kind, kind)


def already_beautified(course_dir: Path) -> bool:
    if not course_dir.is_dir():
        return False
    return any(
        p.is_dir() and re.match(r"^\d{2} - ", p.name) for p in course_dir.iterdir()
    )


def write_course_readme(course_dir: Path, course: dict, enrich: dict) -> None:
    lines = [f"# {course.get('name') or course.get('slug')}", ""]
    lines += [
        f"Source slug: `{course.get('slug')}`",
        "",
        "Lectures and readings are in numbered folders. Quizzes, labs, and assignments are listed below when Coursera exposes them in the syllabus; `dl_coursera` does not download those item types.",
        "",
        "## Contents",
        "",
    ]
    skipped_by_mod = {}
    for row in enrich.get("skipped") or []:
        skipped_by_mod.setdefault(row.get("moduleId"), []).append(row)

    for i, module in enumerate(course.get("modules") or [], start=1):
        title = module.get("name") or module.get("slug") or f"Module {i}"
        lines.append(f"### {i:02d}. {title}")
        lines.append("")
        mod_desc = (enrich.get("modules") or {}).get(module.get("id"), {}).get("description")
        if mod_desc:
            lines.append(mod_desc)
            lines.append("")
        for lesson in module.get("lessons") or []:
            lesson_name = lesson.get("name") or ""
            show_lesson = lesson_name and not UNTITLED.match(lesson_name)
            if show_lesson:
                lines.append(f"**{lesson_name}**")
                lines.append("")
            for item in lesson.get("items") or []:
                kind = "Video" if item.get("type") == "Lecture" else "Reading"
                lines.append(f"- {kind}: {item.get('name') or item.get('slug')}")
        for row in skipped_by_mod.get(module.get("id"), []):
            status = skipped_label(row["type"])
            if row.get("locked"):
                status += ", locked on Coursera"
            lines.append(f"- Not downloaded: {row['name']} ({status})")
        lines.append("")
    (course_dir / "README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def beautify_course(course_dir: Path, course: dict, sess: requests.Session | None) -> None:
    enrich = fetch_enrichment(sess, course["slug"]) if sess else {"modules": {}, "skipped": []}
    if already_beautified(course_dir):
        write_course_readme(course_dir, course, enrich)
        return
    for mi, module in enumerate(course.get("modules") or [], start=1):
        mod_old = course_dir / old_dir_name(mi, module.get("slug") or "")
        flatten_untitled_lessons(mod_old)
        for li, lesson in enumerate(module.get("lessons") or [], start=1):
            lesson_untitled = UNTITLED.match(lesson.get("name") or "") or UNTITLED.match(
                lesson.get("slug") or ""
            )
            for ii, item in enumerate(lesson.get("items") or [], start=1):
                item_old_name = old_dir_name(ii, item.get("slug") or "")
                if lesson_untitled:
                    item_old = mod_old / item_old_name
                else:
                    item_old = (
                        mod_old / old_dir_name(li, lesson.get("slug") or "") / item_old_name
                    )
                item_new = item_old.parent / numbered(ii, item.get("name") or item.get("slug") or "item")
                item_dir = rename_path(item_old, item_new)
                rename_media(item_dir, item.get("name") or item.get("slug") or "item")
            if not lesson_untitled:
                lesson_old = mod_old / old_dir_name(li, lesson.get("slug") or "")
                rename_path(
                    lesson_old,
                    mod_old / numbered(li, lesson.get("name") or lesson.get("slug") or "lesson"),
                )
        if mod_old.exists():
            rename_path(
                mod_old,
                course_dir / numbered(mi, module.get("name") or module.get("slug") or "module"),
            )
    refs = course_dir / "references"
    if refs.is_dir():
        rename_path(refs, course_dir / "References")
    write_course_readme(course_dir, course, enrich)


def fetch_spec_meta(sess: requests.Session, slug: str) -> dict:
    try:
        r = sess.get(
            "https://www.coursera.org/api/onDemandSpecializations.v1",
            params={"q": "slug", "slug": slug, "fields": "name,description,tagline,slug"},
            timeout=30,
        )
        return (r.json().get("elements") or [{}])[0]
    except Exception:
        return {}


def write_spec_readme(spec_dir: Path, spec: dict, meta: dict | None = None) -> None:
    lines = [f"# {spec.get('name') or spec.get('slug')}", ""]
    if meta:
        tagline = (meta.get("tagline") or "").strip()
        desc = (meta.get("description") or "").strip()
        if tagline:
            lines += [tagline, ""]
        if desc:
            lines += [desc, ""]
    lines.append("Courses in syllabus order:")
    lines.append("")
    for i, course in enumerate(spec.get("courses") or [], start=1):
        name = course.get("name") or course.get("slug")
        slug = course.get("slug")
        folder = numbered(i, name)
        lines.append(f"{i}. [{name}]({folder}/README.md) (`{slug}`)")
    lines += [
        "",
        "Each course folder has:",
        "",
        "- `README.md` table of contents",
        "- numbered module folders with videos, readings, and subtitles",
        "",
    ]
    (spec_dir / "README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def beautify_tree(root: Path, sess: requests.Session | None) -> None:
    cache = root / ".cache" / "crawl.json"
    if not cache.is_file():
        raise SystemExit(f"No crawl.json under {root}")
    data = json.loads(cache.read_text(encoding="utf-8"))
    if data.get("type") == "Spec":
        for i, course in enumerate(data.get("courses") or [], start=1):
            old = resolve_course_dir(root, i, course)
            beautify_course(old, course, sess)
            rename_path(old, root / numbered(i, course.get("name") or course.get("slug") or "course"))
        meta = fetch_spec_meta(sess, data["slug"]) if sess else {}
        write_spec_readme(root, data, meta)
        return
    beautify_course(root, data, sess)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Downloaded course or specialization directory")
    parser.add_argument("--cookies", type=Path, default=Path.home() / "coursera/cookies.txt")
    args = parser.parse_args()
    root = args.path.resolve()
    sess = load_cookies(args.cookies)
    beautify_tree(root, sess)
    print(f"Beautified {root}")


if __name__ == "__main__":
    sys.exit(main())
