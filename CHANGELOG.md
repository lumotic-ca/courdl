# Changelog

## [0.2.0] - 2026-09-09

### Added
- Certificate and specialization URLs expand to every `/learn/` course via Coursera catalog APIs, then each course downloads as today.
- `courdl-engine resolve --pretty --input` prints the course list.
- Parallel file workers (default 4) inside `dl_coursera` (upstream hardcodes 1).
- Docs for setup, sidecar layout, cookie normalization, and `scripts/batch-from-links.py`.

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
