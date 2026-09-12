use std::path::PathBuf;

use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;

use crate::error::{ok, Envelope};
use crate::paths::{cookies_path, ensure_dir};

fn cookies_look_valid(raw: &str) -> bool {
    raw.to_ascii_uppercase().contains("CAUTH")
}

fn picked_to_string(
    picked: Option<tauri_plugin_dialog::FilePath>,
) -> Result<Option<String>, String> {
    let Some(file) = picked else {
        return Ok(None);
    };
    file.into_path()
        .map(|path| Some(path.display().to_string()))
        .map_err(|e| format!("Could not read the selected path: {e}"))
}

/// Async on purpose: `blocking_pick_*` from a sync command deadlocks macOS (NSOpenPanel).
#[tauri::command]
pub async fn pick_cookies_file(app: AppHandle) -> Envelope<Option<String>> {
    let picked = app
        .dialog()
        .file()
        .set_title("Import Coursera cookies")
        .add_filter("Cookies", &["txt"])
        .blocking_pick_file();
    match picked_to_string(picked) {
        Ok(path) => ok(path),
        Err(e) => crate::error::err("dialog", e),
    }
}

#[tauri::command]
pub fn import_cookies(app: AppHandle, source: String) -> Envelope<String> {
    let src = PathBuf::from(source.trim());
    if source.trim().is_empty() {
        return crate::error::err::<String>("cookies_missing", "Choose a Netscape cookies.txt file.");
    }
    if !src.is_file() {
        return crate::error::err::<String>(
            "cookies_missing",
            format!("That cookies file is not readable: {}", src.display()),
        );
    }
    let raw = match std::fs::read_to_string(&src) {
        Ok(s) => s,
        Err(e) => {
            return crate::error::err::<String>(
                "cookies_missing",
                format!("Could not read that cookies file: {e}"),
            )
        }
    };
    if !cookies_look_valid(&raw) {
        return crate::error::err::<String>(
            "cookies_missing",
            "That file has no CAUTH cookie. Export cookies from a logged-in Coursera session.",
        );
    }
    let dest = match cookies_path(&app) {
        Ok(p) => p,
        Err(e) => return crate::error::err::<String>("io", e),
    };
    if let Some(parent) = dest.parent() {
        if let Err(e) = ensure_dir(parent) {
            return crate::error::err::<String>("io", e);
        }
    }
    if let Err(e) = std::fs::copy(&src, &dest) {
        return crate::error::err::<String>("io", format!("Could not copy cookies: {e}"));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&dest, std::fs::Permissions::from_mode(0o600));
    }
    ok(dest.display().to_string())
}

pub fn cookies_exist(app: &AppHandle) -> bool {
    cookies_path(app).ok().is_some_and(|p| p.is_file())
}

#[cfg(test)]
mod tests {
    use super::{cookies_look_valid, picked_to_string};

    #[test]
    fn cancel_returns_none() {
        assert_eq!(picked_to_string(None).unwrap(), None);
    }

    #[test]
    fn cauth_detection() {
        assert!(cookies_look_valid("# Netscape\n.coursera.org\tTRUE\t/\tTRUE\t1\tCAUTH\ttoken\n"));
        assert!(cookies_look_valid(r#"[{"name":"cauth","value":"x"}]"#));
        assert!(!cookies_look_valid("hello cookies"));
    }
}
