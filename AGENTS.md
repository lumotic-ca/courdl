# AGENTS.md — CourDL

Desktop GUI for downloading enrolled Coursera lectures and readings.

- **Stack:** Tauri v2 (Rust) + static HTML/JS + Python sidecar (`courdl-engine`)
- **Engine:** `dl_coursera==1.0.1` plus `courdl_engine` beautify
- **Do not** put Coursera cookies in git. Do not spawn `dl_coursera` from the UI; always go through `courdl-engine`.
- **Human copy:** no em dashes in UI or user-facing docs.

Read [docs/architecture.md](docs/architecture.md) before changing how cookies, the sidecar, or download jobs work.

## Layout

```
engine/                 Python package + PyInstaller spec (source of truth for crawl + beautify)
src/                    frontend (wizard, status, form, library, log)
src-tauri/              Tauri commands (auth, download, library, prereqs, paths)
docs/                   architecture, engine, packaging, host CLI notes
scripts/                sidecar pack/link; batch-from-links.py for cert course lists
.github/workflows/      Windows NSIS release on v* tags
```

## Commands

| Command | Purpose |
| --- | --- |
| `engine/.venv/bin/pytest` | Slug and cookie unit tests |
| `bash scripts/link-dev-sidecar.sh` | Linux/macOS stub sidecar for `tauri dev` |
| `npm run dev` | Tauri debug |
| `npm run build` | NSIS installer (Windows) |
| `python scripts/batch-from-links.py --help` | Download a cert/course text manifest |

Keep download logic in `engine/`. Keep UI thin. When adding engine flags, mirror them in `DownloadOptions`, the form, and `download.rs`.

Certificate and specialization URLs are expanded in `courdl_engine/catalog.py` before download. Do not pass a cert slug straight into one `dl_coursera` Spec crawl.

Changelog: user-facing engine or GUI behavior goes in [CHANGELOG.md](CHANGELOG.md).
