use serde::Serialize;
use std::process::{Command, Stdio};

#[derive(Serialize)]
pub struct ToolResult {
    pub exit_code: i32,
    pub stdout: String,
    pub stderr: String,
}

impl ToolResult {
    pub fn run(path: String, args_json: String, env_json: String, cwd: String) -> ToolResult {
        let args: Vec<String> = serde_json::from_str(&args_json).unwrap();
        let env: serde_json::Value = serde_json::from_str(&env_json).unwrap();

        let mut cmd = Command::new(path);
        cmd.args(args);
        cmd.current_dir(cwd);
        cmd.stdin(Stdio::null());
        cmd.stdout(Stdio::piped());
        cmd.stderr(Stdio::piped());

        if let serde_json::Value::Object(map) = env {
            for (k, v) in map {
                cmd.env(k, v.as_str().unwrap_or(""));
            }
        }

        let output = cmd.output().expect("failed to run tool");

        ToolResult {
            exit_code: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
        }
    }
}
