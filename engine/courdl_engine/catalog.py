from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

from courdl_engine.slug import SlugError, slug_from_input

UA = "Mozilla/5.0 (compatible; CourDL/1.0)"
SPEC_URL = "https://www.coursera.org/api/onDemandSpecializations.v1"
COURSE_URL = "https://www.coursera.org/api/onDemandCourses.v1"
MATERIALS_URL = "https://www.coursera.org/api/onDemandCourseMaterials.v2/"
PARTNERS_URL = "https://www.coursera.org/api/partners.v1"

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
        {
            "q": "slug",
            "slug": slug,
            "fields": "name,slug,courseIds,tagline,partnerIds,productVariant",
        },
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


def _partners_by_ids(sess: requests.Session, ids: list[str]) -> list[str]:
    if not ids:
        return []
    data = _get_json(sess, PARTNERS_URL, {"ids": ",".join(ids)})
    by_id = {
        str(el.get("id")): (el.get("name") or "").strip()
        for el in data.get("elements") or []
    }
    return [by_id[i] for i in ids if by_id.get(i)]


def product_kind_from_spec(kind: str, variant: str) -> str:
    if kind in ("specialization", "professional-certificate"):
        return kind
    if "ProfessionalCertificate" in (variant or ""):
        return "professional-certificate"
    return "specialization"


def display_product_name(
    name: str,
    *,
    kind: str = "",
    product_variant: str = "",
    partners: list[str] | None = None,
) -> str:
    """Folder/title as shown on Coursera: company + product + Certificate/Specialization."""
    title = (name or "").strip() or "certificate"
    for partner in partners or []:
        partner = (partner or "").strip()
        if partner and partner.casefold() not in title.casefold():
            title = f"{partner} {title}"
            break
    kind = kind or ""
    variant = product_variant or ""
    is_cert = kind == "professional-certificate" or "ProfessionalCertificate" in variant
    is_spec = kind == "specialization" or variant == "NormalS12n"
    lower = title.casefold()
    if is_cert and "certificate" not in lower:
        title = f"{title} Certificate"
    elif is_spec and "specialization" not in lower and "certificate" not in lower:
        title = f"{title} Specialization"
    return title


def count_modules(sess: requests.Session, slug: str) -> int | None:
    data = _get_json(
        sess,
        MATERIALS_URL,
        {
            "q": "slug",
            "slug": slug,
            "includes": "modules",
            "fields": "moduleIds,onDemandCourseMaterialModules.v1(name,slug)",
            "showLockedItems": "true",
        },
    )
    linked = data.get("linked") or {}
    mods = linked.get("onDemandCourseMaterialModules.v1") or []
    if mods:
        return len(mods)
    els = data.get("elements") or []
    ids = (els[0].get("moduleIds") if els else None) or []
    return len(ids) if ids else None


def _with_preview(product: dict[str, Any], sess: requests.Session | None = None) -> dict[str, Any]:
    kind = product.get("kind") or "course"
    courses = product.get("courses") or []
    if kind in ("professional-certificate", "specialization") and len(courses) >= 1:
        n = len(courses)
        label = "certificate" if kind == "professional-certificate" else "specialization"
        word = "course" if n == 1 else "courses"
        product["courseCount"] = n
        product["preview"] = f"{n} {word} in this {label}"
        return product
    slug = product.get("slug") or (courses[0].get("slug") if courses else "")
    n = count_modules(sess or _session(), slug) if slug else None
    if n:
        word = "module" if n == 1 else "modules"
        product["moduleCount"] = n
        product["preview"] = f"{n} {word} in this course"
    return product


def resolve_product(value: str) -> dict[str, Any]:
    """Turn a Coursera URL or slug into a course or an expanded certificate/specialization."""
    kind, slug = classify_input(value)
    sess = _session()

    if kind == "course":
        return _with_preview(
            {
                "kind": "course",
                "slug": slug,
                "name": slug,
                "courses": [
                    {
                        "slug": slug,
                        "name": slug,
                        "url": f"https://www.coursera.org/learn/{slug}",
                    }
                ],
            },
            sess,
        )

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
        product_kind = product_kind_from_spec(kind, spec.get("productVariant") or "")
        api_name = spec.get("name") or slug
        partners = _partners_by_ids(sess, [str(x) for x in spec.get("partnerIds") or []])
        display = display_product_name(
            api_name,
            kind=product_kind,
            product_variant=spec.get("productVariant") or "",
            partners=partners,
        )
        return _with_preview(
            {
                "kind": product_kind,
                "slug": spec.get("slug") or slug,
                "name": display,
                "apiName": api_name,
                "partners": partners,
                "productVariant": spec.get("productVariant") or "",
                "tagline": spec.get("tagline") or "",
                "courses": courses,
                "unresolvedCourseIds": missing,
            },
            sess,
        )

    if kind in ("specialization", "professional-certificate"):
        raise CatalogError(
            f"No published course list for '{slug}'. The product may still be pre-enroll, or Coursera has not attached courseIds."
        )

    return _with_preview(
        {
            "kind": "course",
            "slug": slug,
            "name": slug,
            "courses": [
                {
                    "slug": slug,
                    "name": slug,
                    "url": f"https://www.coursera.org/learn/{slug}",
                }
            ],
        },
        sess,
    )
