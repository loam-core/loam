# Loam Quickstart

A minimal, mechanical “get running in 5 minutes” guide.

## 1. Clone the Repository

```bash
git clone https://github.com/loam-core/loam
cd loam
```

## 2. Create and Activate a Virtual Environment

Loam installs its CLI into the active Python environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Loam (Editable Mode)

```bash
pip install -e .
```

This installs:

- the `loam` CLI
- all runtime dependencies
- an editable link to the source tree

The CLI now lives at:

```bash
./.venv/bin/loam
```

## 3.1 Build the Native Driver (Required)

Loam uses a native Rust runtime (`libloam_driver.so`). Build it once after cloning:

```bash
cd src/loam/runtime/driver/native
cargo build --release --out-dir ..
```

This produces:

```bash
src/loam/runtime/driver/libloam_driver.so
```

Loam automatically loads this file at runtime.

## 4. Verify the CLI

```bash
loam --help
```

You should see a usage summary including:

```text
usage: loam [-h] [--debug] {identity,logs,secret,state,ops,run,exec} …
```

## 5. Initialize the Loam Store

```bash
loam ops init
```

This creates:

```text
~/.loam/
    stores/        # identity stores
    backends/      # backend configs
    tools/         # tool configs
```

## 6. Issue an Identity

```bash
loam identity issue --name "<optional human name>"

```

This creates a new sovereign identity under:

```text
~/.loam/stores/<identity-uuid>/
```

Inspect them:
```bash
loam identity list
loam identity show <identity>
loam identity verify <identity>
```

## 7. Identity Store Layout

A typical identity contains:

```text
identity.toml        # identity policy + config
keys/                # encrypted private key + public key
continuity/          # append-only epoch chain
chronicle/           # semantic execution log
dossier/             # immutable identity metadata
lineage/             # origin + ancestry
secrets/             # encrypted capability secrets
artifacts/           # files produced by agents
metadata.json        # identity metadata
```

An identity is a sovereign cryptographic persona, not an execution environment. Execution
happens inside epochs opened by the substrate when you call `loam exec` or `loam run`.

## 8. Edit Identity Policy (`identity.toml`)

Every identity has a policy file at:

```text
~/.loam/stores/<uuid>/identity.toml
```

This file controls:

- allowed tools
- allowed subprocess commands
- allowed filesystem paths
- allowed HTTP domains
- allowed LLM models
- mount points
- approval rules

It does not define:

- agent entrypoints
- default LLM providers
- backend configuration

Those belong in agent code and backend config, not policy.

### 8.1 Minimal Example

```toml
[http]
allowed_domains = [
  "api.github.com",
  "pypi.org",
  "files.pythonhosted.org",
  "*",
]

[llm]
allowed_models = ["None"]
```

If policy does not allow a backend or model, you will see errors like:

```text
Unknown LLM provider: ollama
```

### 8.2 Full Policy Block Explanations

#### `[tools]`

Controls which substrate tools the identity may call.

Examples:

- `fs.*` — virtual filesystem
- `http.request` — outbound HTTP
- `process.run` — subprocess execution
- `state.*` — identity state hashing
- `artifact.emit` — artifact creation

If a tool is not listed, the identity cannot use it.

#### `[subprocess]`

Controls what commands the identity may execute.

- `allowed_commands` — whitelisted binaries
- `allowed_paths` — directories where binaries may reside

Prevents arbitrary code execution.

#### `[filesystem]`

Controls which virtual paths the identity may access.

Examples:

- `scratch://` — ephemeral workspace
- `state://` — identity state
- `output://` — user-defined mount

If a path is not allowed, the tool call fails.

#### `[filesystem.mounts]`

Maps virtual paths to real host paths.

Example:

```toml
[filesystem.mounts]
output = "/home/user/documents/agent_output"
```

This exposes `output://` to the agent.

#### `[http]`

Controls which domains the identity may reach.

Example:

```toml
allowed_domains = ["api.github.com", "*"]
```
`*.github.com` works as well.
`*` is allowed but not recommended.

#### `[llm]`

Controls which model names the identity may request.
This does not configure backends — it only defines what is allowed.

Example:

```toml
allowed_models = ["gpt-4.1-mini", "llama3.1:8b"]
```

If an agent requests a model not listed here, the substrate rejects it.

#### `[approvals]`

Reserved for future interactive approval hooks. Currently unused.

## 9. Configure LLM Backends

Loam Core ships with backend implementations, but they require user-specific configuration.
Backend configs live under:

```text
~/.loam/backends/
```

### 9.1 Ollama Backend (local models)

Create:

```text
~/.loam/backends/ollama.toml
```

Example:

```toml
provider = "ollama"
api_url = "http://localhost:11434"
default_model = "llama3.1:8b"
```

Update identity policy:

```toml
[llm]
allowed_models = ["llama3.1:8b"]
```

If missing or misconfigured:

```text
Unknown LLM provider: ollama
```

### 9.2 OpenAI Backend

Requires a secret:

```bash
loam secret create <identity> openai_api_key --value <your-key>
```

Update identity policy:

```toml
[llm]
allowed_models = ["gpt-4.1-mini"]
```

### 9.3 GitHub Copilot Backend

Requires a GitHub token:

```bash
loam secret create <identity> github_token --value <your-token>
```

Update identity policy:

```toml
[llm]
allowed_models = ["gpt-4o-copilot"]
```

## 10. Run a Program as an Identity (`exec`)

Loam Core wraps any subprocess in an identity epoch.

```bash
loam exec <identity> echo "hello from loam"
```

This:

- prompts for the identity’s passphrase
- opens a new epoch
- executes the command
- records chronicle
- closes the epoch

Run a script:

```bash
loam exec <identity> ./examples/hello.py
```

## 11. Run a Loam-Native Agent (`run`)

`loam run` is for agents that speak the Loam protocol.

```bash
loam run <identity> ./myagent.py --passphrase <passphrase>
```

This:

- launches the agent runtime
- sends init
- receives protocol messages (`think`, `tool`, etc.)
- handles LLM/tool calls
- records chronicle
- closes the epoch

If the backend is unsupported or disallowed:

```text
unexpected error: Unknown LLM provider: ollama
```

> Note: The HTTP and `myagent.py` examples use `example.com`, which is not allowed by default policy.
>
> To run it, add `example.com` (or `*` to allow all domains) to `[http].allowed_domains` in your identity TOML.

## 12. Inspect Continuity and Chronicle Logs

```bash
loam logs interlaced <identity>
loam logs show continuity <identity>
loam logs show chronicle <identity>
```

These correspond to:

```text
continuity/continuity.log
chronicle/chronicle.log
```

## 13. Manage Secrets

```bash
loam secret create <identity> <name> --value <value>
loam secret list <identity>
loam secret delete <identity> <name>
```

Secrets are encrypted per identity and require policy permission.

## 14. Manage State Hashing

```bash
loam state show <identity>
loam state enable <identity> --path <absolute path>
```

State hashing allows deterministic state tracking for agents.
