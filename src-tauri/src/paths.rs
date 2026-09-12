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
    let names = sidecar_binary_names(&target_triple(), cfg!(windows));
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()));
    let resource_dir = app.path().resource_dir().ok();
    let dirs = sidecar_search_dirs(
        exe_dir.as_deref(),
        resource_dir.as_deref(),
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("binaries"),
    );

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

pub(crate) fn sidecar_binary_names(triple: &str, windows: bool) -> Vec<String> {
    if windows {
        vec![
            format!("courdl-engine-{triple}.exe"),
            "courdl-engine.exe".into(),
        ]
    } else {
        vec![
            format!("courdl-engine-{triple}"),
            "courdl-engine".into(),
        ]
    }
}

/// Directories that may contain the bundled engine, including a macOS .app layout.
pub(crate) fn sidecar_search_dirs(
    exe_dir: Option<&Path>,
    resource_dir: Option<&Path>,
    cargo_binaries: PathBuf,
) -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Some(dir) = exe_dir {
        dirs.push(dir.to_path_buf());
        if dir.file_name().and_then(|n| n.to_str()) == Some("MacOS") {
            if let Some(contents) = dir.parent() {
                dirs.push(contents.join("Resources"));
                dirs.push(contents.join("Resources").join("binaries"));
                dirs.push(contents.join("MacOS"));
            }
        }
    }
    if let Some(res) = resource_dir {
        dirs.push(res.to_path_buf());
        dirs.push(res.join("binaries"));
        if let Some(parent) = res.parent() {
            dirs.push(parent.to_path_buf());
            dirs.push(parent.join("MacOS"));
        }
    }
    dirs.push(cargo_binaries);
    dirs
}

pub(crate) fn target_triple() -> String {
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

#[cfg(test)]
mod tests {
    use super::{sidecar_binary_names, sidecar_search_dirs, target_triple};
    use std::path::{Path, PathBuf};

    #[test]
    fn unix_sidecar_names_include_triple() {
        let names = sidecar_binary_names("aarch64-apple-darwin", false);
        assert_eq!(names[0], "courdl-engine-aarch64-apple-darwin");
        assert_eq!(names[1], "courdl-engine");
    }

    #[test]
    fn windows_sidecar_names_include_exe() {
        let names = sidecar_binary_names("x86_64-pc-windows-msvc", true);
        assert_eq!(names[0], "courdl-engine-x86_64-pc-windows-msvc.exe");
        assert_eq!(names[1], "courdl-engine.exe");
    }

    #[test]
    fn macos_app_bundle_search_includes_resources() {
        let exe = PathBuf::from("/Applications/CourDL.app/Contents/MacOS");
        let res = PathBuf::from("/Applications/CourDL.app/Contents/Resources");
        let dirs = sidecar_search_dirs(Some(&exe), Some(&res), PathBuf::from("/tmp/binaries"));
        assert!(dirs.iter().any(|d| d == Path::new("/Applications/CourDL.app/Contents/MacOS")));
        assert!(dirs.iter().any(|d| d == Path::new("/Applications/CourDL.app/Contents/Resources")));
        assert!(dirs.iter().any(|d| d.ends_with("Resources/binaries")));
        assert!(dirs.iter().any(|d| d == Path::new("/tmp/binaries")));
    }

    #[test]
    fn target_triple_is_nonempty() {
        assert!(!target_triple().is_empty());
    }
}
