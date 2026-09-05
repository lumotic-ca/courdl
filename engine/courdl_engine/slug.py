from __future__ import annotations

import re

_SLUG = re.compile(
    r"coursera\.org/(?:learn|specializations|professional-certificates)/([^/?#]+)",
    re.I,
)


class SlugError(ValueError):
    pass


def slug_from_input(value: str) -> str:
    value = (value or "").strip().rstrip("/")
    if not value:
        raise SlugError("Enter a Coursera URL or course slug.")
    m = _SLUG.search(value)
    if m:
        slug = m.group(1).strip()
    else:
        slug = value.split("/")[-1].strip()
    slug = slug.split("?")[0].split("#")[0]
    if not slug or "." in slug and "coursera.org" in value.lower() and not m:
        raise SlugError(f"Could not parse a Coursera slug from: {value}")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", slug):
        raise SlugError(f"Invalid slug: {slug}")
    return slug
