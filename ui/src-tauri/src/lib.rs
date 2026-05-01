use serde::Serialize;
use std::process::Stdio;
use tauri::ipc::Channel;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

/// Streamed event sent through a Channel back to the JS frontend.
#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase", tag = "event", content = "data")]
pub enum HelixEvent {
    Output { stream: String, line: String },
    Done { exit_code: i32 },
}

#[derive(Clone, Serialize)]
pub struct CommandResult {
    pub exit_code: i32,
    pub stdout: String,
    pub stderr: String,
}

fn helixsh_exe() -> (String, Vec<String>) {
    if let Ok(exe) = std::env::current_exe() {
        let sidecar = exe.parent().unwrap_or(std::path::Path::new(".")).join("helixsh.pyz");
        if sidecar.exists() {
            return (python_exe(), vec![sidecar.display().to_string()]);
        }
    }
    if which_helixsh().is_some() {
        let bin = if cfg!(windows) { "helixsh.exe" } else { "helixsh" };
        return (bin.to_string(), vec![]);
    }
    (python_exe(), vec!["-m".to_string(), "helixsh".to_string()])
}

fn python_exe() -> String {
    if cfg!(windows) { "python".to_string() } else { "python3".to_string() }
}

fn which_helixsh() -> Option<String> {
    let bin = if cfg!(windows) { "helixsh.exe" } else { "helixsh" };
    std::env::var_os("PATH").and_then(|path| {
        std::env::split_paths(&path).find_map(|dir| {
            let candidate = dir.join(bin);
            if candidate.exists() { Some(candidate.display().to_string()) } else { None }
        })
    })
}

/// Stream a helixsh command's stdout/stderr back to the frontend via a Channel.
/// The frontend creates a Channel and passes it; each line is a HelixEvent::Output;
/// completion is HelixEvent::Done with the exit code.
#[tauri::command]
pub async fn run_helixsh(
    on_event: Channel<HelixEvent>,
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

    let ch_out = on_event.clone();
    let stdout_task = tokio::spawn(async move {
        let mut lines = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let _ = ch_out.send(&HelixEvent::Output { stream: "stdout".into(), line });
        }
    });

    let ch_err = on_event.clone();
    let stderr_task = tokio::spawn(async move {
        let mut lines = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let _ = ch_err.send(&HelixEvent::Output { stream: "stderr".into(), line });
        }
    });

    let _ = tokio::join!(stdout_task, stderr_task);
    let status = child.wait().await.map_err(|e| e.to_string())?;
    let code = status.code().unwrap_or(-1);
    let _ = on_event.send(&HelixEvent::Done { exit_code: code });
    Ok(())
}

/// Run a helixsh command to completion and return captured output.
/// Used for lightweight sidebar queries (doctor, nf-list).
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

#[tauri::command]
pub fn get_helixsh_path() -> String {
    let (exe, args) = helixsh_exe();
    if args.is_empty() { exe } else { format!("{} {}", exe, args.join(" ")) }
}

/// Window control actions forwarded from the custom titlebar.
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
        .invoke_handler(tauri::generate_handler![
            run_helixsh,
            query_helixsh,
            get_helixsh_path,
            window_action,
        ])
        .run(tauri::generate_context!())
        .expect("error running helixsh UI");
}
