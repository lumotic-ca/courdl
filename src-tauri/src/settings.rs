use serde::{Deserialize, Serialize};

use tauri::AppHandle;

use crate::paths::{default_library_dir, ensure_dir, settings_path};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Settings {
    pub library_path: String,
    pub last_url: String,
    pub skip_existing: bool,
    pub beautify: bool,
    pub wizard_complete: bool,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            library_path: default_library_dir().display().to_string(),
            last_url: String::new(),
            skip_existing: true,
            beautify: true,
            wizard_complete: false,
        }
    }
}

pub fn load(app: &AppHandle) -> Settings {
    let path = match settings_path(app) {
        Ok(p) => p,
        Err(_) => return Settings::default(),
    };
    let raw = std::fs::read_to_string(&path).ok();
    let mut s = raw
        .and_then(|t| serde_json::from_str::<Settings>(&t).ok())
        .unwrap_or_default();
    if s.library_path.trim().is_empty() {
        s.library_path = default_library_dir().display().to_string();
    }
    s
}

pub fn save(app: &AppHandle, settings: &Settings) -> Result<(), String> {
    let path = settings_path(app)?;
    if let Some(parent) = path.parent() {
        ensure_dir(parent)?;
    }
    let data = serde_json::to_string_pretty(settings).map_err(|e| e.to_string())?;
    std::fs::write(&path, data).map_err(|e| format!("Write settings: {e}"))
}
