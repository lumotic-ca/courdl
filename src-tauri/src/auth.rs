use std::path::PathBuf;

use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;

use crate::error::{ok, Envelope};
use crate::paths::{cookies_path, ensure_dir};

#[tauri::command]
pub fn pick_cookies_file(app: AppHandle) -> Envelope<Option<String>> {
    let picked = app.dialog().file().blocking_pick_file();
    let path = picked.and_then(|p| p.into_path().ok().map(|p| p.display().to_string()));
    ok(path)
}

#[tauri::command]
pub fn import_cookies(app: AppHandle, source: String) -> Envelope<String> {
    let src = PathBuf::from(source.trim());
    if !src.is_file() {
        return crate::error::err::<String>("cookies_missing", "Choose a Netscape cookies.txt file.");
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
