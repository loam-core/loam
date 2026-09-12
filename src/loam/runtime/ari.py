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

    # ============================================================
    # LLM
    # ============================================================

    def llm_think(self, input: str, backend=None, model=None, tags=None):
        """Send a cognition request (not a tool call) to the runtime."""
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
            if msg and msg.get("type") == "input" and msg.get("call_id") == call_id:
                return msg["value"]


    # ============================================================
    # Secrets
    # ============================================================

    def secret_use(self, name: str, operation: str, payload: bytes):
        """Request a secret operation without exposing the secret."""
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
                    self._fatal(f"secret_use failed: {msg['error']}")
                return msg.get("result")

            self._fatal(f"Unexpected message while waiting for secret_used: {msg!r}")

    def secret_hmac(self, name: str, payload: bytes) -> str:
        """Compute HMAC using a named secret."""
        return self.secret_use(name, "hmac", payload)

    def secret_sign(self, name: str, payload: bytes):
        """Sign payload using a named secret key."""
        return self.secret_use(name, "sign", payload)

    def secret_encrypt(self, name: str, plaintext: bytes):
        """Encrypt plaintext using a named secret key."""
        return self.secret_use(name, "encrypt", plaintext)

    def secret_decrypt(self, name: str, ciphertext: bytes):
        """Decrypt ciphertext using a named secret key."""
        return self.secret_use(name, "decrypt", ciphertext)

    # ============================================================
    # HTTP
    # ============================================================

    def http_request(self, method: str, url: str, headers=None, body=None):
        """Perform an HTTP request via http.request."""
        args = {
            "method": method,
            "url": url,
            "headers": headers or {},
            "body": body or "",
        }

        result = self.tool("http.request", args)
        if result["exit_code"] != 0:
            return None

        try:
            return json.loads(result["stdout"])
        except Exception:
            return None
        
    # ============================================================
    # Subprocess
    # ============================================================
    def process_run(self, argv, stdin=None, timeout=None):
        args = {
            "argv": argv,
            "stdin": stdin,
            "timeout": timeout,
        }
        return self.tool("process.run", args)

    # ============================================================
    # Filesystem: search
    # ============================================================

    def fs_search(self, path: str, pattern: str = "", recursive: bool = False):
        """Search for files in the sandbox by filename pattern."""
        args = {
            "path": path,
            "pattern": pattern,
            "recursive": recursive,
        }

        result = self.tool("fs.search", args)
        if result["exit_code"] != 0:
            return []

        try:
            payload = json.loads(result["stdout"])
            return payload.get("matches", [])
        except Exception:
            return []

    def fs_read(self, path: str) -> Optional[str]:
        result = self.tool("fs.read", {"path": path})
        if result["exit_code"] != 0:
            return None
        try:
            payload = json.loads(result["stdout"])
            return payload.get("content")
        except Exception:
                return None

    def fs_write(self, path: str, content: str) -> bool:
        result = self.tool("fs.write", {"path": path, "content": content})
        return result["exit_code"] == 0

    def fs_list(self, path: str):
        result = self.tool("fs.list", {"path": path})
        if result["exit_code"] != 0:
            return []
        try:
            payload = json.loads(result["stdout"])
            return payload.get("entries", [])
        except Exception:
            return []

    def fs_delete(self, path: str) -> bool:
        result = self.tool("fs.delete", {"path": path})
        return result["exit_code"] == 0
    # ============================================================
    # State
    # ============================================================

    def state_read(self, path: str) -> Optional[str]:
        """Read a UTF‑8 file from the identity's state directory."""
        result = self.tool("state.read", {"path": path})
        if result["exit_code"] != 0:
            return None

        try:
            payload = json.loads(result["stdout"])
            return payload.get("data")
        except Exception:
            return None

    def state_write(self, path: str, data: str) -> bool:
        """Write a UTF‑8 file into the identity's state directory. Chunks
        transparently if the payload would exceed the tool-call size cap."""
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

    def artifact_emit(self, path: str, description: str | None = None):
        args = {"path": path}
        if description is not None:
            args["description"] = description

        result = self.tool("artifact.emit", args)
        if result["exit_code"] != 0:
            raise RuntimeError(f"artifact.emit failed: {result['stderr']}")

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
