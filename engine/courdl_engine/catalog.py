from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

from courdl_engine.slug import SlugError, slug_from_input

UA = "Mozilla/5.0 (compatible; CourDL/1.0)"
SPEC_URL = "https://www.coursera.org/api/onDemandSpecializations.v1"
COURSE_URL = "https://www.coursera.org/api/onDemandCourses.v1"

_PATH = re.compile(
    r"/(learn|specializations|professional-certificates)/([^/?#]+)",
    re.I,
)


class CatalogError(ValueError):
    pass


def _session() -> requests.Session:
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    sess.headers["Accept"] = "application/json"
    return sess


def classify_input(value: str) -> tuple[str, str]:
    """Return (kind, slug). kind is course, specialization, or professional-certificate."""
    raw = (value or "").strip()
    slug = slug_from_input(raw)
    parsed = urlparse(raw) if "://" in raw else None
    if parsed:
        m = _PATH.search(parsed.path or "")
        if m:
            kind = m.group(1).lower()
            if kind == "learn":
                return "course", slug
            if kind == "specializations":
                return "specialization", slug
            return "professional-certificate", slug
    return "unknown", slug


def _get_json(sess: requests.Session, url: str, params: dict[str, str]) -> dict[str, Any]:
    r = sess.get(url, params=params, timeout=30)
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json() if r.content else {}


def _spec_element(sess: requests.Session, slug: str) -> dict[str, Any] | None:
    data = _get_json(
        sess,
        SPEC_URL,
        {"q": "slug", "slug": slug, "fields": "name,slug,courseIds,tagline"},
    )
    els = data.get("elements") or []
    if not els:
        return None
    el = els[0]
    if not el.get("courseIds"):
        return None
    return el


def _courses_by_ids(sess: requests.Session, ids: list[str]) -> dict[str, dict[str, str]]:
    if not ids:
        return {}
    data = _get_json(
        sess,
        COURSE_URL,
        {"ids": ",".join(ids), "fields": "slug,name,id"},
    )
    out: dict[str, dict[str, str]] = {}
    for el in data.get("elements") or []:
        cid = el.get("id")
        slug = el.get("slug")
        if cid and slug:
            out[cid] = {
                "id": cid,
                "slug": slug,
                "name": el.get("name") or slug,
            }
    return out


def resolve_product(value: str) -> dict[str, Any]:
    """Turn a Coursera URL or slug into a course or an expanded certificate/specialization."""
    kind, slug = classify_input(value)
    sess = _session()

    if kind == "course":
        return {
            "kind": "course",
            "slug": slug,
            "name": slug,
            "courses": [{"slug": slug, "name": slug, "url": f"https://www.coursera.org/learn/{slug}"}],
        }

    spec = _spec_element(sess, slug)
    if spec:
        ids = [str(x) for x in spec.get("courseIds") or []]
        by_id = _courses_by_ids(sess, ids)
        courses = []
        missing = []
        for cid in ids:
            row = by_id.get(cid)
            if not row:
                missing.append(cid)
                continue
            courses.append(
                {
                    "id": row["id"],
                    "slug": row["slug"],
                    "name": row["name"],
                    "url": f"https://www.coursera.org/learn/{row['slug']}",
                }
            )
        if not courses:
            raise CatalogError(
                f"Certificate or specialization '{slug}' listed courses, but none resolved to /learn/ slugs yet."
            )
        product_kind = kind if kind in ("specialization", "professional-certificate") else "specialization"
        return {
            "kind": product_kind,
            "slug": spec.get("slug") or slug,
            "name": spec.get("name") or slug,
            "tagline": spec.get("tagline") or "",
            "courses": courses,
            "unresolvedCourseIds": missing,
        }

    if kind in ("specialization", "professional-certificate"):
        raise CatalogError(
            f"No published course list for '{slug}'. The product may still be pre-enroll, or Coursera has not attached courseIds."
        )

    return {
        "kind": "course",
        "slug": slug,
        "name": slug,
        "courses": [{"slug": slug, "name": slug, "url": f"https://www.coursera.org/learn/{slug}"}],
    }
