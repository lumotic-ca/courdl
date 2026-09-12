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

Apple Silicon CI uses `macos-14` (`aarch64-apple-darwin`). The app is **ad-hoc signed, not notarized**. GitHub downloads get a quarantine flag, and macOS reports that as "CourDL is damaged". That is Gatekeeper, not a bad file.

After copying to Applications:

```bash
xattr -cr /Applications/CourDL.app
open /Applications/CourDL.app
```

File pickers (import cookies, change library folder) must run as **async** Tauri commands. A sync `blocking_pick_*` call deadlocks the macOS open panel and the app must be force-quit. See [smoke.md](smoke.md).

The PyInstaller sidecar is windowed on macOS (`console=False`) so Finder does not attach a Terminal. CI re-signs the sidecar with `src-tauri/entitlements.macos.plist`.

Example: attach a 0.1.3 Apple Silicon DMG to the existing `v0.1.3` release by dispatching the workflow with `git_ref=v0.1.3` and `release_tag=v0.1.3`. That older DMG still has the file-picker freeze.

## Windows release

GitHub Actions workflow `.github/workflows/release-windows-nsis.yml`:

1. Install Python 3.12 and PyInstaller
2. Build the sidecar
The NSIS `.exe` lands at `target/release/bundle/nsis/` when using the repo-root Cargo workspace (not `src-tauri/target`).

The installer is **unsigned**. Windows SmartScreen will warn until an Authenticode cert is added.

WebView2 is required on Windows 10. Windows 11 usually already has it.
