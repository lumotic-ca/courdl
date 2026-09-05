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
pub fn cancel_download(job: tauri::State<JobState>) -> Envelope<bool> {
    match job.child.lock() {
        Ok(mut guard) => {
            if let Some(child) = guard.take() {
                let _ = child.kill();
                ok(true)
            } else {
                crate::error::err::<bool>("idle", "No download is running.")
            }
        }
        Err(e) => crate::error::err::<bool>("lock", e.to_string()),
    }
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
