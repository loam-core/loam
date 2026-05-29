# Loam

## What Loam Is
Loam is a substrate for sovereign identity and durable continuity that spans executions. It
gives any computational actor a cryptographically-rooted identity and an append-only continuity
chain so it can remain accountable across time and boundaries.

## Why Loam Exists
Modern computation has no concept of self. Processes don’t persist across time, tools don’t have identity, and agents can’t be accountable for their own actions. 
Loam provides the minimal primitives required for continuity — identity, epochs, and a local
policy membrane. Everything built on top of this layer inherits those guarantees. Loam does not
define a system; it defines the physics the system must obey.

## What Loam Provides

- Sovereign identity
- Durable continuity
- Identity epochs
- Chronicle — semantic execution logs
- Lineage
- Revocation
- Local policy enforcement
- Capability secrets
- Explicit boundaries
- Actor lifecycle primitives

These are the minimal building blocks required for any agent, process, or tool to maintain a
coherent identity across time.

## What Loam Is Not

Loam is not:

- A framework
- A platform
- A cloud
- A workflow engine

Loam defines the substrate — the layer beneath all of the above.

## Install & Quickstart

See the docs/quickstart.md for the full Quickstart. Short version:

```bash
git clone https://github.com/loam-core/loam
cd loam
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
Install the Native Driver (Required)
Choose one of the two paths below.

Option A — No Rust (recommended)
Download the prebuilt driver:

```bash
curl -LO https://github.com/loam-core/loam/releases/download/v0.1/libloam_driver.so
```
Move it into the driver directory:

```bash
mv libloam_driver.so loam/runtime/driver/
```

Option B — Build the Driver from Source (requires Rust)
```bash
cd loam/runtime/driver/native
cargo build --release --out-dir ..
cd ../../..
```
This produces:
loam/runtime/driver/libloam_driver.so

Initialize Loam:

```bash
loam ops init
loam identity issue --name myagent
```

Run a program:

```bash
loam exec myagent echo "hello"
```

Run an agent:

```bash
loam run myagent ./agent.py
```

## Architecture Overview

Loam defines a minimal identity-native substrate composed of:

- **Identity** — cryptographic root of self
- **Continuity** — append-only chain of epochs
- **Epoch** — a single execution boundary
- **Chronicle** — semantic execution record
- **Policy** — local capability governance
- **Secrets** — encrypted capability tokens
- **State** — deterministic identity-scoped memory
- **Runtimes** — subprocess and agent execution membranes

See docs/architecture.md for the full overview.

## Examples

See the `examples/` directory for:

- ARI agents
- SDK agents
- Rust native agents

Run any example with:

```bash
loam run <identity> examples/<path>/<agent>
```

## CLI Reference

Every command and flag is documented in docs/cli_reference.md.

## Contributing

See CONTRIBUTING.md for guidelines on issues, pull requests, and the development workflow.

## License

Loam is licensed under the Apache 2.0 License — see LICENSE for details.

## Status

Loam is early-stage: the substrate is stabilizing but details may evolve. Do not build
production systems on this version.