# CourDL packaging

## Sidecar name

Tauri `externalBin` is `binaries/courdl-engine`. The file on disk must be `courdl-engine-<target-triple>[.exe]`.

Windows CI copies:

`src-tauri/binaries/courdl-engine-x86_64-pc-windows-msvc.exe`

NSIS places that binary **next to** `CourDL.exe`, not under `resources/`. `paths.rs` probes the exe directory first. If you only search `resource_dir()`, Windows builds report "Missing: CourDL engine".

This repo is a Cargo workspace. The NSIS installer is at **repo-root** `target/release/bundle/nsis/`, not `src-tauri/target/…`. The release workflow uploads both globs.

## Local Linux / macOS development

```bash
cd engine && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cd .. && bash scripts/link-dev-sidecar.sh
npm install
npm run dev
```

`link-dev-sidecar.sh` drops a stub binary Tauri can resolve. Real downloads need a built sidecar or `python -m courdl_engine`.

## Windows release

GitHub Actions `.github/workflows/release-windows-nsis.yml` on `v*` tags:

1. Python 3.12, `pip install -e ".[pack]"`, PyInstaller `courdl-engine.spec`
2. Copy sidecar into `src-tauri/binaries/` with the msvc triple name
3. `npx tauri build --bundles nsis`
4. Attach `CourDL_*_x64-setup.exe` to the GitHub Release

The installer is **unsigned**. Windows SmartScreen will warn until an Authenticode cert is added.

WebView2 is required on Windows 10. Windows 11 usually already has it. Install mode is current-user NSIS.
