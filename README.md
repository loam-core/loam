Loam Core
Loam Core is a substrate for sovereign identity and durable continuity that spans executions.
It gives any computational actor a cryptographically‑rooted identity and an append‑only continuity chain so it can remain accountable across time and boundaries.

Modern computation has no concept of self. Processes don’t persist across time, tools don’t have identity, and agents can’t be accountable for their own actions. Loam provides the minimal primitives required for continuity: identity, epochs, and a local policy membrane. Everything built above this layer inherits these guarantees. Loam does not define the system — it defines the physics the system must obey.

What Loam Provides
Sovereign identity

Durable continuity

Identity epochs

Chronicle — semantic execution logs

Lineage

Revocation

Local policy enforcement

Capability secrets

Explicit boundaries

Actor lifecycle primitives

These are the minimal building blocks required for any agent, process, or tool to maintain a coherent identity across time.

What Loam Is Not
Loam is not:

a framework

a platform

a cloud

a workflow engine

Loam defines the substrate — the layer beneath all of those.

Install & Quickstart
See the full Quickstart.

Short version:

Code
git clone https://github.com/loam/loam-core
cd loam-core
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
Initialize Loam:

Code
loam ops init
loam identity issue --name myagent
Run a program:

Code
loam exec myagent echo "hello"
Run an agent:

Code
loam run myagent ./agent.py
Architecture Overview
Loam defines a minimal identity‑native substrate:

Identity — cryptographic root of self

Continuity — append‑only chain of epochs

Epoch — a single execution boundary

Chronicle — semantic execution record

Policy — local capability governance

Secrets — encrypted capability tokens

State — deterministic identity‑scoped memory

Runtimes — subprocess + agent execution membranes

Full overview: Architecture Overview

Examples
See examples/ for:

ARI agents

SDK agents

Rust native agents

Run any example:

Code
loam run examples/<path>/<agent>
CLI Reference
Every command, every flag:
CLI Reference

Contributing
See CONTRIBUTING.md for guidelines on issues, pull requests, and development workflow.

License
Loam Core is licensed under the Apache 2.0 License.
See LICENSE for details.

Status
Loam is early.
The substrate is stabilizing, but details may evolve.
Do not build production systems on this version.