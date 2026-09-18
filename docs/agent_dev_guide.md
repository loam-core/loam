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
{"type": "init", "envelope": {...}, "args": [...], "capabilities": {...}, ...}
```

`capabilities` is a summarized, agent-readable view of this identity's
policy config — allowed tools, HTTP domains, filesystem paths, LLM models,
and subprocess commands/paths — so agent code can introspect what it's
allowed to do instead of discovering it by hitting a `policy_denied`
failure. It is not part of the hashed/signed `envelope` field itself. See
`PolicyEnforcer.capability_manifest()` in `runtime/id_runtime.py`, and
`agent.capabilities` / `ctx.capabilities` in §4/§5 below.

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

### 2.6 Continuity info

Agent → runtime:

```json
{"type": "continuity_info", "call_id": "..."}
```

Runtime → agent:

```json
{"type": "continuity_info_result", "call_id": "...", "result": {"fresh": false, "last_seq": 4, "last_state_hash": "...", "last_kind": "inscription"}, "error": null}
```

Read-only: reports the continuity log as of process start (`fresh: true`
means this identity has no continuity history yet). It does not reflect
this run's own record, which is only appended after the agent finishes.
Safe to call during simulation.


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

### Continuity

Agents can introspect continuity without shelling out to the CLI (`continuity_info`):

- returns: `fresh`, `last_seq`, `last_state_hash`, `last_kind`

Read-only — never appends a record, and works during simulation.

### Capabilities

Agents receive a summarized capability manifest at init time (see §2.1):

- `tools.allowed`, `http.allowed_domains`, `filesystem.allowed_paths`, `llm.allowed_models`, `subprocess.allowed_commands`/`allowed_paths`

Lets agent code check what it's allowed to do up front, instead of discovering it via `policy_denied` failures.

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
Continuity | `continuity_info` | Read-only continuity introspection
Capabilities | `init.capabilities` | Summarized policy manifest
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
- init handshake (including the `self.capabilities` policy manifest)
- JSON message I/O
- tool calls and tool_result routing
- think calls and think_result routing
- secret operations
- state read/write
- continuity introspection (`continuity_info()`)
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

The SDK provides a thin ergonomic layer on top of the ARI Agent class, exposed as `self.ctx` (a `loam.sdk.Context`). It does not change the protocol — it simply makes common operations easier to write by wrapping tool calls and cognition in small helper methods. `Context` is the single ergonomic surface for SDK agents: every ARI capability is reachable through it, so you never need to reach past `self.ctx` back into the underlying `loam.runtime.ari.Agent` methods.

`Context` wraps:
- LLM cognition (`llm`)
- human input (`input`)
- HTTP requests (`http`)
- filesystem operations (`read`, `write`, `delete`, `listdir`, `search`)
- process execution (`run`)
- secret operations (`secret.hmac`/`sign`/`encrypt`/`decrypt`/`use`)
- state read/write (`state_read`, `state_write`, `state_write_detailed`)
- continuity introspection (`continuity_info`)
- the capability manifest (`capabilities`)
- simulation (`simulate`)
- artifact emission (`emit`)
- finishing (`finish`)

This lets you write concise agent code without manually constructing JSON messages or calling `agent.tool(...)` directly. The SDK is optional — it adds ergonomics, not new capabilities.

Every `Context` method is a direct pass-through to the corresponding `Agent` method, so **it raises the same exceptions that method does** — see §7.1 for the one error-handling convention this SDK follows, documented there once rather than repeated per method.

Example:

```python
#!/usr/bin/env python3
from loam.sdk import Agent

class MyAgent(Agent):
    def main(self):
        # LLM cognition
        greeting = self.ctx.llm(
            "Say hello",
            backend="ollama",
            model="llama3.1:8b"
        )

        # SDK filesystem helpers (not available on the ARI class)
        self.ctx.write("scratch://hello.txt", greeting)
        stored = self.ctx.read("scratch://hello.txt")

        self.ctx.finish({
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

### 7.1 Error handling convention

`loam.runtime.ari.Agent` (and everything built on it, including `loam.sdk.Context`)
follows one rule: **operation-level failures raise, protocol-level failures exit.**

- **Protocol-level violations** — malformed JSON from the runtime, EOF mid-exchange,
  an out-of-sequence message — mean the wire contract itself is broken. There is
  nothing an agent could catch and recover from, so these terminate the process
  immediately (`_fatal()` → `sys.exit(1)`).
- **Operation-level failures** — a tool call came back with a non-zero exit code,
  a secret operation failed, a result was too large to inline and got redirected to
  a signed artifact — are ordinary, expected-to-happen conditions. Every typed
  convenience method (`fs_read`, `fs_write`, `fs_list`, `fs_delete`, `fs_search`,
  `http_request`, `state_read`, `secret_use`/`secret_hmac`/`secret_sign`/
  `secret_encrypt`/`secret_decrypt`, `artifact_emit`) raises an exception instead of
  silently returning `None`/`[]`/`False` or calling `sys.exit()`.

All of these exceptions live in `loam.runtime.ari` and share a common base:

- `LoamAgentError(RuntimeError)` — base class; catch this (or plain `RuntimeError`,
  for backward compatibility) to handle any operation-level failure generically.
  - `LoamToolError` — a tool call completed but reported failure. Has `.tool`.
  - `LoamArtifactRedirected` — the result was too large to inline and was written
    to a signed artifact instead. Has `.tool` and `.artifact` (the artifact path);
    fetch the real content with `fs_read(artifact_path)`.
  - `LoamSecretError` — a `secret_use` operation failed. Has `.name` and `.operation`.

```python
from loam.runtime.ari import LoamToolError, LoamArtifactRedirected

try:
    content = agent.fs_read("scratch://big_output.json")
except LoamArtifactRedirected as e:
    content = agent.fs_read(e.artifact)
except LoamToolError as e:
    agent.finish({"error": str(e)}, status="error")
```

Two methods are deliberate exceptions to the "raise" rule, and stay that way on
purpose:

- `process_run()` never raises on a non-zero exit code — the exit code of the
  command you ran is meaningful data for you to inspect, not a Loam-level failure
  (the same convention Python's own `subprocess.run()` follows by default).
- `state_write()` returns a plain `bool` and `state_write_detailed()` returns
  `{"ok": bool, "error": str | None}` instead of raising, because a chunked state
  write is a multi-step operation (`write_begin` → `write_chunk`* → `write_commit`/
  `write_abort`) where the caller usually wants to inspect the failure reason
  without a `try`/`except`, and may want to keep going after a failed write rather
  than unwind the whole call stack.

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

## 10. Embedding AgentRuntime in a Host App

Everything above is about writing the *agent* process. This section is for
the other side: a Python host app that wants to launch Loam agents
programmatically, without going through the `loam` CLI.

`loam run` (`loam/cli/run.py`) hand-assembles a runtime from a passphrase:
resolve the store id, build a `KeySourceContext`, derive a mechanism hash,
unlock the identity to get a signer, then construct `AgentRuntime`.
`AgentRuntime.open()` collapses that into one call:

```python
from loam.runtime.agent_runtime import AgentRuntime

runtime = AgentRuntime.open("my-identity", passphrase, workdir="/path/to/agent/dir")

status, result = runtime.run(agent_path="/path/to/agent.py", agent_args=[])

while status == "await_input":
    user_input = get_input_from_your_host_app(result["prompt"])
    status, result = runtime.resume(paused_state=result, user_input=user_input)
```

Notes:

- `AgentRuntime.open()` unlocks the identity as a side effect (it appends a
  continuity unlock record), the same as `loam run` does — don't call it
  repeatedly just to inspect state; construct one runtime and reuse it.
- Anything accepted by `AgentRuntime.__init__` (`force_python_driver`,
  `legacy_python`, etc.) can be passed through as extra keyword arguments.
- If you already have a `signer`/`ksctx` from elsewhere in your host app
  (e.g. you unlocked the identity for another reason), construct
  `AgentRuntime(...)` directly instead — `open()` is a convenience for the
  common case of "I just have a store id and a passphrase."
