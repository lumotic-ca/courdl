# CourDL engine notes

Adapted from the Jupiter host toolchain. The sidecar in this repo is now the source of truth for
`dl_coursera` + beautify. Jupiter still has a host CLI under `~/coursera` for Linux; see
[host-cli.md](host-cli.md).

## Tooling

| Tool | Verdict |
| ---- | ------- |
| ThePharmer/coursera-dl | Do not use |
| FLZ101/dl_coursera 1.0.1 | Use this |

`dl_coursera` writes `01@truncated-slug` folders. Beautify turns them into `01 - Human Title`.

## Paid account vs files on disk

Enrollment lets you use the Coursera **web app**. `dl_coursera` only fetches files: lecture MP4,
subtitles, supplement HTML. Quizzes and graded work are not files.

Cookies prove you are logged in. They do not dump quiz banks.

## CLI

```bash
courdl-engine check-cookies --file cookies.txt
courdl-engine resolve --pretty --input 'https://www.coursera.org/professional-certificates/google-it-automation'
courdl-engine download --cookies cookies.txt --outdir ~/Documents/CourDL --input '<url-or-slug>'
courdl-engine beautify --path ~/Documents/CourDL/<slug> --cookies cookies.txt
```

Certificates expand to each `/learn/` course and download **one course at a time**. Keep `.cache/crawl.json` if you want to re-beautify without crawling again.

The desktop app writes one session log per Download click: `<library>/courdl-logs/courdl-YYYYMMDD-HHMMSS.txt`. Cookie values are not written there.

## Beautify behavior

- Flatten `untitled-lesson`
- Match course folders when slugs are longer than 40 characters
- List syllabus items that were not downloaded (quizzes, assignments) in each course README
