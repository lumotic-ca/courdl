# CourDL

Desktop app for **enrolled** Coursera lecture and reading downloads. It wraps
[dl_coursera](https://github.com/FLZ101/dl_coursera) 1.0.1 and our folder beautifier.

Not a Coursera clone. It does not unlock quizzes, labs, or graded projects.

Private repo: [lumotic-ca/courdl](https://github.com/lumotic-ca/courdl).

## What you get

- Videos (`.mp4`), subtitles (`.srt`), and reading HTML
- Numbered folders and a `README.md` table of contents
- Default library: `Documents/CourDL` (you can change it)

## Windows setup

1. Install the latest **unsigned** NSIS installer from [Releases](https://github.com/lumotic-ca/courdl/releases) (`CourDL_*_x64-setup.exe`). SmartScreen may warn because there is no Authenticode cert.
2. Windows 10 needs [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/). Windows 11 usually already has it.
3. Log in to Coursera in a browser. Export cookies for `.coursera.org` (Cookie-Editor Netscape or JSON, or "Get cookies.txt LOCALLY"). HttpOnly rows are fine. `CAUTH` is required.
4. In CourDL, import that file. Cookies usually last about two weeks. Re-import when downloads 401 or skip videos.
5. Paste a **course** URL (`/learn/…`) or slug and click Download. Beautify is on by default.

Cookies are login-equivalent. Never commit them.

### Certificate URLs

A `/professional-certificates/…` link often downloads only the **first** course. For a full cert, use each included `/learn/` URL (as Coursera lists them separately). On Linux you can batch that list with `scripts/batch-from-links.py` (see [docs/engine.md](docs/engine.md)).

## Linux / develop

The GUI is Windows-first. On this host, use the engine CLI or the batch script:

```bash
cd engine && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/courdl-engine check-cookies --file ~/Documents/cookies.txt
.venv/bin/courdl-engine download --cookies ~/Documents/cookies.txt \
  --outdir ~/Documents/CourDL --input 'https://www.coursera.org/learn/<slug>'
```

GUI dev: [docs/packaging.md](docs/packaging.md). Structure: [docs/architecture.md](docs/architecture.md). Agent notes: [AGENTS.md](AGENTS.md).

## Credits

See [NOTICE.md](NOTICE.md).
