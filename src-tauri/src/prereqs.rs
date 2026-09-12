use serde::Serialize;
use tauri::AppHandle;

use crate::auth::cookies_exist;
use crate::error::{ok, Envelope};
use crate::paths::{cookies_path, sidecar_path, sidecar_present};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PrerequisiteReport {
    pub platform: String,
    pub sidecar: bool,
    pub cookies: bool,
    pub webview2: bool,
    pub cookies_path: Option<String>,
    pub notes: Vec<String>,
}

pub fn evaluate(app: &AppHandle) -> PrerequisiteReport {
    let mut notes = Vec::new();
    let sidecar = sidecar_present(app);
    if let Some(path) = sidecar_path(app) {
        notes.push(format!("Engine: {}", path.display()));
    } else if sidecar {
        notes.push("Engine sidecar is registered with the app shell.".into());
    } else {
        notes.push(engine_missing_note());
    }
    let cookies = cookies_exist(app);
    if !cookies {
        notes.push("Import a Netscape cookies.txt from a logged-in Coursera session (CAUTH required).".into());
    }
    let webview2 = webview2_ok();
    if !webview2 {
        notes.push(
            "WebView2 runtime is missing. Install the Evergreen WebView2 runtime from Microsoft, then reopen CourDL."
                .into(),
        );
    }
    PrerequisiteReport {
        platform: std::env::consts::OS.to_string(),
        sidecar,
        cookies,
        webview2,
        cookies_path: cookies_path(app).ok().map(|p| p.display().to_string()),
        notes,
    }
}

pub fn ready(report: &PrerequisiteReport) -> bool {
    report.sidecar && report.cookies && report.webview2
}

fn engine_missing_note() -> String {
    if cfg!(target_os = "macos") {
        "CourDL engine was not found next to the app. Reinstall the DMG from the GitHub Release, then run: xattr -cr /Applications/CourDL.app"
            .into()
    } else if cfg!(windows) {
        "CourDL engine was not found next to the app. Reinstall from the GitHub Release .exe."
            .into()
    } else {
        "CourDL engine was not found next to the app. Reinstall CourDL."
            .into()
    }
}

fn webview2_ok() -> bool {
    #[cfg(windows)]
    {
        use std::path::PathBuf;
        use std::process::Command;
        let pf = std::env::var("ProgramFiles").unwrap_or_else(|_| r"C:\Program Files".into());
        let pf86 =
            std::env::var("ProgramFiles(x86)").unwrap_or_else(|_| r"C:\Program Files (x86)".into());
        for base in [pf.as_str(), pf86.as_str()] {
            let path = PathBuf::from(base)
                .join("Microsoft")
                .join("EdgeWebView")
                .join("Application");
            if path.is_dir() {
                return true;
            }
        }
        Command::new("reg")
            .args([
                "query",
                r"HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                "/v",
                "pv",
            ])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
    #[cfg(not(windows))]
    {
        true
    }
}

#[tauri::command]
pub fn check_prerequisites(app: AppHandle) -> Envelope<PrerequisiteReport> {
    ok(evaluate(&app))
}

#[tauri::command]
pub fn can_download(app: AppHandle) -> Envelope<bool> {
    ok(ready(&evaluate(&app)))
}
