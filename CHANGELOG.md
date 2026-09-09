# Changelog

## [0.2.0] - 2026-09-09

### Added
- Certificate and specialization URLs expand to every `/learn/` course via Coursera catalog APIs, then each course downloads as today.
- URL preview: `{n} courses in this certificate` or `{n} modules in this course` after paste.
- `courdl-engine resolve --pretty --input` prints the course list and preview line.
- Parallel file workers (default 2 in the app) inside `dl_coursera`.
- Certificate downloads run up to 5 courses at once, drop to 3 after a 429, then climb back. `--jobs`, `--jobs-min`, `--no-adaptive`.
- `scripts/batch-from-links.py` is resumable (`_batch-state.json`), stoppable (`_batch.stop`), and runs up to 10 course jobs at once.
- Empty `.cache` folders no longer count as a finished course. Skip-existing requires mp4, srt, or html outside `.cache`.
- Course crawls that Coursera reports as empty specializations are treated as courses.

## [0.1.3] - 2026-09-05

### Fixed
- Accept Cookie-Editor `#HttpOnly_` Netscape rows and JSON cookie exports. Rewrite them to classic Netscape so `CAUTH` is visible to dl_coursera.

## [0.1.2] - 2026-09-05

### Fixed
- Find the bundled engine next to `CourDL.exe` on Windows (NSIS does not put sidecars in `resources/`).

## [0.1.0] - 2026-09-04

### Added
- Tauri v2 desktop shell (wizard, status, download form, library, log)
- `courdl-engine` sidecar: `version`, `check-cookies`, `resolve`, `download`, `beautify`
- Windows NSIS release workflow
