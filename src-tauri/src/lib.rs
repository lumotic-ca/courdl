mod auth;
mod download;
mod error;
mod library;
mod paths;
mod prereqs;
mod settings;

use download::JobState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(JobState::default())
        .setup(|app| {
            if let Ok(dir) = paths::app_data_dir(app.handle()) {
                let _ = std::fs::create_dir_all(&dir);
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            prereqs::check_prerequisites,
            prereqs::can_download,
            auth::pick_cookies_file,
            auth::import_cookies,
            download::check_cookies,
            download::engine_version,
            download::start_download,
            download::cancel_download,
            download::get_settings,
            download::save_settings,
            library::list_library,
            library::open_library_folder,
            library::pick_library_dir,
        ])
        .run(tauri::generate_context!())
        .expect("error while running CourDL");
}
