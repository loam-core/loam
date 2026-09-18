# Comprehensive Example Agent (Overview & Key Concepts)

This document explains the behavior, architecture, and developer‑relevant mechanics of the Comprehensive Example Agent.

This agent is intentionally designed to exercise the entire Loam ARI lifecycle:

- HTTP tools
- LLM cognition
- Simulation mode
- Human‑in‑the‑loop approval
- Multi‑process continuation
- Identity‑scoped state
- Scratch filesystem
- Artifact emission

If you understand this example, you understand how to build real Loam agents.

## 1. What This Agent Does (High‑Level Flow)

This agent performs a complete multi‑phase workflow:

- Fetch content from https://example.com using the http.request tool.
- Summarize the content using the LLM backend.
- Simulate storing that summary in the agent’s identity state.
- Ask the LLM to evaluate the simulated action.
- Pause for human approval using await_input.
- This is a checkpoint: the agent process exits.
- A new process resumes after the operator responds.
- If approved, write the summary to identity state.
- Write the summary to scratch (in the resumed process).
- Emit an artifact from that scratch file.
- Finish with a structured result.

This is the canonical pattern for approval‑gated, stateful, resumable Loam agents.

## 2. Key Concepts Developers Must Understand

### 2.1 await_input is a Checkpoint Boundary

When the agent calls:

```python
input_prompt("...")
```
Loam:
- sends the prompt to the operator
- terminates the agent process
- waits for human input
- spawns a new process to resume execution

This has two critical implications:
- Scratch is per‑process and does not survive across input.
- State is persistent and does survive across input.

**If you write to scratch before input, the file will not exist after resume.**

Correct pattern:

```ptyhon
# after human input
write("scratch://file.txt", data)
emit("scratch://file.txt")
``` 
### 2.2 Scratch Is Ephemeral
Allowed prefix:

```python
scratch://
```

Mapped to a temporary directory like:

`/tmp/loam-scratch-XXXXXX/`

Scratch:
- is created at process start
- is destroyed when the process exits
- does not persist across await_input

Use scratch only for temporary files created after human approval.

### 2.3 State Is Persistent and Identity‑Scoped

Allowed prefix:

`state://`

Mapped to:

`~/.loam/state/<identity>/` (or wherever you set your state path to with `loam state enable` or `loam state set-path`)

State:
- persists across runs
- persists across checkpoints
- is isolated per identity
- is safe to write before or after input
- is hashed if `loam state enable` is used, meaning it can only be changed during a run

This is where long‑term agent memory lives.

### 2.4 Simulation Mode Forks a Child Agent

Calling:

```python
simulate(payload)
```
causes Loam to:
- spawn a child agent
- run it in simulation mode
- return its result
- avoid modifying state or scratch

This allows agents to preview actions before committing them.

### 2.5 Artifact Emission Reads from the Sandbox

`artifact.emit("scratch://summary.txt")` works because:

fs.write and artifact.emit both resolve paths through the sandbox

the backend copies the file into:

`stores/<identity>/artifacts/<timestamp>-file.bin`
`stores/<identity>/artifacts/<timestamp>-file.artifact.json`

Artifacts are immutable, signed, and stored permanently.

## 3. Required Pre‑Steps Before Running This Agent

### 3.1 Enable State for the Identity

`loam identity set-state-path <identity> --path ~/.loam/state/compagent`

### 3.2 Allow the HTTP Domain

In `identity.toml`:

```toml
[http]
allowed_domains = ["example.com"]
```

### 3.3 Ensure Required Tools Are Allowed

In `identity.toml`:

```toml
[tools]
allowed = [
    "fs.read",
    "fs.write",
    "fs.delete",
    "fs.list",
    "fs.search",
    "http.request",
    "process.run",
    "state.read",
    "state.write",
    "artifact.emit",
]
```

### 3.4 Ensure the LLM Model Is Allowed
In identity.toml:

```toml
[llm]
allowed_models = ["llama3.1:8b"]
```

## 4. Developer Takeaways

This example demonstrates:

How ARI agents run across multiple processes

How to safely use scratch and state

How to build approval‑gated workflows

How to simulate actions before committing them

How to produce artifacts

How to structure multi‑phase agents

This is the recommended pattern for any real‑world Loam agent that:

- interacts with external systems
- requires human approval
- maintains state
- produces artifacts
- must be resumable

5. Full Example Code

```python
#!/usr/bin/env python3
import sys
from loam.sdk import Agent


class SummaryAgent(Agent):
    def run(self):
        # Simulation branch
        if self.simulation_input is not None:
            return self.simulation_mode()

        # Real execution
        return self.real_mode()

    # -------------------------
    # REAL EXECUTION
    # -------------------------
    def real_mode(self):
        ctx = self.ctx

        BACKEND = "ollama"
        MODEL = "llama3.1:8b"
        SOURCE_URL = "https://example.com"

        # 1. Fetch some data via HTTP
        http_result = ctx.http("GET", SOURCE_URL)
        http_body = http_result.get("stdout") or ""

        # 2. Ask the LLM to summarize it
        summary = ctx.llm(
            f"Summarize the following content for the operator:\n\n{http_body}",
            backend=BACKEND,
            model=MODEL,
        )

        # 3. Simulate committing this summary to state
        simulation_input = {
            "action": "store_summary",
            "state_key": "last_summary",
            "summary_preview": summary,
        }
        sim_result = ctx.simulate(simulation_input)
        print("SIM RESULT:", sim_result, file=sys.stderr)

        # 4. Ask the LLM to evaluate the simulated result
        eval_text = ctx.llm(
            "You are reviewing a simulated agent action.\n\n"
            f"Simulation result:\n{sim_result}\n\n"
            "Question: Is it reasonable to store this summary as the new 'last_summary'?",
            backend=BACKEND,
            model=MODEL,
        )

        # 5. Ask the human to confirm (this is the checkpoint boundary)
        human_answer = ctx.input(
            "Store this summary as the new last_summary? (yes/no)\n\n"
            f"LLM evaluation:\n{eval_text}\n\n"
            f"Summary:\n{summary}\n\n"
            "Your decision: "
        )
        should_commit = str(human_answer).strip().lower().startswith("y")

        committed = False
        state_error = None

        # 6. If approved, write to state
        if should_commit:
            try:
                ctx.state_write("last_summary", summary)
                committed = True
            except Exception as e:
                state_error = str(e)

        # 7. Now (in the resumed process) write summary to scratch and emit artifact
        scratch_path = "scratch://summary.txt"
        ctx.write(scratch_path, summary)

        try:
            ctx.emit(scratch_path, description="HTTP summary for this identity")
        except Exception as e:
            print("Artifact emit failed:", e, file=sys.stderr)

        # 8. Finish with a structured result
        ctx.finish(
            {
                "source_url": SOURCE_URL,
                "summary": summary,
                "simulation_result": sim_result,
                "llm_evaluation": eval_text,
                "human_decision": human_answer,
                "committed_to_state": committed,
                "state_error": state_error,
                "scratch_path": scratch_path,
            }
        )

    # -------------------------
    # SIMULATION EXECUTION
    # -------------------------
    def simulation_mode(self):
        ctx = self.ctx
        payload = self.simulation_input

        result = ctx.llm(
            "Simulate evaluating this agent action:\n\n"
            f"{payload}\n\n"
            "Return a short JSON-friendly assessment.",
            backend="ollama",
            model="llama3.1:8b",
        )

        ctx.finish({"simulated_evaluation": result})


if __name__ == "__main__":
    SummaryAgent().run()
```
