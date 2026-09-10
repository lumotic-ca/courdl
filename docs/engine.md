# CourDL engine notes

The sidecar in this repo is the source of truth for `dl_coursera` + beautify. Jupiter still has a host CLI under `~/coursera` for Linux history; see [host-cli.md](host-cli.md).

## Tooling

| Tool | Verdict |
| ---- | ------- |
| ThePharmer/coursera-dl | Do not use |
| FLZ101/dl_coursera 1.0.1 | Use this |

`dl_coursera` writes `01@truncated-slug` folders. Beautify turns them into `01 - Human Title`.

## Paid account vs files on disk

Enrollment lets you use the Coursera **web app**. `dl_coursera` only fetches files: lecture MP4, subtitles, supplement HTML. Quizzes and graded work are not files.

Cookies prove you are logged in. They do not dump quiz banks.

## CLI

```bash
courdl-engine check-cookies --file cookies.txt
courdl-engine resolve --pretty --input 'https://www.coursera.org/professional-certificates/google-it-automation'
courdl-engine download --cookies cookies.txt --outdir ~/Documents/CourDL \
  --jobs 5 --workers 2 --input 'https://www.coursera.org/professional-certificates/google-it-automation'
courdl-engine beautify --path ~/Documents/CourDL/<slug> --cookies cookies.txt
```

Keep `.cache/crawl.json` if you want to re-beautify without crawling again.

## Cookies

CourDL rewrites the cookie file to classic Netscape before `MozillaCookieJar` / `dl_coursera` load it:

- Cookie-Editor `#HttpOnly_` Netscape rows (CAUTH is HttpOnly)
- JSON cookie arrays
- UTF-16 exports

`CAUTH` on `.coursera.org` is required. Cookies last on the order of two weeks.

## Beautify behavior

- Flatten `untitled-lesson`
- Match course folders when slugs are longer than 40 characters
- List syllabus items that were not downloaded (quizzes, assignments) in each course README

## Certificates and batch lists

`resolve` / `download` expand a published `/professional-certificates/…` or `/specializations/…` URL to each `/learn/` course (syllabus order). The desktop URL field shows `{n} courses in this certificate` or `{n} modules in this course` from the same resolve call.

Use `scripts/batch-from-links.py` when the list is handmade (courses mixed from several products, extras Coursera does not put in `courseIds`).

```
Microsoft Full Stack Dev Certificate
https://www.coursera.org/learn/full-stack-integration
https://www.coursera.org/learn/security-and-authentication
```

```bash
engine/.venv/bin/python ../scripts/batch-from-links.py \
  --links ~/Documents/Course\ Links.txt \
  --outdir ~/Documents/CourDL\ Courses \
  --cookies ~/Documents/cookies.txt \
  --jobs 4 --workers 3
```

A certificate URL in the app starts about 5 course jobs and 2 file workers each. On HTTP 429 it drops to 3 course jobs, then climbs after a few successes. Catalog crawls are serialized so parallel courses do not race.

`batch-from-links.py --jobs` is concurrent courses (1-10, default 4). `--workers` is file threads per course (default 3). Touch `_batch.stop` in the outdir to halt after the current certificate. Resume is `_batch-state.json`. A course is skipped only when it already has lecture files, not when `_batch-state.json` lists it.

The script writes `cert-name/<course-slug>/`. Duplicate slugs across certs are copied from the first completed download instead of crawled again. `--skip-existing` is on by default.

## Windows asset names

`dl_coursera` 1.0.1 can write `image.jpg?expiry=...&hmac=....jpg`. CourDL sanitizes those in `courdl_engine/paths.py` before download. See [troubleshooting.md](troubleshooting.md).

## Progress protocol

Stdout lines that are JSON objects with `"courdl": true` are GUI progress events. Other stdout/stderr is log text.
