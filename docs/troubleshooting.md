# CourDL troubleshooting

## Missing: CourDL engine (Windows)

NSIS places `courdl-engine.exe` next to `CourDL.exe`, not under `resources/`. Fixed in 0.1.2. Reinstall from the latest Release if an old build probes the wrong folder.

## `ImportError: cannot import name 'DownloadError'`

The first 0.2.1 sidecar dropped `DownloadError` from `courdl_engine.download`. Status and Download show the traceback; the window stays open. Reinstall 0.2.1 from the GitHub Release (rebuilt installer, same version).

## Cookies rejected / videos skipped / 401

Re-export `.coursera.org` cookies. `CAUTH` is required. Cookie-Editor `#HttpOnly_` and JSON are rewritten to classic Netscape (0.1.3). Cookies last about two weeks.

## Certificate downloads only the first course

Use 0.2.0 or later. Catalog expand is in `catalog.py`. Pre-enroll products with no `courseIds` still fail at resolve. Handmade lists: `scripts/batch-from-links.py`.

## Skip-existing skipped a broken folder

Empty `.cache` is not a finished course. 0.2.0+ requires mp4, srt, or html outside `.cache`.

## `OSError: [Errno 22] Invalid argument` on a `.jpg?expiry=...` path

Coursera sometimes puts a signed URL query string in the **asset name**. Windows forbids `?`. CourDL 0.2.1 sanitizes names before download. Failed extras are retried even when videos already exist. If an old course still misses an image, turn off Skip existing once, or delete that course `.cache/courdl-path-schema` so gather is rebuilt.

Optional images can fail without aborting the certificate. The log shows a warning and `.cache/download.dl_tasks_failed.json` lists them. Missing lecture videos still fail the course.

## Rate limits (429)

Certificate jobs start at 5 and drop to 3. File workers stay at 2 in the app.

## Host Linux batch

[jupiter coursera-offline.md](https://github.com/lumotic-ca/jupiter/blob/main/documentation/coursera-offline.md).
