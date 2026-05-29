# Loam Agent Development Guide

How to write Loam-native agents in Python, Rust, or any language.

Loam agents are intentionally explicit. The substrate exposes identity, continuity, policy,
and boundaries directly. This makes early agent development feel lower-level than typical
frameworks. Higher-level ergonomic layers can be built on top of the stable substrate, but
they are intentionally out of scope for Loam.

Loam agents are processes that speak a simple JSON protocol over stdin/stdout. There is no
embedded runtime, no framework, and no magic.

If your program can:

- read a line of JSON
- write a line of JSON
- flush stdout

…then it can be a Loam agent. This guide explains how.

## 1. What a Loam Agent Is

A Loam agent is:

- a normal executable
- launched inside an identity epoch
- speaking JSON messages over stdin/stdout
- mediated by the Loam runtime
- governed by identity policy
- recorded in continuity and chronicle

Agents do not link against Loam (unless using the Python SDK). They do not run inside a VM
or container — they are plain processes.

## 2. The Loam Agent Protocol (ARI)

Every agent must speak the ARI protocol.

### 2.1 Init handshake

Runtime → agent (example):

```json
{"type": "init", "envelope": {...}, "args": [...], ...}
```

Agent → runtime (ack):

```json
{"type": "init", "status": "ok"}
```

### 2.2 Tool calls

Agent → runtime (call):

```json
{"type": "call_tool", "call_id": "...", "name": "http.request", "args": {...}}
```

Runtime → agent (result):

```json
{"type": "tool_result", "call_id": "...", "exit_code": 0, "stdout": "...", "artifact": "..."}
```

### 2.3 LLM cognition

Agent → runtime:

```json
{"type": "think", "input": "Say hello", "model": "...", "backend": "..."}
```

Runtime → agent:

```json
{"type": "think_result", "result": "..."}
```

### 2.4 Secrets

Agent → runtime:

```json
{"type": "secret_use", "call_id": "...", "name": "openai_api_key", "operation": "hmac", "payload": "..."}
```

Runtime → agent:

```json
{"type": "secret_used", "call_id": "...", "result": "..."}
```

### 2.5 Finish

Agent → runtime:

```json
{"type": "finish", "status": "ok", "result": {...}}
```

After `finish` the agent should exit.


## Available Tools & Capabilities

Loam agents run inside an identity-native execution membrane. Inside that membrane,
agents can call a set of substrate-mediated tools. These tools are explicit, deterministic,
logged in the chronicle, and governed by identity policy.

### LLM cognition

Agents can request model-level reasoning via the substrate using the `think` message.

- `input`: prompt text
- `backend`: ollama, openai, etc.
- `model`: model identifier
- returns: model output

This is a cognition request mediated by the runtime (not a regular tool call).

### HTTP

Agents can make outbound HTTP requests through the substrate (`http.request`):

- `method`
- `url`
- `headers`
- `body`
- returns: `exit_code`, `stdout`, `stderr`, `artifact`

### Subprocess execution

Agents can run local commands inside the sandbox (`process.run`):

- `argv`: command + args
- `stdin`: optional input
- `timeout`: optional timeout
- returns: `exit_code`, `stdout`, `stderr`, `artifact`

### Filesystem sandbox

Agents can interact with a sandboxed filesystem (`fs.*`):

- `fs.read` — read a file
- `fs.write` — write a file
- `fs.delete` — delete a file
- `fs.list` — list directory entries
- `fs.search` — search for files

All paths are sandboxed to the agent’s execution environment.

### Secrets

Agents can request secret operations without seeing secret material:

- `secret_use` operations: `hmac`, `sign`, `encrypt`, `decrypt`

Secrets never leave the substrate — agents only receive operation results.

### State (identity-scoped)

Agents can read/write deterministic state bound to the identity:

- `state.read`
- `state.write`

State persists across epochs and is hashed into continuity.

### Artifacts

Agents can emit signed artifacts from an epoch (`artifact.emit`):

- `path`: file to emit
- `description`: optional

Artifacts are durable, signed, and recorded in the chronicle.

### Simulation

Agents can request simulated executions (`simulate`):

- `input`: arbitrary payload
- returns: `simulation_result`

Useful for planning, dry-runs, or previews.

### Human input

Agents can request operator input (`await_input`):

- `prompt`: text shown to the operator
- returns: operator-provided value

This is the substrate’s human-in-the-loop primitive.

### Summary

Capability | Tool / Message | Description
---|---|---
LLM cognition | `think` | Substrate-mediated reasoning
HTTP | `http.request` | Make HTTP calls
Subprocess | `process.run` | Run commands
Filesystem | `fs.*` | Read/write/delete/list/search
Secrets | `secret_use` | HMAC, sign, encrypt, decrypt
State | `state.*` | Identity-scoped storage
Artifacts | `artifact.emit` | Emit signed artifacts
Simulation | `simulate` | Run simulated execution
Human input | `await_input` | Ask operator for input

## 3. Writing a Raw ARI Agent (bare protocol)

This is the canonical minimal agent. It shows the protocol loop with no SDK, no helpers,
and no magic.

```python
#!/usr/bin/env python3
import sys, json

def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

def main():
    # Receive init
    init = json.loads(sys.stdin.readline())
    send({"type": "init", "status": "ok"})

    # Ask runtime to think
    send({"type": "think", "input": "Say hello"})

    # Wait for think_result
    for line in sys.stdin:
        msg = json.loads(line)
        if msg["type"] == "think_result":
            send({
                "type": "finish",
                "status": "ok",
                "result": {"greeting": msg["result"]}
            })
            return

if __name__ == "__main__":
    main()
```

This is the pure substrate version.

## 4. Writing an ARI Shim Agent (Python)

Your `loam_agent.Agent` class wraps the protocol loop so you don’t have to.

Example: HTTP agent (shim)

```python
#!/usr/bin/env python3
from loam_agent import Agent
import json

def main():
    agent = Agent()

    url = agent.args[0] if agent.args else "https://example.com"

    resp = agent.tool("http.request", {
        "method": "GET",
        "url": url,
        "headers": {},
        "body": None,
    })

    body = resp["stdout"]
    try:
        parsed = json.loads(body) if body else None
    except:
        parsed = body

    agent.finish({
        "requested_url": url,
        "exit_code": resp["exit_code"],
        "body": parsed,
        "artifact": resp["artifact"],
    })

if __name__ == "__main__":
    main()
```

This is the Python ARI style.

## 5. Writing an SDK Agent (ergonomic Python)

The SDK adds helpers and nicer syntax but preserves the protocol.

```python
from loam.runtime.ari import Agent
from loam.sdk.ari_helpers import llm, finish, read, write, http, secret

class MyAgent(Agent):
    def main(self):
        greeting = llm(self, "Say hello", backend="ollama", model="llama3.1:8b")

        mac = secret(self).hmac("openai_api_key", b"hello world")

        write(self, "scratch://hello.txt", greeting)
        stored = read(self, "scratch://hello.txt")

        resp = http(self, "GET", "https://example.com")

        finish(self, {
            "greeting": greeting,
            "stored": stored,
            "http": resp,
        })
```

This is the ergonomic version.

## 6. Writing a Rust Agent

Your Rust agent is a minimal ARI example. Example (annotated):

```rust
use std::io::{self, BufRead, Write};
use serde_json::Value;

fn main() {
    let stdin = io::stdin();
    let mut reader = stdin.lock();
    let mut stdout = io::stdout();

    // 1. Read init
    let mut line = String::new();
    reader.read_line(&mut line).unwrap();
    let _init: Value = serde_json::from_str(&line).unwrap();

    // 2. Send init ack
    writeln!(stdout, r#"{{"type":"init","status":"ok"}}"#).unwrap();
    stdout.flush().unwrap();

    // 3. Immediately finish
    let response = serde_json::json!({
        "type": "finish",
        "status": "ok",
        "result": { "note": "rust agent finished successfully" }
    });

    writeln!(stdout, "{}", response.to_string()).unwrap();
    stdout.flush().unwrap();
}
```

This is the bare-metal ARI loop in Rust. It demonstrates that ARI is language-agnostic.

## 7. Tools, Secrets, State, Artifacts

Call tools with:

```json
{"type": "call_tool", "name": "...", "args": {...}}
```

Use secrets without seeing them:

```json
{"type": "secret_use", "name": "openai_api_key", "operation": "hmac", "payload": "..."}
```

Read/write identity-scoped state:

- `state.read`
- `state.write`

Emit files:

- `artifact.emit`

## 8. Testing Your Agent

Run it:

```bash
loam run <identity> ./agent.py
```

Inspect continuity:

```bash
loam logs show continuity <identity>
```

Inspect chronicle:

```bash
loam logs show chronicle <identity>
```

Debug mode:

```bash
loam run --debug <identity> ./agent.py
```

## 9. Best Practices

- Always flush stdout
- Always send newline-terminated JSON
- Always handle unexpected messages
- Keep agents deterministic
- Use state intentionally
- Emit artifacts only when meaningful
- Fail fast and clearly
