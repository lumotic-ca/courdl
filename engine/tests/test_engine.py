from pathlib import Path
from unittest.mock import patch

from courdl_engine.catalog import classify_input, resolve_product
from courdl_engine.cookies import CookieError, check_cookies_file
from courdl_engine.slug import SlugError, slug_from_input


def test_slug_from_learn_url():
    assert (
        slug_from_input("https://www.coursera.org/learn/process-modeling/home/module/1")
        == "process-modeling"
    )


def test_slug_from_cert_url():
    assert (
        slug_from_input(
            "https://www.coursera.org/professional-certificates/microsoft-visio-workflow-design-and-automation#about"
        )
        == "microsoft-visio-workflow-design-and-automation"
    )


def test_slug_plain():
    assert slug_from_input("collaboration-and-sharing") == "collaboration-and-sharing"


def test_slug_empty():
    try:
        slug_from_input("  ")
        assert False
    except SlugError:
        pass


def test_cookies_require_cauth(tmp_path: Path):
    p = tmp_path / "cookies.txt"
    p.write_text(
        "# Netscape\n.coursera.org\tTRUE\t/\tTRUE\t1999999999\tCAUTH\treal-token\n",
        encoding="utf-8",
    )
    info = check_cookies_file(p)
    assert info["hasCauth"] is True


def test_cookies_httponly_prefix(tmp_path: Path):
    p = tmp_path / "cookies.txt"
    p.write_text(
        "# Netscape HTTP Cookie File\n"
        "#HttpOnly_.coursera.org\tTRUE\t/\tTRUE\t1999999999\tCAUTH\treal-token\n",
        encoding="utf-8",
    )
    info = check_cookies_file(p)
    assert info["hasCauth"] is True
    rewritten = p.read_text(encoding="utf-8")
    assert "CAUTH" in rewritten
    assert not any(line.lower().startswith("#httponly") for line in rewritten.splitlines())


def test_cookies_json_export(tmp_path: Path):
    p = tmp_path / "cookies.txt"
    p.write_text(
        '[{"domain":".coursera.org","name":"CAUTH","value":"real-token",'
        '"path":"/","secure":true,"expirationDate":1999999999}]',
        encoding="utf-8",
    )
    info = check_cookies_file(p)
    assert info["hasCauth"] is True
    assert "\tCAUTH\t" in p.read_text(encoding="utf-8")


def test_classify_cert_and_course_urls():
    kind, slug = classify_input(
        "https://www.coursera.org/professional-certificates/google-it-automation"
    )
    assert kind == "professional-certificate"
    assert slug == "google-it-automation"
    kind, slug = classify_input(
        "https://www.coursera.org/learn/python-crash-course?specialization=google-it-automation"
    )
    assert kind == "course"
    assert slug == "python-crash-course"
    kind, slug = classify_input("google-it-automation")
    assert kind == "unknown"
    assert slug == "google-it-automation"


def test_resolve_product_expands_course_ids():
    spec = {
        "elements": [
            {
                "name": "Google IT Automation with Python",
                "slug": "google-it-automation",
                "courseIds": ["id-a", "id-b"],
            }
        ]
    }
    courses = {
        "elements": [
            {"id": "id-b", "slug": "python-operating-system", "name": "Using Python"},
            {"id": "id-a", "slug": "python-crash-course", "name": "Crash Course on Python"},
        ]
    }

    def fake_get(_sess, url, params):
        if "onDemandSpecializations" in url:
            return spec
        return courses

    with patch("courdl_engine.catalog._get_json", side_effect=fake_get):
        product = resolve_product(
            "https://www.coursera.org/professional-certificates/google-it-automation"
        )
    assert product["kind"] == "professional-certificate"
    assert [c["slug"] for c in product["courses"]] == [
        "python-crash-course",
        "python-operating-system",
    ]
    assert product["courses"][0]["url"] == "https://www.coursera.org/learn/python-crash-course"
    assert product["courseCount"] == 2
    assert product["preview"] == "2 courses in this certificate"


def test_course_preview_counts_modules():
    def fake_get(_sess, url, params):
        if "CourseMaterials" in url:
            return {
                "linked": {
                    "onDemandCourseMaterialModules.v1": [
                        {"name": "a"},
                        {"name": "b"},
                        {"name": "c"},
                    ]
                }
            }
        return {}

    with patch("courdl_engine.catalog._get_json", side_effect=fake_get):
        product = resolve_product(
            "https://www.coursera.org/learn/python-crash-course?specialization=google-it-automation"
        )
    assert product["kind"] == "course"
    assert product["moduleCount"] == 3
    assert product["preview"] == "3 modules in this course"


def test_cookies_reject_placeholder(tmp_path: Path):
    p = tmp_path / "cookies.txt"
    p.write_text(
        ".coursera.org\tTRUE\t/\tTRUE\t1999999999\tCAUTH\treplace-with-real-value\n",
        encoding="utf-8",
    )
    try:
        check_cookies_file(p)
        assert False
    except CookieError:
        pass


def test_looks_rate_limited():
    from courdl_engine.adaptive import looks_rate_limited

    assert looks_rate_limited(RuntimeError("HTTP 429 Too Many Requests"))
    assert looks_rate_limited(RuntimeError("rate limit exceeded"))
    assert not looks_rate_limited(RuntimeError("cookies expired"))


def test_adaptive_gate_drops_then_climbs():
    from courdl_engine.adaptive import AdaptiveGate

    gate = AdaptiveGate(high=5, low=3, recover_after=2)
    assert gate.enter() == 5
    assert gate.leave(rate_limited=True) == 3
    assert gate.enter() == 3
    assert gate.leave(rate_limited=False) == 3
    assert gate.enter() == 3
    assert gate.leave(rate_limited=False) == 4


def test_course_ready_ignores_cache_only(tmp_path: Path):
    from courdl_engine.download import _course_ready

    dest = tmp_path / "course"
    cache = dest / ".cache"
    cache.mkdir(parents=True)
    (cache / "crawl.json").write_text("{}", encoding="utf-8")
    assert not _course_ready(dest)
    (dest / "lecture.mp4").write_bytes(b"x")
    assert _course_ready(dest)


def test_spec_probe_empty_elements_looks_like_course():
    from courdl_engine.download import _SpecProbeResponse

    class Inner:
        def json(self):
            return {"elements": []}

    data = _SpecProbeResponse(Inner()).json()
    assert "elements" not in data
