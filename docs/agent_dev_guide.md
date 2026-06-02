# Loam Agent Development Guide

How to write Loam‑native agents in Python, Rust, or any language.

Loam agents are intentionally explicit. The substrate exposes identity, continuity, policy, and boundaries directly. This makes early agent development feel lower‑level than typical frameworks, but it also gives you a stable, language‑agnostic foundation to build on.

At the core, a Loam agent is just a process that speaks a small JSON protocol over stdin/stdout. There is no embedded runtime, no VM, and no framework magic. 

If your program can:

- read a line of JSON
- write a line of JSON
- flush stdout

…then it can be a Loam agent.

Loam provides three layers for writing agents, all built on the same substrate boundary:

- the raw ARI protocol (the wire format)
- the ARI Agent class (the Python implementation of that protocol)
- the SDK (ergonomic helpers built on top of the ARI Agent class)

Most developers will use the SDK, but all three layers matter because they define the substrate boundary.

## 1. What a Loam Agent Is

A Loam agent is:

- a normal executable
- launched inside an identity epoch
- speaking JSON messages over stdin/stdout
- mediated by the Loam runtime
- governed by identity policy
- recorded in continuity and chronicle

Agents do not link against Loam. Python agents may import the SDK, but they still run as normal processes. They do not run inside a VM or container — they are plain processes.

## 2. The Loam Agent Protocol (ARI)

The ARI protocol defines the JSON messages exchanged between the runtime and the agent. Every agent, regardless of language or SDK, ultimately speaks this protocol.

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


# Writing Loam Agents
>[!NOTE]
> **Which layer should I use?**
>- If you’re writing Python agents, start with the [SDK](#5-writing-an-sdk-agent-ergonomic-python).
>- If you’re integrating Loam into another Python framework, use the [ARI Agent class](#4-writing-a-python-agent-using-the-ari-agent-class).
>- If you’re building a Loam SDK or runtime in another language, use the [raw ARI](#3-writing-a-raw-ari-protocol-agent) protocol.

## 3. Writing a Raw ARI Protocol Agent

This example speaks the ARI protocol directly over stdin/stdout with no helper classes. It is the lowest‑level way to write a Loam agent and shows exactly how the runtime and agent exchange JSON messages.

A raw ARI agent handles:
- init handshake
- sending think requests
- receiving think_result
- calling tools manually
- routing tool_result messages
- sending the final finish message

Everything is done by writing JSON lines to stdout and reading JSON lines from stdin.

```python
#!/usr/bin/env python3
import sys, json

def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

def main():
    # 1. Receive init
    init_line = sys.stdin.readline()
    init_msg = json.loads(init_line)
    send({"type": "init", "status": "ok"})

    # 2. Ask the runtime to think
    send({
        "type": "think",
        "input": "Say hello",
        "backend": "ollama",
        "model": "llama3.1:8b"
    })

    greeting = None

    # 3. Wait for think_result
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("type") == "think_result":
            greeting = msg.get("result")
            break

    # 4. Write greeting to scratch
    send({
        "type": "call_tool",
        "call_id": "write1",
        "name": "fs.write",
        "args": [{"path": "scratch://hello.txt", "content": greeting}],
    })

    # 5. Wait for fs.write result
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("type") == "tool_result" and msg.get("call_id") == "write1":
            break

    # 6. Read it back
    send({
        "type": "call_tool",
        "call_id": "read1",
        "name": "fs.read",
        "args": [{"path": "scratch://hello.txt"}],
    })

    reread = None
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("type") == "tool_result" and msg.get("call_id") == "read1":
            reread = json.loads(msg["stdout"]).get("content")
            break

    # 7. Finish
    send({
        "type": "finish",
        "status": "ok",
        "result": {
            "greeting": greeting,
            "stored": reread,
        }
    })

if __name__ == "__main__":
    main()
```

This is the pure substrate version.

## 4. Writing a Python Agent Using the ARI Agent Class

Loam provides a Python implementation of the ARI protocol in loam.runtime.ari.Agent. This class implements the entire protocol loop for you — the init handshake, reading and writing JSON messages, waiting for tool and think results, handling secret and state operations, emitting artifacts, running simulations, and sending the final finish message. You only implement your agent’s main() method.

The ARI Agent class handles:
- init handshake
- JSON message I/O
- tool calls and tool_result routing
- think calls and think_result routing
- secret operations
- state read/write
- artifact emission
- simulation requests
- finish messages

### Example:

```python
#!/usr/bin/env python3
from loam.runtime.ari import Agent
import json

class HelloAgent(Agent):
    def main(self):
        # 1. LLM cognition
        greeting = self.llm_think(
            "Say hello",
            backend="ollama",
            model="llama3.1:8b"
        )

        # 2. Write to scratch
        self.fs_write("scratch://hello.txt", greeting)

        # 3. Read it back
        reread_raw = self.fs_read("scratch://hello.txt")
        reread = reread_raw if isinstance(reread_raw, str) else None

        # 4. Finish
        self.finish({
            "greeting": greeting,
            "stored": reread,
        })

if __name__ == "__main__":
    HelloAgent().main()

```

This is the Python ARI style.

## 5. Writing an SDK Agent (ergonomic Python)

The SDK provides a thin ergonomic layer on top of the ARI Agent class. It does not change the protocol — it simply makes common operations easier to write by wrapping tool calls and cognition in small helper functions.

SDK helpers wrap:
- LLM cognition (llm)
- HTTP requests (http)
- filesystem operations (read, write)
- secret operations (secret)
- finishing (finish)

This lets you write concise agent code without manually constructing JSON messages or calling `agent.tool(...)` directly. The SDK is optional — it adds ergonomics, not new capabilities.

Example:

```python
#!/usr/bin/env python3
from loam.runtime.ari import Agent
from loam.sdk.ari_helpers import llm, finish, write, read

class MyAgent(Agent):
    def main(self):
        # LLM cognition
        greeting = llm(
            self,
            "Say hello",
            backend="ollama",
            model="llama3.1:8b"
        )

        # SDK filesystem helpers (not available on the ARI class)
        write(self, "scratch://hello.txt", greeting)
        stored = read(self, "scratch://hello.txt")

        finish(self, {
            "greeting": greeting,
            "stored": stored,
        })

if __name__ == "__main__":
    MyAgent().main()
```

This is the ergonomic version.

## 6. Writing a Rust Agent

This example uses the raw ARI protocol directly, just like Section 3, but implemented in Rust. It demonstrates that ARI is language-agnostic.

Example:

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
