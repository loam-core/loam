#!/usr/bin/env python3
import sys
import json
import uuid
import base64
from typing import Any, Dict, Optional

# Below MAX_PAYLOAD_BYTES (8192, enforced in runtime/protocol.py) with margin
# for JSON-escaping overhead and worst-case non-ASCII expansion.
STATE_WRITE_SINGLE_SHOT_LIMIT = 7168   # below this: one plain state.write call
STATE_WRITE_CHUNK_SAFETY_CAP = 6144    # hard ceiling every write_chunk message must clear
STATE_WRITE_CHUNK_CHAR_ESTIMATE = 900  # initial chunk length guess, in characters


# ============================================================
# Error convention
# ============================================================
# Two tiers of failure exist in this file, and they are handled differently
# on purpose:
#
#   - Protocol-level violations (malformed JSON, EOF mid-exchange, an
#     unexpected message type while correlating a call_id) mean the wire
#     contract itself is broken. Nothing built on top of it can be trusted,
#     so these still go through _fatal() -> sys.exit(1). There is nothing an
#     agent could catch and recover from here.
#
#   - Operation-level failures (a tool call came back with a non-zero
#     exit_code, a secret operation failed, a result was too large to inline
#     and got redirected to a signed artifact) are ordinary, expected-to-happen
#     conditions. Every typed convenience method below raises a
#     LoamAgentError subclass for these instead of silently returning
#     None/[]/False or calling sys.exit(). LoamAgentError subclasses
#     RuntimeError so existing `except Exception`/`except RuntimeError`
#     agent code keeps working unchanged.
#
# `tool()` itself is the exception: it is the raw ARI primitive and always
# returns the raw result dict regardless of exit_code, exactly like the wire
# protocol does. `process_run()` is also a pass-through for the same reason
# process_run's own subprocess.run() is: a non-zero exit code from the
# command you ran is meaningful data, not a Loam-level failure.

class LoamAgentError(RuntimeError):
    """Base class for catchable, operation-level Loam agent errors."""


class LoamToolError(LoamAgentError):
    """A tool call completed but reported failure (non-zero exit_code)."""

    def __init__(self, tool: str, message: str):
        super().__init__(f"{tool} failed: {message}")
        self.tool = tool


class LoamArtifactRedirected(LoamAgentError):
    """
    Raised by the typed read helpers (fs_read, fs_list, fs_search,
    http_request, state_read) when the result was too large to inline and
    the runtime redirected it to a signed artifact instead (see
    runtime/protocol.py::maybe_artifact). The actual content is not in this
    exception — fetch it from `.artifact` via fs.read on the artifact path.
    """

    def __init__(self, tool: str, artifact_path: str):
        super().__init__(
            f"{tool} result exceeded the inline size limit; "
            f"content was redirected to artifact {artifact_path!r}"
        )
        self.tool = tool
        self.artifact = artifact_path


class LoamSecretError(LoamAgentError):
    """A secret_use operation (hmac/sign/encrypt/decrypt) failed."""

    def __init__(self, name: str, operation: str, message: str):
        super().__init__(f"secret_use({name!r}, {operation!r}) failed: {message}")
        self.name = name
        self.operation = operation


class Agent:
    def __init__(self):
        # ---- Init handshake with runtime ----
        init_msg = self._read_json()
        if init_msg is None or init_msg.get("type") != "init":
            self._fatal("Expected init message from runtime")

        self.envelope = init_msg.get("envelope")
        self.envelope_hash = init_msg.get("envelope_hash")
        self.args = init_msg.get("args", [])
        self.simulation_input = init_msg.get("simulation_input")
        # Summarized policy view (tools/http/filesystem/llm/subprocess allow-lists);
        # see PolicyEnforcer.capability_manifest() in runtime/id_runtime.py.
        self.capabilities: Optional[Dict[str, Any]] = init_msg.get("capabilities")

        self._send_json({"type": "init", "status": "ok"})

    # ============================================================
    # Core protocol
    # ============================================================

    def tool(self, name: str, args: Any) -> Dict[str, Any]:
        """Call a substrate tool and return its raw result fields."""
        call_id = str(uuid.uuid4())

        self._send_json({
            "type": "call_tool",
            "call_id": call_id,
            "name": name,
            "args": args if isinstance(args, list) else [args],
        })

        while True:
            msg = self._read_json()
            if msg is None:
                self._fatal("EOF while waiting for tool_result")

            if msg.get("type") == "tool_result" and msg.get("call_id") == call_id:
                return {
                    "exit_code": msg.get("exit_code"),
                    "stdout": msg.get("stdout"),
                    "stderr": msg.get("stderr"),
                    "artifact": msg.get("artifact"),
                }

            self._fatal(f"Unexpected message while waiting for tool_result: {msg!r}")

    def _unwrap_tool_result(self, tool_name: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Shared success/failure handling for the typed convenience wrappers
        (fs_read, fs_list, fs_search, http_request, state_read).

        Raises LoamToolError if the tool call failed, LoamArtifactRedirected
        if the result was too large to inline and got redirected to an
        artifact, or returns the parsed JSON stdout payload on success.
        """
        if result["exit_code"] != 0:
            raise LoamToolError(tool_name, result.get("stderr") or "tool call failed")

        if result["stdout"] is None:
            if result["artifact"]:
                raise LoamArtifactRedirected(tool_name, result["artifact"])
            return None

        try:
            return json.loads(result["stdout"])
        except Exception as e:
            raise LoamToolError(tool_name, f"malformed tool response: {e}") from e

    # ============================================================
    # LLM
    # ============================================================

    def llm_think(self, input: str, backend=None, model=None, tags=None) -> str:
        """Send a cognition request (not a tool call) to the runtime.

        Returns the model's text output (never None; empty string on
        backend-side failure, since cognition_llm_think() already
        chronicles the error and returns "").
        """
        self._send_json({
            "type": "think",
            "backend": backend,
            "input": input,
            "model": model,
            "tags": tags or {},
        })

        while True:
            msg = self._read_json()
            if msg is None:
                self._fatal("EOF while waiting for think_result")

            if msg.get("type") == "think_result":
                return msg.get("result")

            self._fatal(f"Unexpected message while waiting for think_result: {msg!r}")

    # ============================================================
    # Wait/Input
    # ============================================================

    def input(self, prompt: str) -> str:
        call_id = str(uuid.uuid4())
        self._send_json({
            "type": "await_input",
            "call_id": call_id,
            "prompt": prompt,
        })
        while True:
            msg = self._read_json()
            if msg is None:
                self._fatal("EOF while waiting for input")

            if msg.get("type") == "input" and msg.get("call_id") == call_id:
                return msg["value"]

            self._fatal(f"Unexpected message while waiting for input: {msg!r}")


    # ============================================================
    # Secrets
    # ============================================================

    def secret_use(self, name: str, operation: str, payload: bytes) -> Any:
        """Request a secret operation without exposing the secret.

        Return type depends on `operation`: "hmac"/"sign"/"encrypt" return a
        base64-encoded str, "decrypt" returns raw bytes — prefer the typed
        secret_hmac/secret_sign/secret_encrypt/secret_decrypt wrappers below,
        which encode this in their own type hints.

        Raises LoamSecretError if the runtime reports a failure. This used
        to call sys.exit(1) on failure, which agent code could not catch;
        it now raises like every other operation-level failure in this
        class (see the module-level "Error convention" note above).
        """
        call_id = str(uuid.uuid4())

        self._send_json({
            "type": "secret_use",
            "call_id": call_id,
            "name": name,
            "operation": operation,
            "payload": base64.b64encode(payload).decode("ascii"),
        })

        while True:
            msg = self._read_json()
            if msg is None:
                self._fatal("EOF while waiting for secret_used")

            if msg.get("type") == "secret_used" and msg.get("call_id") == call_id:
                if msg.get("error"):
                    raise LoamSecretError(name, operation, msg["error"])
                return msg.get("result")

            self._fatal(f"Unexpected message while waiting for secret_used: {msg!r}")

    def secret_hmac(self, name: str, payload: bytes) -> str:
        """Compute HMAC using a named secret. Returns a base64-encoded str."""
        return self.secret_use(name, "hmac", payload)

    def secret_sign(self, name: str, payload: bytes) -> str:
        """Sign payload using a named secret key. Returns a base64-encoded str."""
        return self.secret_use(name, "sign", payload)

    def secret_encrypt(self, name: str, plaintext: bytes) -> str:
        """Encrypt plaintext using a named secret key.

        Returns a base64-encoded str (nonce + ciphertext), NOT bytes —
        unlike secret_decrypt(), which returns raw bytes.
        """
        return self.secret_use(name, "encrypt", plaintext)

    def secret_decrypt(self, name: str, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext using a named secret key.

        Returns raw plaintext bytes, NOT str — unlike the other secret_*
        methods, which all return base64-encoded str.
        """
        return self.secret_use(name, "decrypt", ciphertext)

    # ============================================================
    # HTTP
    # ============================================================

    def http_request(self, method: str, url: str, headers=None, body=None) -> Dict[str, Any]:
        """Perform an HTTP request via http.request.

        Returns a dict shaped like ``{"status": int, "headers": dict,
        "body": str}`` on success.

        Raises LoamToolError on failure, or LoamArtifactRedirected if the
        response body was too large to inline.
        """
        args = {
            "method": method,
            "url": url,
            "headers": headers or {},
            "body": body or "",
        }

        result = self.tool("http.request", args)
        return self._unwrap_tool_result("http.request", result)

    # ============================================================
    # Subprocess
    # ============================================================
    def process_run(self, argv, stdin=None, timeout=None) -> Dict[str, Any]:
        """Run a sandboxed subprocess and return its raw result dict:
        ``{"exit_code": int, "stdout": str | None, "stderr": str | None,
        "artifact": str | None}`` (stdout/stderr are None and artifact is
        set if the combined output was too large to inline).

        Unlike the other typed wrappers this does not raise on a non-zero
        exit_code: the exit code of the command you ran is meaningful data
        for the caller to inspect, not a Loam-level failure (the same
        convention subprocess.run() itself follows by default).
        """
        args = {
            "argv": argv,
            "stdin": stdin,
            "timeout": timeout,
        }
        return self.tool("process.run", args)

    # ============================================================
    # Filesystem: search
    # ============================================================

    def fs_search(self, path: str, pattern: str = "", recursive: bool = False) -> list:
        """Search for files in the sandbox by filename pattern.

        Returns a list of matches (shape defined by the fs.search backend;
        empty list if the tool call reported no matches). Raises
        LoamToolError on failure, or LoamArtifactRedirected if the match
        list was too large to inline.
        """
        args = {
            "path": path,
            "pattern": pattern,
            "recursive": recursive,
        }

        result = self.tool("fs.search", args)
        payload = self._unwrap_tool_result("fs.search", result)
        return payload.get("matches", []) if payload is not None else []

    def fs_read(self, path: str) -> Optional[str]:
        """Read a file from the sandbox.

        Raises LoamToolError on failure, or LoamArtifactRedirected if the
        file was too large to inline (fetch it via the artifact path
        instead).
        """
        result = self.tool("fs.read", {"path": path})
        payload = self._unwrap_tool_result("fs.read", result)
        return payload.get("content") if payload is not None else None

    def fs_write(self, path: str, content: str) -> bool:
        """Write a file into the sandbox. Raises LoamToolError on failure."""
        result = self.tool("fs.write", {"path": path, "content": content})
        if result["exit_code"] != 0:
            raise LoamToolError("fs.write", result.get("stderr") or "fs.write failed")
        return True

    def fs_list(self, path: str) -> list:
        """List a sandbox directory.

        Returns a list of ``{"name": str, "is_dir": bool, "bytes": int |
        None}`` entries (bytes is None for directories).

        Raises LoamToolError on failure, or LoamArtifactRedirected if the
        listing was too large to inline.
        """
        result = self.tool("fs.list", {"path": path})
        payload = self._unwrap_tool_result("fs.list", result)
        return payload.get("entries", []) if payload is not None else []

    def fs_delete(self, path: str) -> bool:
        """Delete a file from the sandbox. Raises LoamToolError on failure."""
        result = self.tool("fs.delete", {"path": path})
        if result["exit_code"] != 0:
            raise LoamToolError("fs.delete", result.get("stderr") or "fs.delete failed")
        return True

    # ============================================================
    # State
    # ============================================================

    def state_read(self, path: str) -> Optional[str]:
        """Read a UTF‑8 file from the identity's state directory.

        Raises LoamToolError on failure, or LoamArtifactRedirected if the
        stored value was too large to inline.
        """
        result = self.tool("state.read", {"path": path})
        payload = self._unwrap_tool_result("state.read", result)
        return payload.get("data") if payload is not None else None

    def state_write(self, path: str, data: str) -> bool:
        """Write a UTF‑8 file into the identity's state directory. Chunks
        transparently if the payload would exceed the tool-call size cap.

        Deliberately kept outside the raise convention used elsewhere in
        this class: chunked writes are multi-step, and callers that just
        want a yes/no already have that here without a try/except. Use
        state_write_detailed() for the real failure reason."""
        return self._state_write_impl(path, data)["ok"]

    def state_write_detailed(self, path: str, data: str) -> Dict[str, Any]:
        """Same as state_write, but returns {"ok": bool, "error": str|None}
        with the real failure reason instead of discarding it."""
        return self._state_write_impl(path, data)

    def _state_write_impl(self, path: str, data: str) -> Dict[str, Any]:
        single_shot = json.dumps([{"path": path, "data": data}]).encode("utf-8")
        if len(single_shot) <= STATE_WRITE_SINGLE_SHOT_LIMIT:
            result = self.tool("state.write", {"path": path, "data": data})
            return self._interpret_tool_result(result)

        begin = self.tool("state.write_begin", {"path": path})
        interpreted = self._interpret_tool_result(begin)
        if not interpreted["ok"]:
            return interpreted
        try:
            handle = json.loads(begin["stdout"])["handle"]
        except Exception as e:
            return {"ok": False, "error": f"malformed write_begin response: {e}"}

        idx, n = 0, len(data)
        while idx < n:
            chunk_len = min(STATE_WRITE_CHUNK_CHAR_ESTIMATE, n - idx)
            candidate = data[idx: idx + chunk_len]
            # Defensive measure-and-shrink: verify actual encoded size before
            # sending, so worst-case escaping (e.g. all-emoji content) never
            # crosses the cap even though the base estimate assumes BMP text.
            for _ in range(20):
                msg_bytes = json.dumps([{"handle": handle, "data": candidate}]).encode("utf-8")
                if len(msg_bytes) <= STATE_WRITE_CHUNK_SAFETY_CAP or chunk_len <= 1:
                    break
                chunk_len = max(1, chunk_len // 2)
                candidate = data[idx: idx + chunk_len]

            interpreted = self._interpret_tool_result(
                self.tool("state.write_chunk", {"handle": handle, "data": candidate})
            )
            if not interpreted["ok"]:
                self.tool("state.write_abort", {"handle": handle})
                return interpreted
            idx += chunk_len

        commit = self.tool("state.write_commit", {"handle": handle})
        return self._interpret_tool_result(commit)

    def _interpret_tool_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if result["exit_code"] == 0:
            return {"ok": True, "error": None}
        error = result.get("stderr") or ""
        stdout = result.get("stdout")
        if stdout:
            try:
                payload = json.loads(stdout)
                error = payload.get("error", error) or error
            except Exception:
                error = stdout or error
        return {"ok": False, "error": error or "unknown error"}

    # ============================================================
    # Artifacts
    # ============================================================

    def artifact_emit(self, path: str, description: str | None = None) -> Dict[str, str]:
        """Emit a file as a signed artifact. Returns ``{"artifact": str}``
        (the artifact path). Raises LoamToolError on failure."""
        args = {"path": path}
        if description is not None:
            args["description"] = description

        result = self.tool("artifact.emit", args)
        if result["exit_code"] != 0:
            raise LoamToolError("artifact.emit", result.get("stderr") or "artifact.emit failed")

        # stdout is None; artifact contains the path
        return {"artifact": result["artifact"]}


    # ============================================================
    # Simulation
    # ============================================================

    def simulate(self, input_payload: Any) -> Dict[str, Any]:
        """Request a simulation run and return simulation_result."""
        self._send_json({"type": "simulate", "input": input_payload})

        while True:
            msg = self._read_json()
            if msg is None:
                self._fatal("EOF while waiting for simulation_result")

            if msg.get("type") == "simulation_result":
                return msg

            self._fatal(f"Unexpected message while waiting for simulation_result: {msg!r}")

    # ============================================================
    # Continuity
    # ============================================================

    def continuity_info(self) -> Dict[str, Any]:
        """
        Read-only continuity primitive: last recorded seq/state_hash/kind,
        and whether this identity has any continuity history at all.

        Returns a dict shaped like::

            {"fresh": bool, "last_seq": int, "last_state_hash": str | None,
             "last_kind": str | None}

        ``fresh`` is True only when the identity has no continuity log yet
        (i.e. this would be its genesis record). This reflects state as of
        process start, not this run's own record — that only exists after
        the agent finishes (see AgentRuntime.run() -> finalize_continuity()).
        Safe to call during simulation; raises LoamAgentError on failure.
        """
        call_id = str(uuid.uuid4())
        self._send_json({"type": "continuity_info", "call_id": call_id})

        while True:
            msg = self._read_json()
            if msg is None:
                self._fatal("EOF while waiting for continuity_info_result")

            if msg.get("type") == "continuity_info_result" and msg.get("call_id") == call_id:
                if msg.get("error"):
                    raise LoamAgentError(f"continuity_info failed: {msg['error']}")
                return msg.get("result")

            self._fatal(f"Unexpected message while waiting for continuity_info_result: {msg!r}")

    # ============================================================
    # Finish
    # ============================================================

    def finish(self, result: Any, status: str = "ok") -> None:
        """Send final result and exit."""
        self._send_json({"type": "finish", "status": status, "result": result})
        sys.exit(0)

    # ============================================================
    # Low-level IO
    # ============================================================

    def _read_json(self) -> Optional[Dict[str, Any]]:
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except Exception as e:
            self._fatal(f"Failed to parse JSON from runtime: {e!r}, line={line!r}")

    def _send_json(self, obj: Dict[str, Any]) -> None:
        try:
            sys.stdout.write(json.dumps(obj) + "\n")
            sys.stdout.flush()
        except Exception as e:
            self._fatal(f"Failed to send JSON to runtime: {e!r}")

    def _fatal(self, msg: str) -> None:
        sys.stderr.write(f"[AGENT FATAL] {msg}\n")
        sys.stderr.flush()
        sys.exit(1)
