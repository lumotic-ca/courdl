from pathlib import Path

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
