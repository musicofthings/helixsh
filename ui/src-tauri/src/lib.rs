mod commands;

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::run_helixsh,
            commands::query_helixsh,
            commands::get_helixsh_path,
            commands::window_action,
        ])
        .run(tauri::generate_context!())
        .expect("error running helixsh UI");
}
