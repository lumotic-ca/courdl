use std::path::{Path, PathBuf};

use tauri::{AppHandle, Manager};

pub fn app_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_data_dir()
        .map_err(|e| format!("App data dir: {e}"))
}

pub fn cookies_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("cookies.txt"))
}

pub fn settings_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("settings.json"))
}

pub fn default_library_dir() -> PathBuf {
    if let Ok(home) = std::env::var("USERPROFILE").or_else(|_| std::env::var("HOME")) {
        return PathBuf::from(home).join("Documents").join("CourDL");
    }
    PathBuf::from("CourDL")
}

pub fn sidecar_present(app: &AppHandle) -> bool {
    app.shell_sidecar_hint()
}

trait ShellHint {
    fn shell_sidecar_hint(&self) -> bool;
}

impl ShellHint for AppHandle {
    fn shell_sidecar_hint(&self) -> bool {
        // Sidecar is bundled at runtime; in dev the file must exist under binaries/.
        let triple = tauri_utils_triple();
        let exe = if cfg!(windows) {
            format!("courdl-engine-{triple}.exe")
        } else {
            format!("courdl-engine-{triple}")
        };
        let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("binaries")
            .join(&exe);
        if dev.is_file() {
            return true;
        }
        if let Ok(res) = self.path().resource_dir() {
            let bundled = res.join(&exe);
            if bundled.is_file() {
                return true;
            }
        }
        false
    }
}

fn tauri_utils_triple() -> String {
    let arch = std::env::consts::ARCH;
    let os = std::env::consts::OS;
    match (arch, os) {
        ("x86_64", "windows") => "x86_64-pc-windows-msvc".into(),
        ("x86_64", "linux") => "x86_64-unknown-linux-gnu".into(),
        ("aarch64", "linux") => "aarch64-unknown-linux-gnu".into(),
        ("aarch64", "macos") => "aarch64-apple-darwin".into(),
        ("x86_64", "macos") => "x86_64-apple-darwin".into(),
        _ => format!("{arch}-unknown-{os}"),
    }
}

pub fn ensure_dir(path: &Path) -> Result<(), String> {
    std::fs::create_dir_all(path).map_err(|e| format!("Create dir {}: {e}", path.display()))
}
