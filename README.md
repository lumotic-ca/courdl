# CourDL

Desktop app for **enrolled** Coursera lecture and reading downloads. It wraps
[dl_coursera](https://github.com/FLZ101/dl_coursera) 1.0.1 and our folder beautifier.

Not a Coursera clone. It does not unlock quizzes, labs, or graded projects.

## What you get

- Videos (`.mp4`), subtitles (`.srt`), and reading HTML
- Numbered folders and a `README.md` table of contents
- Default library: `Documents/CourDL` (you can change it)

## Cookies

1. Log in to Coursera in a browser.
2. Export cookies for `.coursera.org` (Cookie-Editor Netscape or JSON, or "Get cookies.txt LOCALLY"). HttpOnly rows are fine.
3. In CourDL, import that file. `CAUTH` is required.

Cookies are login-equivalent. They usually last about two weeks. Never commit them.

## Windows installer

Private GitHub Releases (`v*` tags or workflow_dispatch). The `.exe` is **unsigned**; SmartScreen may warn.

Requires [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) on Windows 10.

## Develop

See [docs/packaging.md](docs/packaging.md) and [AGENTS.md](AGENTS.md).

## Credits

See [NOTICE.md](NOTICE.md).
