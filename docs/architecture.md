# CourDL architecture

CourDL is a Windows-first desktop shell around a Python sidecar. The GUI never talks to Coursera. It copies cookies, picks a library folder, and runs `courdl-engine`. The engine runs `dl_coursera` 1.0.1, then our beautify pass.

Identifier: `ca.lumotic.courdl`. Current app version lives in `package.json`, `src-tauri/tauri.conf.json`, and `src-tauri/Cargo.toml`. Engine version lives in `engine/courdl_engine/__init__.py`.

## Layers

```
src/                    static HTML/CSS/JS (wizard, status, form, library, log)
src-tauri/              Tauri v2: dialogs, settings, sidecar spawn, library listing
engine/courdl_engine/   CLI: cookies, slug, download, beautify, JSONL progress
FLZ101/dl_coursera      crawler (pinned 1.0.1)
```

UI is modeled on Bake Studio (init overlay, first-run wizard, live log). CourDL uses its own teal palette. It does not bundle Bake or Pake.

## Runtime data (not in git)

| Item | Location |
| --- | --- |
| Imported cookies | App data dir `cookies.txt` (Windows: `%APPDATA%\ca.lumotic.courdl\`) |
| Settings | App data dir `settings.json` (`libraryPath`, `lastUrl`, `skipExisting`, `beautify`, `wizardComplete`) |
| Course files | Library folder (default `Documents/CourDL`) |

Cookies are login-equivalent. Never commit them. CourDL copies the file you pick; it does not send it anywhere except into `dl_coursera` on this machine.

## Frontend (`src/`)

| File | Role |
| --- | --- |
| `index.html` | Layout: setup wizard, status panel, download form, library list, log |
| `js/main.js` | Wire buttons, start/cancel download, listen for sidecar events |
| `js/wizard.js` | First-run overlay and prerequisite list |
| `js/library.js` | Render course folders from `list_library` |
| `js/log.js` | Append log text and progress line |
| `js/api.js` | `invoke` / `listen` wrappers |
| `styles.css` | CourDL chrome |

Download stays disabled until the engine sidecar is found, cookies exist on disk, and (on Windows) WebView2 is present. The wizard can still be dismissed; missing cookies bring it back on the next launch.

## Tauri commands (`src-tauri/src/`)

| Module | Commands / jobs |
| --- | --- |
| `prereqs.rs` | `check_prerequisites`, `can_download`. Engine file probe, cookie file present, WebView2. |
| `paths.rs` | App data, cookies path, library default, sidecar search next to `CourDL.exe` (NSIS does not put sidecars in `resources/`). |
| `auth.rs` | File picker + copy into app data. |
| `settings.rs` | Load/save `settings.json`. |
| `download.rs` | `engine_version`, `resolve_preview`, `check_cookies`, `start_download`, `cancel_download`. Spawns sidecar, forwards JSONL as `download-progress`. Preview is a one-shot `resolve`. |
| `library.rs` | Shallow scan of the library folder for course-like dirs (`README.md`, `.cache/crawl.json`, or numbered child folders). `open_library_folder` opens the parent library, not a single course. |

One download at a time (`JobState`). Cancel kills the sidecar process.

## Engine CLI (`engine/`)

Entry: `python -m courdl_engine` or the PyInstaller binary `courdl-engine`.

| Subcommand | What it does |
| --- | --- |
| `version` | JSON: engine version and `dl_coursera` pin |
| `check-cookies --file` | Parse/normalize cookies, require `.coursera.org` `CAUTH` |
| `resolve --input` | URL or slug to a Coursera slug |
| `download --cookies --outdir --input` | Optional `--skip-existing`, `--no-beautify` |
| `beautify --path [--cookies]` | Rename folders and write README files |

Stdout JSONL for the GUI:

```json
{"courdl": true, "phase": "download", "message": "Starting dl_coursera", "level": "info"}
```

Human logs go to stderr. The GUI treats JSON with `"courdl": true` as progress; everything else is log text.

### Cookies

`courdl_engine/cookies.py` accepts:

- Classic Netscape `cookies.txt`
- Cookie-Editor Netscape with `#HttpOnly_` prefixes (those lines are comments to Python's `MozillaCookieJar`, so CourDL strips the prefix and rewrites the file)
- Cookie-Editor / similar JSON arrays

`dl_coursera` only understands classic Netscape. CourDL rewrites the imported file in place before crawl.

### Download pipeline

1. Normalize and validate cookies (`CAUTH` required).
2. `resolve_product`: `/learn/` stays one course; `/specializations/` and `/professional-certificates/` (and bare slugs that have `courseIds`) expand via Coursera catalog APIs.
3. Each course runs `dl_coursera` into `outdir/<slug>/` or `outdir/<Cert name>/<slug>/`.
4. If `--skip-existing` and the course folder already has lecture files (not only `.cache`), skip crawl.
5. Certificate and specialization products download several courses at once (adaptive 5 then 3 on 429). File workers stay at 2 in the app so total connections stay modest.
6. Beautify each course tree. Certificate folders get a README of course links.

Override with `--jobs`, `--jobs-min`, and `--workers`. Upstream `dl_coursera` defaults to 1 file worker.

Keep `.cache/crawl.json`. Beautify cannot rename without it.

### What lands on disk

Files only: lecture MP4, `.srt` subtitles, reading HTML. Quizzes, labs, notebooks, and graded work stay on Coursera. Enrollment unlocks the web app; it does not zip the course.

## Professional certificates vs course URLs

CourDL expands a live cert or specialization to every `/learn/` URL in `courseIds` order, then downloads each course the same way as a single course link. Pre-enroll products with no `courseIds` fail at resolve with a clear error.

Handmade bundles that are not one Coursera product still use `scripts/batch-from-links.py`.

## Packaging

See [packaging.md](packaging.md). Windows CI builds the sidecar with PyInstaller, names it `courdl-engine-x86_64-pc-windows-msvc.exe`, then `tauri build --bundles nsis`. Tag `v*` publishes the installer. The installer is unsigned; SmartScreen will warn.

## Jupiter and zots-labs

- Host paths, Linux batch, leftover `~/coursera` CLI: [jupiter documentation/coursera-offline.md](https://github.com/lumotic-ca/jupiter/blob/main/documentation/coursera-offline.md)
- Desktop product notes and development history: [zots-labs documentation/courdl.md](https://github.com/lumotic-ca/zots-labs/blob/main/documentation/courdl.md)

Beautify and cookie rules in this repo's engine are the source of truth going forward.
