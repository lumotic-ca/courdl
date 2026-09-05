# Changelog

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
