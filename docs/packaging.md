# CourDL packaging

## Sidecar name

Tauri looks for `src-tauri/binaries/courdl-engine-<target-triple>[.exe]`.

Windows CI copies:

`courdl-engine-x86_64-pc-windows-msvc.exe`

## Local Linux / macOS development

```bash
cd engine && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cd .. && bash scripts/link-dev-sidecar.sh
npm install
npm run dev
```

## Windows release

GitHub Actions workflow `.github/workflows/release-windows-nsis.yml`:

1. Install Python 3.12 and PyInstaller
2. Build the sidecar
3. `npm ci` and `npx tauri build --bundles nsis`
4. Upload the NSIS `.exe` to a GitHub Release

The installer is **unsigned**. Windows SmartScreen will warn until an Authenticode cert is added.

WebView2 is required on Windows 10. Windows 11 usually already has it.
