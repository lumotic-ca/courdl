from pathlib import Path

from courdl_engine.paths import (
    sanitize_asset_name,
    sanitize_dl_tasks,
    sanitize_task_filename,
    url_basename_safe,
    walk_sanitize_assets,
    win_extended_path,
)


def test_signed_cdn_name():
    raw = (
        "ohQyfbLJQAOZfe3t2NZpSw_b6ce0e5f66514dbdb822c54db619f4e1_jan-demiralp-min.jpg"
        "?expiry=1691798400000&hmac=U9FVjFbby9DfdBleDPKmsstYAM1CIfURIPiqYQyxipY.jpg"
    )
    out = sanitize_asset_name(raw)
    assert "?" not in out
    assert "&" not in out
    assert out.endswith(".jpg")
    assert "jan-demiralp-min.jpg" in out or out.endswith(".jpg")


def test_double_extension_from_upstream():
    name = "photo.jpg?expiry=1&hmac=abc.jpg"
    out = sanitize_asset_name(name)
    assert out.count(".jpg") == 1
    assert "?" not in out


def test_forbidden_chars():
    out = sanitize_asset_name('a<>:"|?*b.png')
    assert all(ch not in out for ch in '<>:"|?*')


def test_reserved_device():
    assert sanitize_asset_name("CON.jpg").lower().startswith("_con")
    assert sanitize_asset_name("nul").lower().startswith("_nul")


def test_trailing_dots_spaces():
    assert not sanitize_asset_name("name. ").endswith(" ")
    assert not sanitize_asset_name("file...").endswith(".")


def test_traversal_rejected(tmp_path: Path):
    outdir = tmp_path / "lib"
    outdir.mkdir()
    nasty = str(tmp_path / "outside.jpg")
    safe = sanitize_task_filename(nasty, outdir)
    assert str(outdir.resolve()) in str(Path(safe).resolve())


def test_collisions_deterministic():
    used: set[str] = set()
    a = sanitize_asset_name("x.jpg", used=used)
    b = sanitize_asset_name("x.jpg", used=used)
    assert a != b
    used2: set[str] = set()
    assert sanitize_asset_name("x.jpg", used=used2) == a


def test_component_cap():
    out = sanitize_asset_name("a" * 400 + ".png")
    assert len(out) <= 180
    assert out.endswith(".png")


def test_url_basename_strips_query():
    url = "https://cdn.example/img/jan-demiralp-min.jpg?expiry=1&hmac=abc"
    assert "?" not in url_basename_safe(url)
    assert url_basename_safe(url).endswith(".jpg")


def test_walk_rewrites_html():
    soc = {
        "items": [
            {
                "id": "1",
                "url": "https://cdn.example/a.jpg?x=1",
                "name": "a.jpg?x=1",
                "html": '<img src="a.jpg?x=1">',
            }
        ]
    }
    mapping = walk_sanitize_assets(soc)
    assert mapping
    new = soc["items"][0]["name"]
    assert "?" not in new
    assert new in soc["items"][0]["html"]
    assert "a.jpg?x=1" not in soc["items"][0]["html"]


def test_sanitize_dl_tasks(tmp_path: Path):
    dest = tmp_path / "course"
    dest.mkdir()
    tasks = [
        {
            "url": "https://cdn.example/x.jpg",
            "filename": str(dest / "a.jpg?expiry=1&hmac=z.jpg"),
        }
    ]
    out = sanitize_dl_tasks(tasks, dest)
    fn = out[0]["filename"]
    assert "?" not in Path(fn).name
    assert Path(fn).parent.resolve() == dest.resolve()


def test_win_extended_drive(monkeypatch):
    monkeypatch.setattr("courdl_engine.paths.os.name", "nt")

    def fake_abs(p):
        return r"C:\Users\Cory\file.jpg"

    monkeypatch.setattr("courdl_engine.paths.os.path.abspath", fake_abs)
    p = win_extended_path("C:\\Users\\Cory\\file.jpg")
    assert p.startswith("\\\\?\\C:")


def test_win_extended_unc(monkeypatch):
    monkeypatch.setattr("courdl_engine.paths.os.name", "nt")
    monkeypatch.setattr(
        "courdl_engine.paths.os.path.abspath",
        lambda p: r"\\server\share\a.jpg",
    )
    p = win_extended_path(r"\\server\share\a.jpg")
    assert p.startswith("\\\\?\\UNC\\")


def test_cached_task_migration(tmp_path: Path):
    dest = tmp_path / "slug"
    dest.mkdir()
    bad = str(dest / "pic.jpg?expiry=9")
    tasks = sanitize_dl_tasks([{"url": "u", "filename": bad}], dest)
    assert "?" not in Path(tasks[0]["filename"]).name
