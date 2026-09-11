use std::path::{Path, PathBuf};
use std::sync::Mutex;

use serde::Deserialize;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

use crate::error::{ok, Envelope};
use crate::paths::{cookies_path, ensure_dir};
use crate::prereqs::{evaluate, ready};
use crate::settings::{self, Settings};

#[derive(Default)]
pub struct JobState {
    pub child: Mutex<Option<CommandChild>>,
    pub library: Mutex<Option<PathBuf>>,
    pub active_dest: Mutex<Option<PathBuf>>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadOptions {
    pub input: String,
    pub skip_existing: bool,
    pub beautify: bool,
}

fn sidecar_command(
    app: &AppHandle,
) -> Result<tauri_plugin_shell::process::Command, String> {
    app.shell()
        .sidecar("courdl-engine")
        .map_err(|e| format!("Engine sidecar not found: {e}"))
}

fn is_inside_library(library: &Path, dest: &Path) -> bool {
    let lib = library.canonicalize().unwrap_or_else(|_| library.to_path_buf());
    let target = if dest.exists() {
        dest.canonicalize().unwrap_or_else(|_| dest.to_path_buf())
    } else {
        dest.to_path_buf()
    };
    target.starts_with(&lib) && target != lib
}

fn delete_in_progress(library: Option<&PathBuf>, dest: Option<&PathBuf>) -> Option<String> {
    let library = library?;
    let dest = dest?;
    if !is_inside_library(library, dest) {
        return None;
    }
    if dest.exists() {
        let _ = std::fs::remove_dir_all(dest);
        return Some(dest.display().to_string());
    }
    None
}

fn kill_sidecar(child: CommandChild) {
    #[cfg(windows)]
    {
        let pid = child.pid();
        let _ = std::process::Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .status();
    }
    let _ = child.kill();
}

#[tauri::command]
pub async fn engine_version(app: AppHandle) -> Envelope<serde_json::Value> {
    match sidecar_command(&app) {
        Ok(cmd) => match cmd.args(["version"]).output().await {
            Ok(out) if out.status.success() => {
                let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
                match serde_json::from_str(&text) {
                    Ok(v) => crate::error::ok_json(v),
                    Err(_) => crate::error::ok_json(serde_json::json!({"raw": text})),
                }
            }
            Ok(out) => crate::error::err_json(
                "engine",
                String::from_utf8_lossy(&out.stderr).trim().to_string(),
            ),
            Err(e) => crate::error::err_json("engine", e.to_string()),
        },
        Err(e) => crate::error::err_json("sidecar", e),
    }
}

#[tauri::command]
pub async fn resolve_preview(app: AppHandle, input: String) -> Envelope<serde_json::Value> {
    let trimmed = input.trim().to_string();
    if trimmed.is_empty() {
        return crate::error::ok_json(serde_json::json!({ "preview": "" }));
    }
    match sidecar_command(&app) {
        Ok(cmd) => match cmd.args(["resolve", "--input", &trimmed]).output().await {
            Ok(out) if out.status.success() => {
                let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
                match serde_json::from_str(&text) {
                    Ok(v) => crate::error::ok_json(v),
                    Err(_) => crate::error::ok_json(serde_json::json!({"raw": text})),
                }
            }
            Ok(out) => crate::error::err_json(
                "resolve",
                String::from_utf8_lossy(&out.stderr).trim().to_string(),
            ),
            Err(e) => crate::error::err_json("engine", e.to_string()),
        },
        Err(e) => crate::error::err_json("sidecar", e),
    }
}

#[tauri::command]
pub async fn check_cookies(app: AppHandle) -> Envelope<serde_json::Value> {
    let path = match cookies_path(&app) {
        Ok(p) if p.is_file() => p,
        _ => {
            return crate::error::err_json("cookies_missing", "No cookies imported yet.");
        }
    };
    match sidecar_command(&app) {
        Ok(cmd) => match cmd
            .args(["check-cookies", "--file", &path.display().to_string()])
            .output()
            .await
        {
            Ok(out) if out.status.success() => {
                let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
                match serde_json::from_str(&text) {
                    Ok(v) => crate::error::ok_json(v),
                    Err(_) => crate::error::ok_json(serde_json::json!({"raw": text})),
                }
            }
            Ok(out) => crate::error::err_json(
                "cookies",
                String::from_utf8_lossy(&out.stderr)
                    .trim()
                    .to_string(),
            ),
            Err(e) => crate::error::err_json("engine", e.to_string()),
        },
        Err(e) => crate::error::err_json("sidecar", e),
    }
}

#[tauri::command]
pub async fn start_download(
    app: AppHandle,
    job: tauri::State<'_, JobState>,
    options: DownloadOptions,
) -> Result<Envelope<bool>, String> {
    if options.input.trim().is_empty() {
        return Ok(crate::error::err::<bool>(
            "input",
            "Paste a Coursera URL or course slug.",
        ));
    }
    let report = evaluate(&app);
    if !ready(&report) {
        let msg = report
            .notes
            .first()
            .cloned()
            .unwrap_or_else(|| "CourDL is not ready to download.".into());
        return Ok(crate::error::err::<bool>("prereq", msg));
    }
    {
        let guard = job.child.lock().map_err(|e| e.to_string())?;
        if guard.is_some() {
            return Ok(crate::error::err::<bool>(
                "busy",
                "A download is already running. Cancel it first.",
            ));
        }
    }

    let cookies = cookies_path(&app)?;
    let mut cfg = settings::load(&app);
    cfg.last_url = options.input.clone();
    cfg.skip_existing = options.skip_existing;
    cfg.beautify = options.beautify;
    settings::save(&app, &cfg)?;
    let outdir = cfg.library_path.clone();
    ensure_dir(std::path::Path::new(&outdir))?;
    *job.library.lock().map_err(|e| e.to_string())? = Some(PathBuf::from(&outdir));
    *job.active_dest.lock().map_err(|e| e.to_string())? = None;

    let mut args = vec![
        "download".into(),
        "--cookies".into(),
        cookies.display().to_string(),
        "--outdir".into(),
        outdir,
        "--input".into(),
        options.input.trim().to_string(),
    ];
    if options.skip_existing {
        args.push("--skip-existing".into());
    }
    if !options.beautify {
        args.push("--no-beautify".into());
    }

    let cmd = sidecar_command(&app)?.args(args);
    let (mut rx, child) = cmd.spawn().map_err(|e| format!("Failed to start engine: {e}"))?;
    *job.child.lock().map_err(|e| e.to_string())? = Some(child);

    let _ = app.emit("download-started", ());

    let app_clone = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) | CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(&line).to_string();
                    for piece in text.split_inclusive('\n') {
                        if piece.trim().is_empty() {
                            continue;
                        }
                        if let Ok(json) = serde_json::from_str::<serde_json::Value>(piece.trim()) {
                            if json.get("courdl").and_then(|v| v.as_bool()) == Some(true) {
                                if json.get("phase").and_then(|v| v.as_str()) == Some("dest") {
                                    if let Some(path) = json.get("path").and_then(|v| v.as_str()) {
                                        if let Ok(mut dest) =
                                            app_clone.state::<JobState>().active_dest.lock()
                                        {
                                            *dest = Some(PathBuf::from(path));
                                        }
                                    }
                                }
                                let _ = app_clone.emit("download-progress", json);
                                continue;
                            }
                        }
                        let _ = app_clone.emit("download-log", piece.to_string());
                    }
                }
                CommandEvent::Terminated(payload) => {
                    let _ = app_clone.emit(
                        "download-finished",
                        serde_json::json!({
                            "code": payload.code,
                            "signal": payload.signal,
                        }),
                    );
                    break;
                }
                CommandEvent::Error(message) => {
                    let _ = app_clone.emit("download-log", format!("[error] {message}\n"));
                }
                _ => {}
            }
        }
        if let Ok(mut guard) = app_clone.state::<JobState>().child.lock() {
            *guard = None;
        }
    });

    Ok(ok(true))
}

#[tauri::command]
pub fn cancel_download(app: AppHandle, job: tauri::State<JobState>) -> Envelope<serde_json::Value> {
    let child = match job.child.lock() {
        Ok(mut guard) => guard.take(),
        Err(e) => return crate::error::err_json("lock", e.to_string()),
    };
    if child.is_none() {
        return crate::error::err_json("idle", "No download is running.");
    }
    if let Some(child) = child {
        kill_sidecar(child);
    }
    let dest = job.active_dest.lock().ok().and_then(|g| g.clone());
    let library = job.library.lock().ok().and_then(|g| g.clone());
    let removed = delete_in_progress(library.as_ref(), dest.as_ref());
    if let Ok(mut dest_guard) = job.active_dest.lock() {
        *dest_guard = None;
    }
    let _ = app.emit(
        "download-cancelled",
        serde_json::json!({ "removed": removed }),
    );
    crate::error::ok_json(serde_json::json!({
        "cancelled": true,
        "removed": removed,
    }))
}

#[tauri::command]
pub fn get_settings(app: AppHandle) -> Envelope<Settings> {
    ok(settings::load(&app))
}

#[tauri::command]
pub fn save_settings(app: AppHandle, data: Settings) -> Envelope<Settings> {
    if data.library_path.trim().is_empty() {
        return crate::error::err::<Settings>("library", "Choose a library folder.");
    }
    match settings::save(&app, &data) {
        Ok(()) => ok(data),
        Err(e) => crate::error::err::<Settings>("io", e),
    }
}
