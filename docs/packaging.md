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

## macOS release

Workflow `.github/workflows/release-macos.yml` (manual). It checks out a git ref, builds a PyInstaller sidecar named `courdl-engine-<rustc-host>`, then `tauri build --bundles app,dmg`.

Apple Silicon CI uses `macos-14` (`aarch64-apple-darwin`). The DMG is **unsigned**. First open: right-click the app, choose Open.

Example: attach a 0.1.3 Apple Silicon DMG to the existing `v0.1.3` release by dispatching the workflow with `git_ref=v0.1.3` and `release_tag=v0.1.3`.

## Windows release

GitHub Actions workflow `.github/workflows/release-windows-nsis.yml`:

1. Install Python 3.12 and PyInstaller
2. Build the sidecar
The NSIS `.exe` lands at `target/release/bundle/nsis/` when using the repo-root Cargo workspace (not `src-tauri/target`).

The installer is **unsigned**. Windows SmartScreen will warn until an Authenticode cert is added.

WebView2 is required on Windows 10. Windows 11 usually already has it.
