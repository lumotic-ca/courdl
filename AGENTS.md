# AGENTS.md — CourDL

Desktop GUI for downloading enrolled Coursera lectures and readings.

- **Stack:** Tauri v2 (Rust) + static HTML/JS + Python sidecar (`courdl-engine`)
- **Engine:** `dl_coursera==1.0.1` plus `courdl_engine` beautify
- **Do not** put Coursera cookies in git. Do not spawn `dl_coursera` from the UI; always go through `courdl-engine`.
- **Human copy:** no em dashes in UI or user-facing docs.
- **Do not create a git tag or GitHub Release unless the owner asked.**

Read [docs/architecture.md](docs/architecture.md) before changing cookies, the sidecar, or download jobs.

| Concern | Doc |
| ------- | --- |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Engine CLI | [docs/engine.md](docs/engine.md) |
| Packaging | [docs/packaging.md](docs/packaging.md) |
| Release / tags | [docs/release.md](docs/release.md) |
| Troubleshooting | [docs/troubleshooting.md](docs/troubleshooting.md) |
| Decisions | [docs/decisions.md](docs/decisions.md) |
| Jupiter host batch | [jupiter coursera-offline](https://github.com/lumotic-ca/jupiter/blob/main/documentation/coursera-offline.md) |
| Lab lessons | [zots-labs courdl.md](https://github.com/lumotic-ca/zots-labs/blob/main/documentation/courdl.md) |

## Layout

```
engine/                 Python package + PyInstaller spec (source of truth for crawl + beautify)
src/                    frontend
src-tauri/              Tauri commands
docs/                   architecture, engine, packaging, release, troubleshooting
scripts/                sidecar pack/link; batch-from-links.py
.github/workflows/      CI tests + Windows NSIS on v* tags
```

## Version lockstep

Keep these identical: `package.json`, `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, `engine/pyproject.toml`, `engine/courdl_engine/__init__.py` (`ENGINE_VERSION`). Do not pin that version in jupiter or zots-labs docs.

## Commands

| Command | Purpose |
| --- | --- |
| `engine/.venv/bin/pytest` | Engine unit tests |
| `bash scripts/link-dev-sidecar.sh` | Linux/macOS stub sidecar for `tauri dev` |
| `npm run dev` | Tauri debug |
| `npm run build` | NSIS installer (Windows) |
| `python scripts/batch-from-links.py --help` | Cert/course text manifest |

Keep download logic in `engine/`. Keep UI thin. When adding engine flags, mirror them in `DownloadOptions`, the form, and `download.rs`.

Certificate URLs expand in `courdl_engine/catalog.py`. Do not pass a cert slug straight into one `dl_coursera` Spec crawl.

Windows-unsafe asset names must be sanitized in `courdl_engine/paths.py` before `open()`. Do not edit `dl_coursera` site-packages.

## Definition of Done

- `engine/.venv/bin/pytest` passes
- `cargo check` in `src-tauri` if Rust changed
- CHANGELOG under `[Unreleased]` or the new version heading
- Path sanitizer tests if download filenames changed
- No cookies, no em dashes in UI copy

Changelog: user-facing engine or GUI behavior goes in [CHANGELOG.md](CHANGELOG.md).
