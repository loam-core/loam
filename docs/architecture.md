# Loam Architecture Overview

A one-page conceptual map of the identity-native substrate.

Loam defines the physics of identity, continuity, policy, secrets, state, and execution. It
does not define agent behavior — it defines the environment in which agents can exist.

## Identity

The cryptographic root of self. An identity is:

- a private key
- a public key
- a dossier
- a lineage
- a policy
- a secrets store
- a continuity chain

Identity is sovereign and immutable except through continuity. Identity is the actor, not the
execution environment.

## Continuity

The durable, append-only chain of identity epochs.

Continuity provides:

- temporal ordering
- tamper-evidence
- verifiable history
- durable provenance

Continuity is the structure of identity over time.

## Epoch

A single execution boundary.

An epoch begins when you call:

```bash
loam exec <identity> ...
loam run <identity> ...
```

An epoch:

- loads identity
- loads policy
- decrypts secrets
- executes a program or agent
- records chronicle
- appends to continuity

Epochs are the units of life for an identity.

## Chronicle

The semantic execution record of an epoch.

Chronicle captures:

- tool calls
- subprocess calls
- HTTP requests
- LLM invocations
- secret access
- state transitions
- artifact emissions
- policy evaluations

Chronicle is the content of an epoch. Continuity is the structure of epochs.

## Lineage

The origin and ancestry of an identity.

Lineage provides:

- where the identity came from
- how it was derived
- how it was forked or cloned
- immutable ancestry proofs

Lineage is non-forgeable and cryptographically anchored.

## Policy

Local governance for an identity.

Policy defines:

- allowed tools
- allowed subprocess commands
- allowed filesystem paths
- allowed HTTP domains
- allowed LLM models
- mount points
- approval rules

Policy is enforced before and during execution. Policy is capability governance, not configuration.

## Secrets

Encrypted, identity-scoped capabilities.

Secrets are:

- encrypted at rest
- decrypted only inside an epoch
- governed by policy
- accessible only through the substrate

Secrets give identities capabilities, not knowledge.

## State

Deterministic, identity-scoped memory.

State provides:

- reproducible memory
- deterministic hashing
- identity-local persistence

State enables long-term agent memory.

## Artifacts

Files produced by an identity.

Artifacts are:

- binary or structured outputs
- stored under the identity
- referenced in chronicle
- part of the identity’s durable history

Artifacts are the externalized work of an identity.

## Runtime Layer

The execution membranes that connect identity physics to actual execution.

Loam provides three execution membranes:

### 1. IdentityRuntime (identity membrane)

Inherited by all runtimes.

Provides:

- identity loading
- key decryption
- continuity initialization
- chronicle initialization
- policy enforcement
- secret mediation
- state hashing
- artifact plumbing

IdentityRuntime is the identity physics layer.

### 2. Subprocess Runtime

Used by:

```bash
loam exec <identity> <command>
```

Responsibilities:

- open epoch
- wrap subprocess
- enforce policy
- mediate tools
- mediate secrets
- record chronicle
- close epoch

Executes programs, not agents.

### 3. Agent Runtime

Used by:

```bash
loam run <identity> ./agent.py
```

Responsibilities:

- launch agent process
- speak the Loam Agent Protocol
- send init
- receive think
- route LLM/tool calls
- enforce policy
- mediate secrets
- record chronicle
- close epoch

Executes agents, not programs.

## Protocol Loop (agent execution membrane)

The agent-side execution boundary.

Responsibilities:

- send init
- receive think
- handle tool calls
- handle LLM calls
- enforce protocol structure
- mediate agent ↔ runtime communication

The Protocol Loop is the agent physics layer, not a runtime.

## Backends

Execution providers for tools and LLMs.

Backends provide:

- LLM inference
- HTTP requests
- filesystem access
- subprocess execution
- state hashing
- artifact emission

Backends are configured globally, but governed per-identity by policy.

## Actor Lifecycle

Actors (programs or agents) are:

- executed as an identity
- bounded by an epoch
- governed by policy
- mediated by a runtime
- recorded in chronicle
- appended to continuity
- optionally revoked

The substrate ensures:

- identity integrity
- continuity integrity
- policy enforcement
- deterministic state
- governed capability use

## Architecture Diagram (Text Version)

```text
+-----------------------------+
|         Loam                |
|  (identity-native substrate)|
+-----------------------------+
            |
            v
+-----------------------------+
|         Identity            |
| (keys, dossier, lineage)    |
+-----------------------------+
            |
            v
+-----------------------------+
|         Continuity          |
|   (append-only epoch chain) |
+-----------------------------+
            |
            v
+-----------------------------+
|           Epoch             |
| (single execution boundary) |
+-----------------------------+
            |
            v
+-----------------------------+
|        Runtime Layer        |
|  (Exec / Agent / Identity)  |
+-----------------------------+
            |
            v
+-----------------------------+
|       Protocol Loop         |
|   (agent-side membrane)     |
+-----------------------------+
            |
            v
+-----------------------------+
|           Actor             |
| (program or agent process)  |
+-----------------------------+
            |
            v
+-----------------------------+
|         Chronicle           |
| (semantic execution record) |
+-----------------------------+
```
