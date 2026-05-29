use std::io::{self, BufRead, Write};
use serde_json::Value;

fn main() {
    let stdin = io::stdin();
    let mut reader = stdin.lock();
    let mut stdout = io::stdout();

    // Read init
    let mut line = String::new();
    reader.read_line(&mut line).unwrap();
    let _init: Value = serde_json::from_str(&line).unwrap();

    // Send init ack
    writeln!(stdout, r#"{{"type":"init","status":"ok"}}"#).unwrap();
    stdout.flush().unwrap();

    // Immediately send finish
    let response = serde_json::json!({
        "type": "finish",
        "status": "ok",
        "result": { "note": "rust agent finished successfully" }
    });

    writeln!(stdout, "{}", response.to_string()).unwrap();
    stdout.flush().unwrap();
}
