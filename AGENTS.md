# AGENTS.md — CourDL

Desktop GUI for downloading enrolled Coursera lectures and readings.

- **Stack:** Tauri v2 (Rust) + static HTML/JS + Python sidecar (`courdl-engine`)
- **Engine:** `dl_coursera==1.0.1` plus `courdl_engine` beautify
- **Do not** put Coursera cookies in git. Do not spawn `dl_coursera` from the UI; always go through `courdl-engine`.
- **Human copy:** no em dashes in UI or user-facing docs.
- **Do not create a git tag or GitHub Release unless the owner asked.**
- **Do not run more than one course download at a time in the app.** Certificates expand, then each course runs sequentially.

Read [docs/engine.md](docs/engine.md) before changing cookies, the sidecar, or download jobs.

## Layout

```
engine/                 Python package + PyInstaller spec
src/                    frontend
src-tauri/              Tauri commands
docs/                   engine, packaging, host CLI notes
scripts/                sidecar pack/link
.github/workflows/      Windows NSIS on v* tags
```

## Version lockstep

Keep these identical: `package.json`, `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, `engine/pyproject.toml`, `engine/courdl_engine/__init__.py` (`ENGINE_VERSION`).

## Commands

| Command | Purpose |
| --- | --- |
| `engine/.venv/bin/pytest` | Engine unit tests |
| `bash scripts/link-dev-sidecar.sh` | Linux/macOS stub sidecar for `tauri dev` |
| `npm run dev` | Tauri debug |
| `npm run build` | NSIS installer (Windows) |

Keep download logic in `engine/`. Keep UI thin.

Certificate URLs expand in `courdl_engine/catalog.py`. Do not pass a cert slug into one `dl_coursera` Spec crawl.

Windows-unsafe asset names are sanitized in `courdl_engine/paths.py` before `open()`. Do not edit `dl_coursera` site-packages.

Cancel must kill the sidecar process tree and delete only the in-progress course folder under the library path. Each GUI download must append a `courdl-logs/courdl-*.txt` session file in the library. Do not put cookie values in that file.

Changelog: user-facing engine or GUI behavior goes in [CHANGELOG.md](CHANGELOG.md).
