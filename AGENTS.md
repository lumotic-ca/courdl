# AGENTS.md — CourDL

Desktop GUI for downloading enrolled Coursera lectures and readings.

- **Stack:** Tauri v2 (Rust) + static HTML/JS + Python sidecar (`courdl-engine`)
- **Engine:** `dl_coursera==1.0.1` plus `courdl_engine/beautify.py`
- **Do not** put Coursera cookies in git. Do not spawn `dl_coursera` from the UI; always go through `courdl-engine`.

## Layout

```
engine/                 # Python package + PyInstaller spec
src/                    # frontend (wizard, form, library, log)
src-tauri/              # Tauri commands (auth, download, library, prereqs)
docs/                   # engine and packaging notes
.github/workflows/      # Windows NSIS release
```

## Commands

| Command | Purpose |
| --- | --- |
| `engine/.venv/bin/pytest` | Slug and cookie unit tests |
| `bash scripts/link-dev-sidecar.sh` | Linux/macOS stub sidecar for `tauri dev` |
| `npm run dev` | Tauri debug |
| `npm run build` | NSIS installer (Windows) |

Keep download logic in `engine/`. Keep UI thin. When adding engine flags, mirror them in `DownloadOptions`, the form, and `download.rs`.
