#runtime/agent_runtime.py

import hashlib
import json
import os
import subprocess
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse

from loam.chronicle.emitter import sha256_bytes
from loam.continuity.hash import compute_file_hash
from loam.crypto.canonical import canonical_json
from loam.runtime.exec_runtime import hash_file
from loam.runtime.id_runtime import IdentityRuntime
from loam.runtime.driver.driver import LocalPythonDriver
from loam.runtime.driver.native_driver import NativeDriver
from loam.runtime.protocol import run_agent_loop
from loam.substrate.simulation_envelope import hash_envelope
from loam.backends.tools import REGISTRY as TOOL_REGISTRY

class SimpleResult:
    def __init__(self, returncode: int, stdout: str, stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr




ALLOWED_EXECUTABLES = None  
# None = dev mode (allow anything on PATH)
# []   = deny all
# ["ffmpeg", "convert"] = allow-list


class AgentRuntime(IdentityRuntime):
    """
        Agent execution runtime: owns subprocesses, tools, env, cwd.

        This is the real execution membrane (simulation_depth = 0). It launches the
        agent process and drives the JSON protocol (init → tool calls → finish).

        Driver selection:
        - If the environment variable LOAM_DRIVER is set, ExecRuntime uses the
            NativeDriver to run the agent as a real executable.
        - Otherwise, it falls back to the LocalPythonDriver, which hosts Python
            module‑based agents inside the Python runtime.

        The driver only controls *how the agent process is spawned*. All higher‑level
        substrate behavior (trust, identity, logs, tools, continuity) is identical
        regardless of driver.
        """
    def __init__(self, identity_path, workdir=None, force_python_driver=None, legacy_python=False, **kwargs):
        super().__init__(identity_path, **kwargs)

        self.workdir = workdir or os.getcwd()
        self.force_python_driver = force_python_driver
        self.legacy_python = legacy_python
        self.scratch_dir = None
        
        # Driver selection
        driver_lib = os.getenv("LOAM_DRIVER")
        if self.force_python_driver:
            # Explicit override from CLI
            self.driver = LocalPythonDriver()
        else:
            # Default: native driver
            lib_path = driver_lib or os.path.join(
                os.path.dirname(__file__),
                "driver",
                "libloam_driver.so",
            )
            self.driver = NativeDriver(lib_path=lib_path)

        # Operator-plane artifact storage (per store_id)
        self.artifacts_path = self.store_path / "artifacts"
        self.artifacts_path.mkdir(parents=True, exist_ok=True)
        
        self.llm_backend = None


    def run(self, agent_path, agent_args, simulation_input=None):
        # Create scratch dir at the start of the run
        self.scratch_dir = Path(tempfile.mkdtemp(prefix="loam-scratch-"))

        try:
            # Legacy Python: route to separate runtime
            if self.legacy_python:
                from .legacy_shim import LegacyPythonRuntime
                return LegacyPythonRuntime(self).run(agent_path, agent_args)

            # 1. Identity-plane authority
            self.initialize_authority()

            # 2. Envelope creation
            self.envelope = self.create_execution_envelope(simulation_depth=0)
            self.run_id = self.envelope["run_id"]
            self.envelope_hash = hash_envelope(self.envelope)

            # 3. Exec metadata
            self.exec_path = agent_path
            self.exec_basename = os.path.basename(agent_path)
            self.exec_code_hash = compute_file_hash(Path(agent_path))

            # 4. Chronicle start
            self.chronicle(
                "execution_start",
                {
                    "exec_path": self.exec_path,
                    "exec_basename": self.exec_basename,
                    "exec_code_hash": self.exec_code_hash,
                    "run_id": self.run_id,
                    "args": agent_args,
                    "cwd": self.workdir,
                    "envelope_hash": self.envelope_hash,
                },
            )

            # 5. Protocol loop
            status, result = run_agent_loop(self, agent_path, agent_args, simulation_input)

            # 6. Finalize continuity (REAL executions only)
            if not self.is_simulation():
                self.finalize_continuity()

            # 7. Chronicle finish
            logical = extract_logical_result(result)
            logical_hash = sha256_bytes(canonical_json(logical)) if logical else None

            self.chronicle(
                "execution_finished",
                {
                    "exec_path": agent_path,
                    "exec_path_resolved": str(Path(agent_path).resolve()),
                    "exec_basename": os.path.basename(agent_path),
                    "exec_code_hash": hash_file(agent_path),
                    "status": "ok",
                    "logical_result_hash": logical_hash,
                    "run_id": self.run_id,
                    "envelope_hash": self.envelope_hash,
                },
            )

            return status, result

        finally:
            # ALWAYS clean up scratch, even if the agent crashes
            shutil.rmtree(self.scratch_dir, ignore_errors=True)



    def is_simulation(self) -> bool:
        return False
    

    # ============================================================
    # Subprocesses
    # ============================================================

    def _execute_subprocess(self, target, stdin_data=None):
        # Normalize: always treat target as [script, arg1, arg2...]
        if isinstance(target, (list, tuple)):
            script = target[0]
            args = target[1:]
        else:
            script = target
            args = []

        # Resolve executable path
        exe = shutil.which(script)
        if exe is None:
            raise ValueError(f"Executable not found: {script}")

        # Allow‑list enforcement (dev mode = None)
        if ALLOWED_EXECUTABLES is not None:
            if script not in ALLOWED_EXECUTABLES:
                raise ValueError(f"Executable not allowed: {script}")

        # Build final command
        cmd = [exe] + args

        # Hardened environment
        env = {
            "PATH": "/usr/bin:/bin"
        }

        try:
            proc = subprocess.run(
                cmd,
                input=stdin_data,    
                capture_output=True,
                text=False,
                cwd=self.scratch_dir,   # sandbox directory
                env=env,                # scrub identity + secrets
                timeout=5               # prevent hangs
            )
        except subprocess.TimeoutExpired as e:
            return SimpleResult(
                returncode=124,
                stdout=b"",
                stderr=f"TimeoutExpired: {str(e)}".encode("utf-8")
            )

        # Output caps (1MB each)
        MAX_BYTES = 1_000_000
        stdout = proc.stdout[:MAX_BYTES]
        stderr = proc.stderr[:MAX_BYTES]

        return SimpleResult(
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )
 
    
    #=================================================================
    # Tool dispatcher
    #=================================================================
    def run_tool(self, tool_name, tool_args):
        self.assert_not_simulation()

        # Backwards‑compat shim
        params = tool_args or {}
        if isinstance(params, list) and len(params) == 1 and isinstance(params[0], dict):
            params = params[0]

        # Policy checks
        self.policy.allow_tool(tool_name)

        if tool_name == "http.request":
            url = params.get("url")
            if url:
                domain = urlparse(url).netloc
                self.policy.allow_http_domain(domain)

        if tool_name.startswith("fs."):
            path = params.get("path")
            if path is not None:
                self.policy.allow_fs_path(path)

        if tool_name == "process.run":
            cmd_arg = params.get("argv") or params.get("cmd")
            if cmd_arg is not None:
                # Resolve the executable path
                exe = shutil.which(cmd_arg[0])
                if exe is None:
                    raise RuntimeError(f"Executable not found: {cmd_arg[0]}")

                # Pass the resolved path to the membrane
                self.policy.allow_subprocess(exe)

        # Chronicle start
        self.chronicle("tool_start", {
            "tool": tool_name,
            **self.sanitize_meta(params)
        })

        # Execute backend tool
        try:
            backend_result = TOOL_REGISTRY[tool_name](self, params)
        except Exception as e:
            safe_meta = self.sanitize_meta({
                "error": str(e),
                "error_type": type(e).__name__,
            })
            self.chronicle("tool_error", {
                "tool": tool_name,
                **safe_meta
            })
            raise

        # Chronicle finish
        raw_meta = backend_result.get("meta", {})
        safe_meta = self.sanitize_meta(raw_meta)

        result = backend_result.get("result", {})

        if "error" in result:
            self.chronicle("tool_error", {
                "tool": tool_name,
                **safe_meta
            })
            return SimpleResult(
                returncode=1,
                stdout=json.dumps(result),
                stderr=""
            )

        self.chronicle("tool_finished", {
            "tool": tool_name,
            **safe_meta
        })

        return SimpleResult(
            returncode=0,
            stdout=json.dumps(result),
            stderr=""
        )

    #=================================================================
    #Log sanitizer
    #=================================================================

    def sanitize_meta(self, meta: dict) -> dict:
        """
        Dispatcher metadata firewall.
        Ensures Chronicle receives only safe, structural, non‑PII metadata.
        """

        if not isinstance(meta, dict):
            return {}

        # 1. Allowed keys (structural, non‑PII, non‑payload)
        SAFE_KEYS = {
            "tool",
            "tool_type",
            "path",
            "full_path",
            "bytes",
            "bytes_deleted",
            "entries",
            "status",
            "returncode",
            "response_bytes",
            "stdout_bytes",
            "stderr_bytes",
            "executable",
            "executable_hash",
            "file_hash",
            "file_hash_before",
            "file_hash_after",
            "content_hash",
            "url",
            "method",
            "artifact_path",
            "cmd",              # safe because emitter hashes it; dispatcher strips nested
            "url_hash",
            "path_hash",
            "params_hash",
            "cmd_hash",
            "canonical_hash",
        }

        # 2. Keys that are always unsafe (raw payloads)
        DROP_KEYS = {
            "body",
            "headers",
            "result",
            "stdout",
            "stderr",
            "response",
            "response_body",
            "response_headers",
        }

        # 3. Allowed value types
        SAFE_TYPES = (str, int, float, bool, type(None))

        safe = {}

        for key, value in meta.items():
            # Drop explicitly unsafe keys
            if key in DROP_KEYS:
                continue

            # Skip keys not in whitelist
            if key not in SAFE_KEYS:
                continue

            # Skip nested structures (lists, dicts)
            if isinstance(value, (dict, list)):
                continue

            # Skip unsafe types
            if not isinstance(value, SAFE_TYPES):
                continue

            # Skip large strings (>256 bytes)
            if isinstance(value, str) and len(value) > 256:
                continue

            # Skip obvious PII patterns
            if isinstance(value, str):
                lower = value.lower()

                if "@" in lower:  # email
                    continue
                if lower.startswith("pk_") or lower.startswith("sk_"):  # API keys
                    continue
                if "token" in lower or "secret" in lower or "password" in lower:
                    continue

            safe[key] = value

        return safe
    


    # ------------------------------------------------------------
    # Tool helpers
    # ------------------------------------------------------------
    def resolve_tool_path(self, name):
        system = shutil.which(name)
        if system:
            return system
        return name  # literal fallback

    def hash_tool_file(self, path):
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return None

    def _state_root(self):
        return self.state_dir


    def _sandbox_path(self, raw_path: str) -> Path:
        """
        Resolve a virtual or absolute path into a real filesystem path,
        enforcing capability boundaries defined in identity.toml.
        """
        # ------------------------------------------------------------
        # 1. Virtual namespace: prefix://rest
        # ------------------------------------------------------------
        if "://" in raw_path:
            prefix, rest = raw_path.split("://", 1)

            # 1a. User-defined mounts
            mounts = getattr(self.config.filesystem, "mounts", {}) or {}
            if prefix in mounts:
                root = Path(mounts[prefix])
                return (root / rest).resolve()

            # 1b. Built-in scratch
            if prefix == "scratch":
                return (self.scratch_dir / rest).resolve()

            # 1c. Built-in state
            if prefix == "state":
                state_root = self._state_root()
                if not state_root:
                    raise ValueError("state:// used but no state.path configured")
                return (state_root / rest).resolve()

            raise ValueError(f"Unknown virtual path prefix '{prefix}://'")
        # ------------------------------------------------------------
        # 2. Absolute paths: enforce allowed_paths prefix rules
        # ------------------------------------------------------------
        if raw_path.startswith("/"):
            allowed = getattr(self.config.filesystem, "allowed_paths", []) or []
            if not any(raw_path.startswith(p) for p in allowed if p.startswith("/")):
                raise ValueError(f"policy_denied: absolute path '{raw_path}' not allowed")
            return Path(raw_path).resolve()

        # ------------------------------------------------------------
        # 3. Relative paths: forbidden unless explicitly allowed
        # ------------------------------------------------------------
        raise ValueError(f"policy_denied: relative path '{raw_path}' not allowed")
 
    # ------------------------------------------------------------
    # Resume
    # ------------------------------------------------------------
    def resume(self, paused_state, user_input):
        proc = paused_state["proc"]

        # Send input to the SAME agent process
        self.driver.send_json(proc, {
            "type": "input",
            "call_id": paused_state["call_id"],
            "value": user_input,
        })

        # Continue protocol loop with existing proc
        return run_agent_loop(
            self,
            paused_state["agent_path"],
            paused_state["agent_args"],
            proc=proc,
            simulation_input=None,
            resume_input=None,
        )

def extract_logical_result(result: dict) -> dict:
    """
    Extracts only safe, structural, bounded fields from an agent result.
    """
    if not isinstance(result, dict):
        return {}

    safe = {}
    for k, v in result.items():
        # Only simple scalar fields
        if isinstance(v, (str, int, float, bool, type(None))):
            # Bound size
            if isinstance(v, str) and len(v) > 256:
                continue
            safe[k] = v

    return safe

    #TODO are these still needed?
    def run_python_agent(agent_id, job_path, args):
        print("Python agent mode not implemented yet.")
        return 1


    def run_legacy_command(agent_id, target, args):
        print("Legacy command mode not implemented yet.")
        return 1
