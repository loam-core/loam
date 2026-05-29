use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, ChildStderr, Command, Stdio};

pub struct Handle {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    stderr: BufReader<ChildStderr>,
}

impl Handle {
    pub fn start(exec: String, args_json: String, env_json: String, cwd: String) -> *mut Handle {
        let args: Vec<String> = serde_json::from_str(&args_json).unwrap();
        let env: serde_json::Value = serde_json::from_str(&env_json).unwrap();

        let mut cmd = Command::new(exec);
        cmd.args(args);
        cmd.current_dir(cwd);
        cmd.stdin(Stdio::piped());
        cmd.stdout(Stdio::piped());
        cmd.stderr(Stdio::piped()); // ← was Stdio::null()

        if let serde_json::Value::Object(map) = env {
            for (k, v) in map {
                cmd.env(k, v.as_str().unwrap_or(""));
            }
        }

        let mut child = cmd.spawn().expect("failed to spawn agent");

        let stdin = child.stdin.take().unwrap();
        let stdout = BufReader::new(child.stdout.take().unwrap());
        let stderr = BufReader::new(child.stderr.take().unwrap());

        Box::into_raw(Box::new(Handle { child, stdin, stdout, stderr }))
    }

    pub unsafe fn send_json(&mut self, msg: String) {
        let _ = writeln!(self.stdin, "{}", msg);
        let _ = self.stdin.flush();
    }

    pub unsafe fn read_json(&mut self) -> Option<String> {
        let mut line = String::new();
        match self.stdout.read_line(&mut line) {
            Ok(0) => None,
            Ok(_) => Some(line.trim().to_string()),
            Err(_) => None,
        }
    }

    pub unsafe fn read_stderr(&mut self) -> Option<String> {
        let mut line = String::new();
        match self.stderr.read_line(&mut line) {
            Ok(0) => None,
            Ok(_) => Some(line),
            Err(_) => None,
        }
    }

    pub unsafe fn terminate(&mut self) {
        let _ = self.child.kill();
    }

    pub unsafe fn wait(&mut self, _timeout_ms: u64) -> i32 {
        match self.child.try_wait() {
            Ok(Some(status)) => status.code().unwrap_or(-1),
            Ok(None) => -1, // still running
            Err(_) => -1,
        }
    }
}
