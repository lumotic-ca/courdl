use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

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
    pub session_log: Mutex<Option<PathBuf>>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadOptions {
    pub input: String,
    pub skip_existing: bool,
    pub beautify: bool,
    #[serde(default)]
    pub session_stamp: Option<String>,
}

fn sidecar_command(
    app: &AppHandle,
) -> Result<tauri_plugin_shell::process::Command, String> {
    app.shell()
        .sidecar("courdl-engine")
        .map(|cmd| {
            cmd.env("PYTHONUTF8", "1")
                .env("PYTHONIOENCODING", "utf-8")
        })
        .map_err(|e| format!("Engine sidecar not found: {e}"))
}

fn parse_sidecar_json(stdout: &[u8], stderr: &[u8]) -> Result<serde_json::Value, String> {
    let text = String::from_utf8_lossy(stdout);
    let trimmed = text.trim();
    let try_parse = |s: &str| serde_json::from_str::<serde_json::Value>(s).ok();
    if let Some(v) = try_parse(trimmed) {
        return Ok(v);
    }
    if let Some(start) = trimmed.find('{') {
        let from_brace = trimmed[start..].trim();
        if let Some(v) = try_parse(from_brace) {
            return Ok(v);
        }
        if let Some(end) = from_brace.rfind('}') {
            if let Some(v) = try_parse(&from_brace[..=end]) {
                return Ok(v);
            }
        }
    }
    let err = String::from_utf8_lossy(stderr);
    let err = err.trim();
    if !err.is_empty() {
        return Err(err.to_string());
    }
    Err(format!(
        "Engine returned non-JSON: {}",
        trimmed.chars().take(200).collect::<String>()
    ))
}

fn with_preview_fallback(mut value: serde_json::Value) -> serde_json::Value {
    let Some(obj) = value.as_object_mut() else {
        return value;
    };
    let existing = obj
        .get("preview")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty());
    if existing.is_some() {
        return value;
    }
    let kind = obj
        .get("kind")
        .and_then(|v| v.as_str())
        .unwrap_or("course")
        .to_string();
    let n = obj
        .get("courseCount")
        .and_then(|v| v.as_u64())
        .or_else(|| {
            obj.get("courses")
                .and_then(|v| v.as_array())
                .map(|a| a.len() as u64)
        });
    if let Some(n) = n {
        if kind != "course" || n > 1 {
            let label = if kind == "specialization" {
                "specialization"
            } else {
                "certificate"
            };
            let word = if n == 1 { "course" } else { "courses" };
            obj.insert(
                "preview".into(),
                serde_json::Value::String(format!("{n} {word} in this {label}")),
            );
        }
    }
    value
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

fn safe_stamp(raw: Option<&str>) -> String {
    let cleaned: String = raw
        .unwrap_or("")
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.'))
        .take(32)
        .collect();
    if cleaned.is_empty() {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs().to_string())
            .unwrap_or_else(|_| "session".into())
    } else {
        cleaned
    }
}

fn create_session_log(library: &Path, stamp: &str, header: &str) -> Result<PathBuf, String> {
    let dir = library.join("courdl-logs");
    std::fs::create_dir_all(&dir).map_err(|e| format!("Could not create courdl-logs: {e}"))?;
    let path = dir.join(format!("courdl-{stamp}.txt"));
    let mut file = OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .open(&path)
        .map_err(|e| format!("Could not write session log: {e}"))?;
    file.write_all(header.as_bytes())
        .and_then(|_| file.flush())
        .map_err(|e| format!("Could not write session log: {e}"))?;
    Ok(path)
}

fn append_session_log(path: Option<&PathBuf>, line: &str) {
    let Some(path) = path else {
        return;
    };
    let mut text = line.replace('\r', "");
    if !text.ends_with('\n') {
        text.push('\n');
    }
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = file.write_all(text.as_bytes());
        let _ = file.flush();
    }
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
            Ok(out) if out.status.success() => match parse_sidecar_json(&out.stdout, &out.stderr) {
                Ok(v) => crate::error::ok_json(v),
                Err(msg) => crate::error::err_json("engine", msg),
            },
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
            Ok(out) if out.status.success() => match parse_sidecar_json(&out.stdout, &out.stderr) {
                Ok(v) => crate::error::ok_json(with_preview_fallback(v)),
                Err(msg) => crate::error::err_json("resolve", msg),
            },
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
            Ok(out) if out.status.success() => match parse_sidecar_json(&out.stdout, &out.stderr) {
                Ok(v) => crate::error::ok_json(v),
                Err(msg) => crate::error::err_json("cookies", msg),
            },
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
) -> Result<Envelope<serde_json::Value>, String> {
    if options.input.trim().is_empty() {
        return Ok(crate::error::err_json(
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
        return Ok(crate::error::err_json("prereq", msg));
    }
    {
        let guard = job.child.lock().map_err(|e| e.to_string())?;
        if guard.is_some() {
            return Ok(crate::error::err_json(
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

    let stamp = safe_stamp(options.session_stamp.as_deref());
    let header = format!(
        "CourDL session\ninput={}\nskip_existing={}\nbeautify={}\nlibrary={}\n---\n",
        options.input.trim(),
        options.skip_existing,
        options.beautify,
        outdir
    );
    let session_path = create_session_log(Path::new(&outdir), &stamp, &header)?;
    *job.session_log.lock().map_err(|e| e.to_string())? = Some(session_path.clone());

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

    let _ = app.emit(
        "download-started",
        serde_json::json!({ "sessionLog": session_path.display().to_string() }),
    );

    let app_clone = app.clone();
    let session_for_loop = session_path.clone();
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
                                if let Some(msg) = json.get("message").and_then(|v| v.as_str()) {
                                    let phase = json.get("phase").and_then(|v| v.as_str()).unwrap_or("");
                                    append_session_log(
                                        Some(&session_for_loop),
                                        &format!("[{phase}] {msg}"),
                                    );
                                }
                                let _ = app_clone.emit("download-progress", json);
                                continue;
                            }
                        }
                        append_session_log(Some(&session_for_loop), piece);
                        let _ = app_clone.emit("download-log", piece.to_string());
                    }
                }
                CommandEvent::Terminated(payload) => {
                    append_session_log(
                        Some(&session_for_loop),
                        &format!(
                            "---\nengine_exit code={:?} signal={:?}",
                            payload.code, payload.signal
                        ),
                    );
                    let _ = app_clone.emit(
                        "download-finished",
                        serde_json::json!({
                            "code": payload.code,
                            "signal": payload.signal,
                            "sessionLog": session_for_loop.display().to_string(),
                        }),
                    );
                    break;
                }
                CommandEvent::Error(message) => {
                    append_session_log(Some(&session_for_loop), &format!("[error] {message}"));
                    let _ = app_clone.emit("download-log", format!("[error] {message}\n"));
                }
                _ => {}
            }
        }
        if let Ok(mut guard) = app_clone.state::<JobState>().child.lock() {
            *guard = None;
        }
    });

    Ok(crate::error::ok_json(serde_json::json!({
        "started": true,
        "sessionLog": session_path.display().to_string(),
    })))
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
    let session = job.session_log.lock().ok().and_then(|g| g.clone());
    let removed = delete_in_progress(library.as_ref(), dest.as_ref());
    if let Some(ref path) = session {
        let note = match &removed {
            Some(p) => format!("cancelled; deleted in-progress folder {p}"),
            None => "cancelled".into(),
        };
        append_session_log(Some(path), &format!("---\n{note}"));
    }
    if let Ok(mut dest_guard) = job.active_dest.lock() {
        *dest_guard = None;
    }
    let session_log = session.as_ref().map(|p| p.display().to_string());
    let _ = app.emit(
        "download-cancelled",
        serde_json::json!({ "removed": removed, "sessionLog": session_log }),
    );
    crate::error::ok_json(serde_json::json!({
        "cancelled": true,
        "removed": removed,
        "sessionLog": session_log,
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
