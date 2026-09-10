# CourDL release

- **Do not tag** unless the owner asked.
- Version lockstep: `package.json`, `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, `engine/pyproject.toml`, `ENGINE_VERSION`.
- Tag shape: `v0.2.1`. Workflow [release-windows-nsis.yml](../.github/workflows/release-windows-nsis.yml) builds PyInstaller sidecar + NSIS and attaches `CourDL_*_x64-setup.exe`.
- Installer is **unsigned**. SmartScreen will warn. Windows 10 needs WebView2.
- After the tag: wait for CI, confirm the `.exe` is on the GitHub Release, then call it done.
- Do not move or delete an older tag to hide a bug. Ship a patch version.

CI tests: [.github/workflows/ci.yml](../.github/workflows/ci.yml) (pytest on Ubuntu and Windows).
