Loam Core Agent Development Guide

How to write Loam‑native agents in Python, Rust, or any language.

Loam agents are intentionally explicit. The substrate exposes identity, continuity, policy, and boundaries directly. This makes early agent development feel lower‑level than typical frameworks. Higher‑level ergonomic layers can now be built on top of the stable substrate, but they are intentionally out of scope for Loam Core.

Loam agents are just processes that speak a simple JSON protocol over stdin/stdout. There is no embedded runtime, no framework, no magic.

If your program can:
    • read a line of JSON
    • write a line of JSON
    • flush stdout
…it can be a Loam agent.
This guide teaches you how.

1. What a Loam Agent Is
A Loam agent is:
    • a normal executable
    • launched inside an identity epoch
    • speaking JSON messages over stdin/stdout
    • mediated by the Loam runtime
    • governed by identity policy
    • recorded in continuity + chronicle
Agents do not link against Loam. Agents do not import Loam libraries (unless using the Python SDK). Agents do not run inside a VM or container.
Agents are just processes.

2. The Loam Agent Protocol (ARI)
Every agent must speak the ARI protocol.

2.1 Init handshake
Runtime → agent:
json
{"type": "init", "envelope": {...}, "args": [...], ...}
Agent → runtime:
json
{"type": "init", "status": "ok"}

2.2 Tool calls
Agent → runtime:
json
{"type": "call_tool", "call_id": "...", "name": "http.request", "args": {...}}
Runtime → agent:
json
{"type": "tool_result", "call_id": "...", "exit_code": 0, "stdout": "...", "artifact": "..."}

2.3 LLM cognition
Agent → runtime:
json
{"type": "think", "input": "Say hello", "model": "...", "backend": "..."}
Runtime → agent:
json
{"type": "think_result", "result": "..."}

2.4 Secrets
Agent → runtime:
json
{"type": "secret_use", "call_id": "...", "name": "openai_api_key", "operation": "hmac", "payload": "..."}
Runtime → agent:
json
{"type": "secret_used", "call_id": "...", "result": "..."}

2.5 Finish
Agent → runtime:
json
{"type": "finish", "status": "ok", "result": {...}}
After finish, the agent exits.


Available Tools & Capabilities

Loam agents run inside an identity‑native execution membrane. Inside that membrane, agents can call a set of substrate‑mediated tools. These tools are explicit, deterministic, logged in the chronicle, and governed by identity policy.
This section lists everything an agent can do in Loam Core v0.1.

LLM Cognition
Agents can request model‑level reasoning via the substrate.
    • think
        ◦ input: prompt text
        ◦ backend: ollama, openai, etc
        ◦ model: model identifier
        ◦ returns: model output
This is not a tool call — it’s a cognition request mediated by the runtime.

HTTP
Agents can make outbound HTTP requests through the substrate.
    • http.request
        ◦ method
        ◦ url
        ◦ headers
        ◦ body
        ◦ returns: exit code, stdout, stderr, artifact
Used for API calls, fetching data, webhooks, etc.

Subprocess Execution
Agents can run local commands inside the sandbox.
    • process.run
        ◦ argv: command + args
        ◦ stdin: optional input
        ◦ timeout: optional timeout
        ◦ returns: exit code, stdout, stderr, artifact
Useful for CLI tools, converters, compilers, etc.

Filesystem Sandbox
Agents can interact with a sandboxed filesystem.
    • fs.read — read a file
    • fs.write — write a file
    • fs.delete — delete a file
    • fs.list — list directory entries
    • fs.search — search for files
All paths are sandboxed to the agent’s execution environment.

Secrets
Agents can use secrets without ever seeing them.
    • secret_use
        ◦ hmac
        ◦ sign
        ◦ encrypt
        ◦ decrypt

Secrets never leave the substrate. Agents only receive the result of the operation.

State (Identity‑Scoped)
Agents can read/write deterministic state bound to the identity, not the execution.
    • state.read
    • state.write
State persists across epochs and is hashed into continuity.

Artifacts
Agents can emit signed artifacts from an epoch.
    • artifact.emit
        ◦ path: file to emit
        ◦ description: optional
Artifacts are durable, signed, and recorded in the chronicle.

Simulation
Agents can request a simulated execution.
    • simulate
        ◦ input: arbitrary payload
        ◦ returns: simulation_result
Useful for planning, dry‑runs, or previewing behavior.

Human Input
Agents can request operator input during execution.
    • await_input
        ◦ prompt: text shown to the operator
        ◦ returns: operator‑provided value
This is the substrate’s human‑in‑the‑loop primitive.

Summary Table
Capability	Tool / Message	Description
LLM cognition	think	Substrate‑mediated reasoning
HTTP	http.request	Make HTTP calls
Subprocess	process.run	Run commands
Filesystem	fs.*	Read/write/delete/list/search
Secrets	secret_use	HMAC, sign, encrypt, decrypt
State	state.*	Identity‑scoped storage
Artifacts	artifact.emit	Emit signed artifacts
Simulation	simulate	Run simulated execution
Human input	await_input	Ask operator for input

3. Writing a Raw ARI Agent (bare protocol)
This is the canonical minimal agent. It shows the protocol loop with no SDK, no helpers, no magic.
python
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

This is the pure substrate version.

4. Writing an ARI Shim Agent (Python)
Your loam_agent.Agent class wraps the protocol loop so you don’t have to.
Example: HTTP agent
python
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

This is the Python ARI style.

5. Writing an SDK Agent (ergonomic Python)
The SDK adds:
    • ctx
    • helper functions
    • nicer syntax
It does not change the protocol.
Example: SDK agent
python
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

This is the ergonomic version.

6. Writing a Rust Agent

Your Rust agent is a perfect minimal ARI example.
Here it is again, annotated:
rust
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
This is the bare‑metal ARI loop in Rust.
It proves:
    • Rust agents work
    • ARI is language‑agnostic
    • The protocol is simple

7. Tools, Secrets, State, Artifacts

Tools
Call tools with:
json
{"type": "call_tool", "name": "...", "args": {...}}

Secrets
Use secrets without ever seeing them:
json
{"type": "secret_use", "name": "openai_api_key", "operation": "hmac", "payload": "..."}

State
Read/write identity‑scoped state:
    • state.read
    • state.write
Artifacts

Emit files:
    • artifact.emit

8. Testing Your Agent
Run it
Code
loam run <identity> ./agent.py
Inspect continuity
Code
loam logs show continuity <identity>
Inspect chronicle
Code
loam logs show chronicle <identity>
Debug mode
Code
loam run --debug <identity> ./agent.py

9. Best Practices
    • Always flush stdout
    • Always send newline‑terminated JSON
    • Always handle unexpected messages
    • Keep agents deterministic
    • Use state intentionally
    • Emit artifacts only when meaningful
    • Fail fast and clearly
