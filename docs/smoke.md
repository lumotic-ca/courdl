# CourDL smoke checks

Automated checks (Linux or macOS with the engine venv):

```bash
python3 -m venv engine/.venv
engine/.venv/bin/pip install -e ".[dev]"
bash scripts/smoke.sh
```

That runs engine pytest, Rust unit tests, `cargo check`, and a regression grep that file pickers stay `async fn`. It does not open the GUI.

## Manual: macOS (Apple Silicon DMG)

Use 0.1.6 or later. The 0.1.3 DMG still freezes on file dialogs.

1. Copy `CourDL.app` to `/Applications`.
2. Clear quarantine: `xattr -cr /Applications/CourDL.app`
3. Open the app. Status should list the engine and wait for cookies. It should not say to reinstall a `.exe`.
4. **File pickers (the freeze regression):**
   - Import cookies, then cancel. The app stays responsive. Status is not an error.
   - Import a real `cookies.txt` with `CAUTH`. Status becomes OK.
   - Import a text file with no `CAUTH`. You get an error, not a freeze.
   - Change library folder, cancel, then pick `Documents/CourDL` (or another folder). Library path updates.
5. Paste a `/learn/` URL. Preview shows a module count or stays blank only if resolve failed with a message.
6. Paste a certificate URL. Preview shows `{n} courses in this certificate`.
7. Open library. Finder shows the folder.
8. Download one short enrolled course with skip-existing off. Log moves. Session file appears under `courdl-logs/`.
9. Start a download, click Cancel. The in-progress course folder is removed. Sibling finished courses stay.
10. Force-quit is not needed after any picker.

Intel Macs need a separate `x86_64` build. The current DMG is Apple Silicon only.

## Manual: Windows

1. Install the NSIS `.exe`. If SmartScreen warns, that is the unsigned build.
2. Confirm WebView2 on Windows 10.
3. Same picker, preview, download, and cancel checks as macOS. Cancel should stop `courdl-engine` and its children (`taskkill /T`).

## Known remaining Mac limits (not this change)

- The app is ad-hoc signed, not notarized. Gatekeeper may still say it is damaged until `xattr -cr`.
- PyInstaller on macOS can later need `allow-unsigned-executable-memory` if the sidecar crashes on launch. Entitlements are in `src-tauri/entitlements.macos.plist` for the next DMG build.
- iCloud Desktop and Documents can make the library folder slow. Prefer a local folder if listing stalls.
