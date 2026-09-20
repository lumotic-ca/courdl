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


NUMBERED_DIR = re.compile(r"^\d{2} - ")
COURSE_TITLE_MAX = 160
PRODUCT_JSON = "courdl-product.json"


def numbered(index: int, title: str, max_len: int = 80) -> str:
    return f"{index:02d} - {safe_name(title, max_len=max_len)}"


def numbered_course(index: int, title: str, used: set[str] | None = None) -> str:
    """Syllabus-order folder name: 01 - Full Course Title."""
    name = numbered(index, title or "course", max_len=COURSE_TITLE_MAX)
    used_set = used if used is not None else set()
    candidate = name
    n = 2
    while candidate.lower() in {item.lower() for item in used_set}:
        candidate = f"{name} ({n})"
        n += 1
    used_set.add(candidate)
    return candidate


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


def load_crawl(course_dir: Path) -> dict:
    cache = course_dir / ".cache" / "crawl.json"
    if not cache.is_file():
        return {}
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def course_slug_from_dir(course_dir: Path) -> str | None:
    slug = (load_crawl(course_dir).get("slug") or "").strip()
    if slug:
        return slug
    if course_dir.name and not NUMBERED_DIR.match(course_dir.name) and course_dir.name != "resource":
        return course_dir.name
    return None


def course_title_from_dir(course_dir: Path, fallback: str = "") -> str:
    name = (load_crawl(course_dir).get("name") or "").strip()
    return name or fallback or course_dir.name


def find_existing_course_dir(
    root: Path,
    slug: str,
    index: int | None = None,
    name: str | None = None,
) -> Path | None:
    slug = (slug or "").strip()
    title = name or slug or "course"
    candidates: list[Path] = []
    if slug:
        candidates.append(root / slug)
    if index is not None:
        candidates.append(root / numbered_course(index, title))
        candidates.append(root / numbered(index, title))
        candidates.append(root / f"{index:02d}@{slug}")
        candidates.append(root / old_dir_name(index, slug))
    for path in candidates:
        if path.is_dir():
            return path
    if not root.is_dir():
        return None
    prefix = f"{index:02d}@" if index is not None else None
    slug_key = slug[:40]
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith(".") or child.name == "resource":
            continue
        got = course_slug_from_dir(child)
        if slug and got == slug:
            return child
        if prefix and child.name.startswith(prefix):
            suffix = child.name[len(prefix) :]
            if slug.startswith(suffix) or suffix.startswith(slug_key) or slug_key.startswith(suffix):
                return child
    return None


def resolve_course_dir(root: Path, index: int, course: dict) -> Path:
    slug = (course.get("slug") or "").strip()
    name = course.get("name") or slug or "course"
    found = find_existing_course_dir(root, slug, index, name)
    if found:
        return found
    raise FileNotFoundError(f"No course folder for {index:02d}: {slug or name}")


def sibling_course_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out = []
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith(".") or child.name in {"resource", "courdl-logs"}:
            continue
        if (child / ".cache" / "crawl.json").is_file() or NUMBERED_DIR.match(child.name):
            out.append(child)
    return out


def parse_course_links(path: Path) -> dict[str, list[str]]:
    """Certificate title -> course slugs in the order listed."""
    from courdl_engine.slug import SlugError, slug_from_input

    sections: dict[str, list[str]] = {}
    current: str | None = None
    if not path.is_file():
        return sections
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "coursera.org/learn/" in line or line.startswith("http"):
            if not current:
                continue
            try:
                slug = slug_from_input(line)
            except SlugError:
                continue
            sections.setdefault(current, []).append(slug)
            continue
        current = line
        sections.setdefault(current, [])
    return sections


def _folder_slug_guesses(name: str) -> list[str]:
    def slugify(text: str) -> str:
        text = text.lower().replace("&", " and ")
        text = re.sub(r"[^a-z0-9]+", "-", text)
        return text.strip("-")

    guesses = []
    trimmed = name.strip()
    for source in (
        trimmed,
        re.sub(
            r"\b((professional|google|ibm|meta|microsoft)\s+)?(certificate|specialization|cert)\b",
            "",
            trimmed,
            flags=re.I,
        ),
    ):
        guess = slugify(source)
        if guess and guess not in guesses:
            guesses.append(guess)
    return guesses


def try_catalog_courses(root: Path) -> list[dict]:
    from courdl_engine.catalog import resolve_product

    child_slugs = {course_slug_from_dir(p) for p in sibling_course_dirs(root)}
    child_slugs.discard(None)
    if len(child_slugs) < 2:
        return []
    for guess in _folder_slug_guesses(root.name):
        for value in (
            guess,
            f"https://www.coursera.org/professional-certificates/{guess}",
            f"https://www.coursera.org/specializations/{guess}",
        ):
            try:
                product = resolve_product(value)
            except Exception:
                continue
            courses = product.get("courses") or []
            slugs = [c.get("slug") for c in courses if c.get("slug")]
            if set(slugs) & child_slugs:
                return courses
    return []


def courses_in_syllabus_order(root: Path, link_slugs: list[str] | None = None) -> list[dict]:
    """Build an ordered course list from links, Coursera catalog, then leftover folders."""
    by_slug: dict[str, Path] = {}
    for child in sibling_course_dirs(root):
        slug = course_slug_from_dir(child)
        if slug:
            by_slug[slug] = child

    ordered: list[dict] = []
    used: set[str] = set()

    def add(slug: str, name: str = "") -> None:
        if not slug or slug in used or slug not in by_slug:
            return
        path = by_slug[slug]
        ordered.append(
            {
                "slug": slug,
                "name": course_title_from_dir(path, name or slug),
                "url": f"https://www.coursera.org/learn/{slug}",
            }
        )
        used.add(slug)

    for slug in link_slugs or []:
        add(slug)
    if not ordered:
        for course in try_catalog_courses(root):
            add(course.get("slug") or "", course.get("name") or "")
    for slug in by_slug:
        add(slug)
    return ordered


def apply_certificate_order(root: Path, courses: list[dict]) -> list[Path]:
    """Rename sibling course folders to NN - Full Title using syllabus order."""
    if not root.is_dir() or not courses:
        return []
    used: set[str] = set()
    plan: list[tuple[Path, Path]] = []
    for i, course in enumerate(courses, start=1):
        slug = (course.get("slug") or "").strip()
        name = course.get("name") or slug or f"Course {i}"
        src = find_existing_course_dir(root, slug, i, name)
        if src is None:
            continue
        dest = root / numbered_course(i, name, used)
        if src.resolve() != dest.resolve():
            plan.append((src, dest))
    temps: list[tuple[Path, Path]] = []
    for i, (src, dest) in enumerate(plan, start=1):
        tmp = root / f"_courdl_tmp_{i:02d}_{src.name[:48]}"
        n = 1
        while tmp.exists():
            n += 1
            tmp = root / f"_courdl_tmp_{i:02d}_{n}_{src.name[:40]}"
        src.rename(tmp)
        temps.append((tmp, dest))
    result: list[Path] = []
    for tmp, dest in temps:
        if dest.exists():
            result.append(tmp)
            continue
        tmp.rename(dest)
        result.append(dest)
    return result


def save_product(root: Path, product: dict) -> None:
    path = root / PRODUCT_JSON
    path.write_text(json.dumps(product, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_product(root: Path) -> dict:
    path = root / PRODUCT_JSON
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def apply_library_certificate_order(library: Path, links_file: Path | None = None) -> list[dict]:
    """Number every multi-course folder under a library. Returns a report."""
    links = parse_course_links(links_file) if links_file else {}
    by_title = {key.strip().casefold(): slugs for key, slugs in links.items()}
    report = []
    for child in sorted(library.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith(".") or child.name == "courdl-logs":
            continue
        if len(sibling_course_dirs(child)) < 2:
            continue
        if all(NUMBERED_DIR.match(p.name) for p in sibling_course_dirs(child)):
            report.append({"folder": child.name, "status": "already-numbered", "count": 0})
            continue
        link_slugs = by_title.get(child.name.strip().casefold())
        courses = courses_in_syllabus_order(child, link_slugs)
        if len(courses) < 2:
            report.append({"folder": child.name, "status": "skipped", "count": 0})
            continue
        try:
            apply_certificate_order(child, courses)
            product = {
                "name": child.name,
                "slug": child.name,
                "kind": "certificate",
                "courses": courses,
            }
            save_product(child, product)
            write_spec_readme(child, product)
        except OSError as exc:
            report.append({"folder": child.name, "status": "error", "error": str(exc)})
            continue
        report.append(
            {
                "folder": child.name,
                "status": "numbered",
                "count": len(courses),
                "names": [numbered_course(i, c.get("name") or c.get("slug") or "course") for i, c in enumerate(courses, start=1)],
            }
        )
    return report


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
    used: set[str] = set()
    for i, course in enumerate(spec.get("courses") or [], start=1):
        name = course.get("name") or course.get("slug")
        slug = course.get("slug")
        folder = numbered_course(i, name or "course", used)
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
    if cache.is_file():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("type") == "Spec":
            courses = data.get("courses") or []
            for i, course in enumerate(courses, start=1):
                old = resolve_course_dir(root, i, course)
                beautify_course(old, course, sess)
            apply_certificate_order(root, courses)
            meta = fetch_spec_meta(sess, data["slug"]) if sess else {}
            write_spec_readme(root, data, meta)
            save_product(root, data)
            return
        beautify_course(root, data, sess)
        return

    product = load_product(root)
    courses = product.get("courses") or courses_in_syllabus_order(root)
    if len(courses) >= 2:
        for i, course in enumerate(courses, start=1):
            found = find_existing_course_dir(root, course.get("slug") or "", i, course.get("name"))
            if found is None:
                continue
            data = load_crawl(found)
            if data.get("modules"):
                beautify_course(found, data, sess)
        apply_certificate_order(root, courses)
        product = product or {
            "name": root.name,
            "slug": root.name,
            "kind": "certificate",
            "courses": courses,
        }
        product["courses"] = courses
        save_product(root, product)
        write_spec_readme(root, product)
        return

    raise SystemExit(f"No crawl.json under {root}")


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
