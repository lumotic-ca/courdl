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
