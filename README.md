# Loam

## What Loam Is

Loam is an execution substrate that gives any computational actor a stable, cryptographically‑verifiable self.
It provides identity and continuity that persist across runs, processes, machines, and time.

Loam does not define how agents think, act, or communicate.
It defines the physics those systems run on: identity, epochs, continuity, lineage, and local policy boundaries.

Anything built on top of Loam inherits these guarantees.

## Why Loam Exists

Modern computation has no concept of self.
Processes start and die. Tools run without identity. Agents cannot prove who they are or what they’ve done.

Loam introduces the minimal primitives required for durable, accountable computation:

- a sovereign identity
- an append‑only continuity chain
- verifiable execution epochs
- a semantic chronicle
- a local capability membrane

These are the foundations needed for long‑lived agents, verifiable tools, and accountable automation.

## What Loam Provides

Loam exposes a small, explicit set of substrate‑level primitives:

- Sovereign identity — cryptographic root of self
- Continuity — append‑only chain of execution epochs
- Chronicle — semantic execution record
- Lineage — ancestry and derivation tracking
- Revocation — substrate‑level invalidation
- Local policy — capability boundaries and enforcement
- Secrets — encrypted capability envelopes
- State integrity — identity‑scoped integrity and continuity for developer‑managed state
- Runtimes — subprocess and agent execution membranes

These are the minimal building blocks required for any agent, process, or tool to maintain a coherent identity across time.

## What Loam Is Not

Loam is not:

- a framework
- a platform
- a cloud
- a workflow engine
- an agent model

Loam defines the substrate beneath all of those.

## Substrate vs. Agent Model
Loam defines the substrate protocol that agents must speak in order to run with identity, continuity, and accountability.
It does not define how agents think, plan, remember, or behave.

The [Loam Agent Development Guide](docs/agent_dev_guide.md) teaches how to write a process that runs inside the Loam substrate and speaks its protocol.

It does not prescribe a cognitive architecture or agent model.

Any reasoning loop, planning system, or tool‑use strategy can run on Loam as long as it respects the substrate boundary.

## Install & Quickstart

See the [Getting Started Guide](docs/getting_started.md) for the full introduction to Loam. 

### Short version:

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
mv libloam_driver.so src/loam/runtime/driver/
```

Option B — Build the Driver from Source (requires Rust)
```bash
cd src/loam/runtime/driver/native

cargo build --release
```
This produces:
loam/runtime/driver/libloam_driver.so

Move it to the driver folder.

```bash
mv target/release/libloam_driver.so ..
cd ~/loam
```

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
loam run myagent examples/ari/ari_agent.py
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

See the [Architecture document](docs/architecture.md) for the full overview.

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

Every command and flag is documented in the [CLI Reference](docs/cli_reference.md).

## Contributing

See [CONTRIBUTING](CONTRIBUTING.md) for guidelines on issues, pull requests, and the development workflow.

## License

Loam is licensed under the Apache 2.0 License — see LICENSE for details.

## Status

Loam is early-stage: the substrate is stabilizing but details may evolve. Do not build
production systems on this version.
