import os
from pathlib import Path
import importlib.util


class LegacyPythonRuntime:
    """
    Identity-anchored runtime for legacy Python module agents.
    Uses IdentityRuntime for:
      - identity-plane authority
      - execution envelope
      - chronicle
      - continuity (finalize_continuity)
      - state hashing
      - secret access
    """

    def __init__(self, agent_runtime):
        # agent_runtime is an AgentRuntime, which inherits IdentityRuntime
        self._rt = agent_runtime

    def run(self, agent_path, agent_args):
        # 1. Identity-plane authority
        self._rt.initialize_authority()

        # 2. Envelope creation (depth 0)
        envelope = self._rt.create_execution_envelope(simulation_depth=0)
        run_id = envelope["run_id"]

        # 3. Exec metadata
        exec_path = agent_path
        exec_basename = os.path.basename(agent_path)

        # 4. Chronicle start
        self._rt.chronicle(
            "execution_start",
            {
                "exec_path": exec_path,
                "exec_basename": exec_basename,
                "run_id": run_id,
            },
        )

        # 5. Execute module
        status, result = self._execute_module(exec_path)

        # 6. Continuity (identity-plane)
        #    This computes:
        #      - identity fingerprint hash
        #      - optional state hash
        #      - continuity record append
        self._rt.finalize_continuity()

        # 7. Chronicle finish
        self._rt.chronicle(
            "execution_finished",
            {
                "exec_path": exec_path,
                "exec_basename": exec_basename,
                "run_id": run_id,
                "status": status,
            },
        )

        return status, result

    def _execute_module(self, agent_path):
        path = Path(agent_path)
        spec = importlib.util.spec_from_file_location(path.stem, str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Resolve entrypoint
        if hasattr(module, "agent") and callable(module.agent):
            entry = module.agent
        elif hasattr(module, "main") and callable(module.main):
            entry = module.main
        else:
            raise RuntimeError("Legacy agent must define agent() or main()")

        shim = LegacyShim(self._rt)

        try:
            result = entry(shim)
        except Exception as e:
            self._rt.chronicle(
                "legacy_agent_error",
                {
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return "error", {"error": str(e)}

        if result is None:
            return "ok", {}
        if isinstance(result, dict):
            return "ok", result
        return "ok", {"result": result}



class LegacyShim:
    """
    Minimal compatibility shim for old Python module agents.
    Delegates to IdentityRuntime for:
      - tools
      - secrets
      - state
      - chronicle
    """

    def __init__(self, runtime):
        self._rt = runtime

    # Tools
    def run(self, cmd):
        return self._rt.run_tool(cmd)

    # Secrets (use identity-plane API)
    def secret(self, name: str):
        return self._rt.get_secret(name)

    # State directory
    @property
    def state(self):
        return self._rt.state_dir

    # Chronicle
    def chronicle(self, event, payload=None):
        return self._rt.chronicle(event, payload or {})

    # Optional: simulation passthrough
    def simulate(self, prompt):
        return self._rt.simulate(prompt)

    # Identity-ish helpers
    @property
    def agent_id(self):
        return getattr(self._rt, "agent_id", None)

    @property
    def workdir(self):
        return getattr(self._rt, "workdir", None)
