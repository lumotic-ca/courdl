use serde::Serialize;
use std::fs;
use std::path::PathBuf;

use tauri::AppHandle;
use tauri_plugin_opener::OpenerExt;

use crate::error::{ok, Envelope};
use crate::settings::load;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LibraryItem {
    pub name: String,
    pub path: String,
    pub kind: String,
}

fn looks_like_course(dir: &std::path::Path) -> bool {
    if dir.join("README.md").is_file() {
        return true;
    }
    if dir.join(".cache").join("crawl.json").is_file() {
        return true;
    }
    let Ok(rd) = fs::read_dir(dir) else {
        return false;
    };
    rd.flatten().any(|e| {
        e.file_type().map(|t| t.is_dir()).unwrap_or(false)
            && e.file_name()
                .to_string_lossy()
                .starts_with(|c: char| c.is_ascii_digit())
    })
}

#[tauri::command]
pub fn list_library(app: AppHandle) -> Envelope<Vec<LibraryItem>> {
    let root = PathBuf::from(load(&app).library_path);
    if !root.is_dir() {
        return ok(Vec::new());
    }
    let mut items = Vec::new();
    let Ok(rd) = fs::read_dir(&root) else {
        return ok(items);
    };
    for entry in rd.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with('.') || name == "courdl-logs" {
            continue;
        }
        if looks_like_course(&path) {
            items.push(LibraryItem {
                name,
                path: path.display().to_string(),
                kind: "course".into(),
            });
        }
    }
    items.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));
    ok(items)
}

#[tauri::command]
pub fn open_library_folder(app: AppHandle) -> Envelope<String> {
    let path = load(&app).library_path;
    let p = PathBuf::from(&path);
    if !p.exists() {
        if let Err(e) = fs::create_dir_all(&p) {
            return crate::error::err::<String>("io", format!("Could not create library folder: {e}"));
        }
    }
    match app.opener().open_path(&path, None::<&str>) {
        Ok(()) => ok(path),
        Err(e) => crate::error::err::<String>("open", format!("Could not open folder: {e}")),
    }
}

#[tauri::command]
pub async fn pick_library_dir(app: AppHandle) -> Envelope<Option<String>> {
    use tauri_plugin_dialog::DialogExt;
    let picked = app
        .dialog()
        .file()
        .set_title("Choose CourDL library folder")
        .blocking_pick_folder();
    let Some(folder) = picked else {
        return ok(None);
    };
    match folder.into_path() {
        Ok(path) => ok(Some(path.display().to_string())),
        Err(e) => crate::error::err("dialog", format!("Could not read the selected folder: {e}")),
    }
}
