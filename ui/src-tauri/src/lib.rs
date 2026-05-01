use serde::{Deserialize, Serialize};
use std::process::Stdio;
use tauri::{AppHandle, Emitter, Manager};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct OutputLine {
    pub stream: String, // "stdout" | "stderr"
    pub line: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CommandResult {
    pub exit_code: i32,
    pub stdout: String,
    pub stderr: String,
}

/// Resolve the helixsh executable: prefer a bundled sidecar .pyz,
/// fall back to `helixsh` on $PATH, then `python -m helixsh`.
fn helixsh_exe() -> (String, Vec<String>) {
    // Check for bundled sidecar next to the binary
    if let Ok(exe) = std::env::current_exe() {
        let sidecar = exe.parent().unwrap_or(std::path::Path::new(".")).join("helixsh.pyz");
        if sidecar.exists() {
            return ("python3".to_string(), vec![sidecar.display().to_string()]);
        }
    }
    // Fall back to helixsh on PATH
    if which_helixsh().is_some() {
        return ("helixsh".to_string(), vec![]);
    }
    // Last resort: python -m helixsh
    ("python3".to_string(), vec!["-m".to_string(), "helixsh".to_string()])
}

fn which_helixsh() -> Option<String> {
    std::env::var("PATH").ok().and_then(|path| {
        path.split(':').find_map(|dir| {
            let candidate = std::path::Path::new(dir).join("helixsh");
            if candidate.exists() {
                Some(candidate.display().to_string())
            } else {
                None
            }
        })
    })
}

/// Run a helixsh command, streaming output lines as Tauri events.
/// Each line is emitted as `helixsh://output` with an `OutputLine` payload.
/// Final exit code is emitted as `helixsh://done`.
#[tauri::command]
pub async fn run_helixsh(
    app: AppHandle,
    invocation_id: String,
    args: Vec<String>,
) -> Result<(), String> {
    let (exe, mut prefix_args) = helixsh_exe();
    prefix_args.extend(args);

    let mut child = Command::new(&exe)
        .args(&prefix_args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn helixsh: {e}"))?;

    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();

    let app_stdout = app.clone();
    let id_stdout = invocation_id.clone();
    let stdout_task = tokio::spawn(async move {
        let mut reader = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            let _ = app_stdout.emit(
                "helixsh://output",
                serde_json::json!({
                    "invocationId": id_stdout,
                    "stream": "stdout",
                    "line": line
                }),
            );
        }
    });

    let app_stderr = app.clone();
    let id_stderr = invocation_id.clone();
    let stderr_task = tokio::spawn(async move {
        let mut reader = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            let _ = app_stderr.emit(
                "helixsh://output",
                serde_json::json!({
                    "invocationId": id_stderr,
                    "stream": "stderr",
                    "line": line
                }),
            );
        }
    });

    let _ = tokio::join!(stdout_task, stderr_task);
    let status = child.wait().await.map_err(|e| e.to_string())?;
    let code = status.code().unwrap_or(-1);

    let _ = app.emit(
        "helixsh://done",
        serde_json::json!({ "invocationId": invocation_id, "exitCode": code }),
    );

    Ok(())
}

/// Run a helixsh command synchronously and return captured output.
/// Used for lightweight queries (doctor, nf-list, pipeline-list).
#[tauri::command]
pub async fn query_helixsh(args: Vec<String>) -> Result<CommandResult, String> {
    let (exe, mut prefix_args) = helixsh_exe();
    prefix_args.extend(args);

    let output = Command::new(&exe)
        .args(&prefix_args)
        .output()
        .await
        .map_err(|e| format!("Failed to run helixsh: {e}"))?;

    Ok(CommandResult {
        exit_code: output.status.code().unwrap_or(-1),
        stdout: String::from_utf8_lossy(&output.stdout).to_string(),
        stderr: String::from_utf8_lossy(&output.stderr).to_string(),
    })
}

/// Return the resolved helixsh executable path for display in the UI.
#[tauri::command]
pub fn get_helixsh_path() -> String {
    let (exe, args) = helixsh_exe();
    if args.is_empty() {
        exe
    } else {
        format!("{} {}", exe, args.join(" "))
    }
}

/// Window drag support for the custom titlebar.
#[tauri::command]
pub async fn start_drag(window: tauri::Window) -> Result<(), String> {
    window.start_dragging().map_err(|e| e.to_string())
}

/// Minimise / maximise / close forwarded from the custom titlebar.
#[tauri::command]
pub async fn window_action(window: tauri::Window, action: String) -> Result<(), String> {
    match action.as_str() {
        "minimize" => window.minimize().map_err(|e| e.to_string()),
        "maximize" => {
            if window.is_maximized().unwrap_or(false) {
                window.unmaximize().map_err(|e| e.to_string())
            } else {
                window.maximize().map_err(|e| e.to_string())
            }
        }
        "close" => window.close().map_err(|e| e.to_string()),
        _ => Err(format!("Unknown action: {action}")),
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            run_helixsh,
            query_helixsh,
            get_helixsh_path,
            start_drag,
            window_action,
        ])
        .run(tauri::generate_context!())
        .expect("error running helixsh UI");
}
