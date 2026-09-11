# Decisions

Short dated notes.

## 2026-09-04 — Sidecar, not UI crawl

The GUI never talks to Coursera. All crawl/download goes through `courdl-engine` wrapping pinned `dl_coursera` 1.0.1.

## 2026-09-09 — Catalog expand in CourDL

Do not pass professional-certificate slugs into one `dl_coursera` Spec crawl. Expand `courseIds` ourselves.

## 2026-09-09 — Adaptive jobs 5 then 3

File workers stay at 2 in the app so total connections stay modest.

## 2026-09-10 — Sanitize Windows paths in CourDL, patch release 0.2.1

Do not edit site-packages. Sanitize at `Asset` construction and download-task load. Keep v0.2.0 published; ship 0.2.1. Optional asset failures warn; missing lectures fail the course.

## 2026-09-11 — Rebuild 0.2.1 in place for DownloadError

Do not delete exception classes when inserting helpers. The first 0.2.1 sidecar failed on import and the GUI showed the traceback under Status and Download. Rebuild and replace `v0.2.1`; do not ship 0.2.2. Test `from courdl_engine.download import DownloadError` in CI.
