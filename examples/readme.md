These examples demonstrate how to build agents using Loam’s substrate, the ARI protocol, and the Loam SDK.
ARI agents can be written in any language — Python, Rust, or anything that can speak JSON over stdin/stdout.

Running examples
Install Loam in editable mode from the repo root:

Code
pip install -e .
Run any Python or native ARI agent with:

Code
loam run examples/<path>/<agent>
Rust agents must be built first (see below).

Example Index
ARI examples
Located in examples/ari/.

ARI agents use the low‑level ARI runtime and speak JSON envelopes over stdin/stdout.
They demonstrate how to interact directly with substrate tools.

ari_agent.py
Shows:

HTTP tool (http.request)

scratch filesystem (fs.write, fs.read)

argument handling (agent.args)

structured finish() output

Run:

Code
loam run examples/ari/ari_agent.py
Note: Some domains (like example.com) may be blocked by your identity policy.
Update [http].allowed_domains in your identity TOML to allow them.

SDK examples
Located in examples/sdk/.

SDK agents use the high‑level SDK helper layer for convenience.

myagent.py
Shows:

LLM calls (llm())

reading/writing state

finishing with structured results

Run:

Code
loam run examples/sdk/myagent.py
Rust examples
Located in examples/rust/echo_agent/.

Rust agents are native ARI agents.
They follow the same protocol as Python ARI agents — they just need to be compiled first.

echo_agent
Shows:

init → ack → loop → finish flow

parsing ARI envelopes with serde

emitting tool results

emitting a final finish envelope

Build the agent
Code
cd examples/rust/echo_agent
cargo build --release

This produces:

Code
target/release/echo_agent
Run through Loam
Code
loam run <identity> examples/rust/echo_agent/target/release/echo_agent

Notes
ARI agents can be written in any language as long as they speak the protocol.

Python ARI agents run directly; native agents (Rust, Go, etc.) run after being built.

Some examples require updating your identity policy to allow specific domains or tools.

All examples are intentionally small and focused — copy, modify, extend.