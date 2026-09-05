use std::path::{Path, PathBuf};

use tauri::{AppHandle, Manager};
use tauri_plugin_shell::ShellExt;

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
    sidecar_path(app).is_some() || app.shell().sidecar("courdl-engine").is_ok()
}

/// Tauri copies externalBin next to the app exe (not into resource_dir).
pub fn sidecar_path(app: &AppHandle) -> Option<PathBuf> {
    let triple = target_triple();
    let names: Vec<String> = if cfg!(windows) {
        vec![
            format!("courdl-engine-{triple}.exe"),
            "courdl-engine.exe".into(),
        ]
    } else {
        vec![
            format!("courdl-engine-{triple}"),
            "courdl-engine".into(),
        ]
    };

    let mut dirs = Vec::new();
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            dirs.push(dir.to_path_buf());
        }
    }
    if let Ok(res) = app.path().resource_dir() {
        dirs.push(res.clone());
        dirs.push(res.join("binaries"));
        if let Some(parent) = res.parent() {
            dirs.push(parent.to_path_buf());
        }
    }
    dirs.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("binaries"));

    for dir in dirs {
        for name in &names {
            let candidate = dir.join(name);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

fn target_triple() -> String {
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
