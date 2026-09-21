from pathlib import Path
from unittest.mock import patch

from courdl_engine.beautify import (
    apply_certificate_order,
    courses_in_syllabus_order,
    move_path,
    numbered_course,
    parse_course_links,
    retryable_fs_error,
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


def test_apply_certificate_order_recovers_tmp_folders(tmp_path: Path):
    root = tmp_path / "Global Procurement and Sourcing"
    root.mkdir()
    src = _course_tree(root, "foundations-data", "Foundations: Data, Data, Everywhere")
    src.rename(root / "_courdl_tmp_01_foundations-data")
    apply_certificate_order(
        root,
        [{"slug": "foundations-data", "name": "Foundations: Data, Data, Everywhere"}],
    )
    names = [p.name for p in root.iterdir() if p.is_dir()]
    assert len(names) == 1
    assert names[0].startswith("01 - ")
    assert "Foundations" in names[0]
    assert not any(n.startswith("_courdl_tmp_") for n in names)


def test_tmp_folder_numbers_win_over_alpha(tmp_path: Path):
    root = tmp_path / "Cert"
    root.mkdir()
    a = _course_tree(root, "zzz-last", "Last")
    a.rename(root / "_courdl_tmp_01_zzz-last")
    _course_tree(root, "aaa-second", "Second")
    ordered = courses_in_syllabus_order(root)
    assert [c["slug"] for c in ordered] == ["zzz-last", "aaa-second"]


def test_move_path_retries_access_denied(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    calls = {"n": 0}

    def flaky_move(_a, _b):
        calls["n"] += 1
        if calls["n"] < 3:
            err = PermissionError("Access is denied")
            err.winerror = 5
            raise err
        Path(_b).mkdir()
        Path(_a).rmdir()

    with patch("courdl_engine.beautify.shutil.move", side_effect=flaky_move):
        with patch("courdl_engine.beautify.time.sleep"):
            out = move_path(src, dest)
    assert calls["n"] == 3
    assert out == dest


def test_retryable_winerror_5():
    err = OSError("Access is denied")
    err.winerror = 5
    assert retryable_fs_error(err)
