# Changelog

## [0.1.5] - 2026-09-12

### Fixed
- Paste preview for specializations and certificates. Windows was treating extra engine stdout as success with no `preview`, so the line flashed "Checking URL" then went blank. Parse JSON from the sidecar more strictly and always show `{n} courses in this specialization`.

## [0.1.4] - 2026-09-11

### Added
- Paste preview: `{n} courses in this certificate` or `{n} modules in this course`.
- Certificate and specialization URLs expand to each `/learn/` course, then download **one course at a time**.
- Cancel kills the engine process tree (Windows `taskkill /T`) and deletes only the course folder that was in progress. Finished sibling courses in a certificate stay on disk.
- Windows-safe asset names before `open()` (signed `?key=` / `?expiry=` URLs). Extra files that still fail warn; missing lectures still fail the course.
- Session logs: each download writes `courdl-logs/courdl-YYYYMMDD-HHMMSS.txt` in the library folder. The on-screen log still clears when you start a new run; the files stay.
- macOS DMG workflow (Apple Silicon, unsigned). A 0.1.3 Mac build is attached to the `v0.1.3` GitHub Release, not to 0.1.4.

### Changed
- Skip-existing requires lecture files (`mp4`, `srt`, or `html`) outside `.cache`.
- tqdm progress bars are disabled in the sidecar so the GUI log is not flooded with ANSI redraws.

### Removed from the 0.2.x line
- GitHub Releases **v0.2.0** and **v0.2.1** were withdrawn. They are not a supported upgrade path.
- Concurrent certificate jobs (5 then 3) are gone. That was the overlapping crawl/download log and the cancel that could not keep up.

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
