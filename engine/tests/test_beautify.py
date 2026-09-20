from pathlib import Path

from courdl_engine.beautify import (
    apply_certificate_order,
    courses_in_syllabus_order,
    numbered_course,
    parse_course_links,
    safe_name,
)


def _course_tree(root: Path, slug: str, title: str) -> Path:
    dest = root / slug
    dest.mkdir()
    cache = dest / ".cache"
    cache.mkdir()
    (cache / "crawl.json").write_text(
        '{"type":"Course","slug":"%s","name":"%s","modules":[]}' % (slug, title),
        encoding="utf-8",
    )
    return dest


def test_numbered_course_keeps_full_title():
    title = "Foundations: Data, Data, Everywhere"
    name = numbered_course(1, title)
    assert name.startswith("01 - ")
    assert "Foundations" in name
    assert "Everywhere" in name
    assert ":" not in name


def test_apply_certificate_order_uses_syllabus_not_alpha(tmp_path: Path):
    root = tmp_path / "Google Data Analytics Certificate"
    root.mkdir()
    _course_tree(root, "analyze-data", "Analyze Data to Answer Questions")
    _course_tree(root, "foundations-data", "Foundations: Data, Data, Everywhere")
    _course_tree(root, "ask-questions-make-decisions", "Ask Questions to Make Data-Driven Decisions")
    courses = [
        {"slug": "foundations-data", "name": "Foundations: Data, Data, Everywhere"},
        {"slug": "ask-questions-make-decisions", "name": "Ask Questions to Make Data-Driven Decisions"},
        {"slug": "analyze-data", "name": "Analyze Data to Answer Questions"},
    ]
    apply_certificate_order(root, courses)
    names = sorted(p.name for p in root.iterdir() if p.is_dir())
    assert names[0].startswith("01 - ")
    assert "Foundations" in names[0]
    assert names[1].startswith("02 - ")
    assert "Ask Questions" in names[1]
    assert names[2].startswith("03 - ")
    assert "Analyze Data" in names[2]
    assert (root / names[0] / ".cache" / "crawl.json").is_file()


def test_parse_course_links_keeps_section_order(tmp_path: Path):
    path = tmp_path / "Course Links.txt"
    path.write_text(
        "Google Data Analytics Certificate\n"
        "https://www.coursera.org/learn/foundations-data\n"
        "https://www.coursera.org/learn/ask-questions-make-decisions\n"
        "https://www.coursera.org/learn/analyze-data\n",
        encoding="utf-8",
    )
    sections = parse_course_links(path)
    assert sections["Google Data Analytics Certificate"] == [
        "foundations-data",
        "ask-questions-make-decisions",
        "analyze-data",
    ]


def test_courses_in_syllabus_order_from_links(tmp_path: Path):
    root = tmp_path / "Google Data Analytics Certificate"
    root.mkdir()
    _course_tree(root, "analyze-data", "Analyze Data to Answer Questions")
    _course_tree(root, "foundations-data", "Foundations: Data, Data, Everywhere")
    ordered = courses_in_syllabus_order(
        root,
        ["foundations-data", "ask-questions-make-decisions", "analyze-data"],
    )
    assert [c["slug"] for c in ordered] == ["foundations-data", "analyze-data"]
    assert ordered[0]["name"] == "Foundations: Data, Data, Everywhere"


def test_safe_name_strips_windows_forbidden():
    assert ":" not in safe_name("Foundations: Data")
    assert "?" not in safe_name("What is data?")
