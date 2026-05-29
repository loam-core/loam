#runtime/protocol.py

import base64
import os
import json
import time
import threading

from loam.substrate.artifacts import (
    build_tool_artifact_envelope,
    sign_artifact_envelope,
    write_tool_artifact_files,
)
from loam.runtime.simulation_runtime import SimulationRuntime

def run_agent_loop(runtime, agent_path, agent_args, proc=None, simulation_input=None, resume_input=None):
    # shared stderr buffer (survives await_input/resume)
    stderr_buffer: list[str] = []
    if resume_input is not None and "stderr_buffer" in resume_input:
        stderr_buffer = resume_input["stderr_buffer"]

    # ------------------------------------------------------------
    #  Agent Execution (protocol loop)
    # ------------------------------------------------------------
    if proc is None:
        log("agent: Popen")

        proc = runtime.driver.start_agent(
            runtime.exec_path,
            agent_args,
            env=os.environ.copy(),
            cwd=runtime.workdir,
        )

        if hasattr(runtime.driver, "read_stderr"):
            def _read_stderr():
                while True:
                    line = runtime.driver.read_stderr(proc)
                    if not line:
                        break
                    stderr_buffer.append(line)
            threading.Thread(target=_read_stderr, daemon=True).start()
        else:
            log("agent: no stderr handle; skipping stderr reader")


        # Send init
        init_msg = {
            "type": "init",
            "envelope": runtime.envelope,
            "envelope_hash": runtime.envelope_hash,
            "args": agent_args,
        }

        if simulation_input is not None:
            init_msg["simulation_input"] = simulation_input

        log("agent: send init")
        runtime.driver.send_json(proc, init_msg)
        log("agent: init flushed")

        # Read init ack only on fresh start
        try:
            msg = runtime.driver.read_json(proc)
        except Exception as e:
            log(f"agent: protocol error during init: {e!r}")
            return "error", {
                "kind": "protocol_error_init",
                "error": str(e),
                "stderr": "".join(stderr_buffer),
            }

        log(f"agent: got msg {msg!r}")

        if msg is None:
            log("agent: no init ack")
            return "error", {
                "kind": "no_init_ack",
                "stderr": "".join(stderr_buffer),
            }

        if msg.get("type") != "init":
            log(f"agent: unexpected first message {msg!r}")
            return "error", {
                "kind": "unexpected_init_response",
                "msg": msg,
                "stderr": "".join(stderr_buffer),
            }
    else:
        log("agent: resume existing proc")

    # Main loop (real messages)
    while True:
        try:
            msg = runtime.driver.read_json(proc)
        except Exception as e:
            log(f"agent: protocol error while reading JSON: {e!r}")
            return "error", {
                "kind": "protocol_error",
                "error": str(e),
                "stderr": "".join(stderr_buffer),
            }

        if msg is None:
            log("agent: stdout loop ended")

            runtime.chronicle(
                "execution_aborted",
                {
                    "exec_path": runtime.exec_path,
                    "exec_basename": runtime.exec_basename,
                    "exec_code_hash": runtime.exec_code_hash,
                    "run_id": runtime.run_id,
                    "error_type": "AgentTerminated",
                    "error_message": "agent terminated unexpectedly",
                    "envelope_hash": runtime.envelope_hash,
                },
            )

            return "error", {
                "kind": "agent_terminated",
                "message": "agent terminated unexpectedly",
                "stderr": "".join(stderr_buffer),
                "returncode": getattr(proc, "poll", lambda: None)(),
            }

        log(f"agent: got msg {msg!r}")
        msg_type = msg.get("type")

        if msg_type == "think":
            result = runtime.cognition_llm_think(
                backend=msg.get("backend"),
                input=msg["input"],
                model=msg.get("model"),
                tags=msg.get("tags"),
            )
            runtime.driver.send_json(proc, {
                "type": "think_result",
                "result": result,
            })
            continue

        elif msg_type == "call_tool":
            log("tool: start")
            call_id = msg["call_id"]
            tool_name = msg["name"]
            tool_args = msg.get("args", [])

            # Clamp tool payload size (agent → substrate)
            payload_bytes = len(json.dumps(tool_args).encode("utf-8"))
            if payload_bytes > MAX_PAYLOAD_BYTES:
                error_msg = {
                    "type": "tool_result",
                    "call_id": call_id,
                    "exit_code": -1,
                    "stdout": None,
                    "stderr": f"Tool payload too large ({payload_bytes} bytes > {MAX_PAYLOAD_BYTES})",
                    "artifact": None,
                }
                runtime.driver.send_json(proc, error_msg)
                continue

            result = runtime.run_tool(tool_name, tool_args)

            log("tool: done")

            artifact_info = maybe_artifact(
                store_id=runtime.store_id,
                tool=tool_name,
                stdout=result.stdout.encode(),
                stderr=result.stderr.encode(),
                exit_code=result.returncode,
                artifacts_path=runtime.artifacts_path,
            )

            tool_result_msg = {
                "type": "tool_result",
                "call_id": call_id,
                "exit_code": result.returncode,
                "stdout": artifact_info["stdout"],
                "stderr": artifact_info["stderr"],
                "artifact": artifact_info["artifact"],
            }

            log("agent: send tool_result")
            runtime.driver.send_json(proc, tool_result_msg)
            log("agent: tool_result flushed")

        elif msg_type == "simulate":
            if runtime.envelope["simulation_depth"] >= MAX_SIM_DEPTH:
                err = {
                    "type": "simulation_result",
                    "status": "error",
                    "error": "max_simulation_depth_exceeded",
                    "simulation_depth": runtime.envelope["simulation_depth"],
                }
                runtime.driver.send_json(proc, err)
                continue

            log("sim: start")

            runtime.chronicle(
                "simulation_started",
                {
                    "exec_path": runtime.exec_path,
                    "exec_basename": runtime.exec_basename,
                    "exec_code_hash": runtime.exec_code_hash,
                    "run_id": runtime.run_id,
                    "input": msg.get("input"),
                },
            )

            child = SimulationRuntime(parent=runtime, simulation_input=msg["input"])

            status, result = run_agent_loop(
                child,
                agent_path,
                agent_args,
                simulation_input=msg["input"],
            )

            log("sim: child finished")

            runtime.chronicle(
                "simulation_finished",
                {
                    "exec_path": runtime.exec_path,
                    "exec_basename": runtime.exec_basename,
                    "exec_code_hash": runtime.exec_code_hash,
                    "run_id": runtime.run_id,
                    "status": status,
                },
            )

            sim_result_msg = {
                "type": "simulation_result",
                "status": status,
                "result": result,
                "simulation_depth": child.envelope["simulation_depth"],
                "child_run_id": child.run_id,
                "parent_run_id": runtime.run_id,
            }
            sim_result_msg["telemetry"] = child.extract_simulation_telemetry()

            log("sim: send simulation_result")
            runtime.driver.send_json(proc, sim_result_msg)
            log("sim: simulation_result flushed")
            continue

        elif msg_type == "secret_use":
            call_id = msg["call_id"]
            name = msg["name"]
            operation = msg["operation"]
            payload_b64 = msg["payload"]

            try:
                payload = base64.b64decode(payload_b64)
            except Exception as e:
                err = {
                    "type": "secret_used",
                    "call_id": call_id,
                    "error": f"invalid_payload_b64: {e}",
                    "result": None,
                }
                runtime.driver.send_json(proc, err)
                continue

            try:
                result = runtime.secret_use(name, operation, payload)
            except Exception as e:
                err = {
                    "type": "secret_used",
                    "call_id": call_id,
                    "error": str(e),
                    "result": None,
                }
                runtime.driver.send_json(proc, err)
                continue

            resp = {
                "type": "secret_used",
                "call_id": call_id,
                "result": result,
            }
            runtime.driver.send_json(proc, resp)
            continue

        elif msg_type == "await_input":
            call_id = msg["call_id"]
            prompt = msg.get("prompt", "")

            return "await_input", {
                "call_id": call_id,
                "prompt": prompt,
                "proc": proc,
                "agent_path": agent_path,
                "agent_args": agent_args,
                "envelope": runtime.envelope,
                "stderr_buffer": stderr_buffer,
            }

        elif msg_type == "finish":
            log("agent: finish received")
            status = msg.get("status", "ok")
            result = msg.get("result", {})

            # attach stderr for debugging
            if isinstance(result, dict):
                result.setdefault("_stderr", "".join(stderr_buffer))

            runtime.driver.terminate(proc)
            log("agent: terminated")

            return status, result

        else:
            log(f"agent: unknown msg_type={msg_type}")
            err = {
                "type": "error",
                "kind": "unknown_message",
                "message": f"Unknown message type: {msg_type}",
            }
            runtime.driver.send_json(proc, err)



#---------------------------------------------
# Helpers
#---------------------------------------------
MAX_SIM_DEPTH = 32
MAX_PAYLOAD_BYTES = 8192
MAX_INLINE_BYTES = 4 * 1024 * 1024  # 4 MB


def clamp_bytes(s, limit=MAX_PAYLOAD_BYTES):
    if s is None:
        return None
    b = s.encode("utf-8")
    if len(b) <= limit:
        return s
    return b[:limit].decode("utf-8", errors="ignore") + "...<truncated>"


def log(label):
    print(f"[{time.monotonic():.3f}] {label}")



def maybe_artifact(store_id, tool, stdout, stderr, exit_code, artifacts_path):
    if len(stdout) + len(stderr) <= MAX_INLINE_BYTES:
        return {
            "stdout": stdout.decode("utf-8", errors="ignore"),
            "stderr": stderr.decode("utf-8", errors="ignore"),
            "artifact": None,
        }

    envelope, canonical = build_tool_artifact_envelope(
        store_id=store_id,
        tool=tool,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
    )

    envelope["signature"] = sign_artifact_envelope(store_id, canonical)

    path = write_tool_artifact_files(
        store_id=store_id,
        tool=tool,
        stdout=stdout,
        stderr=stderr,
        envelope=envelope,
        artifacts_path=artifacts_path,
    )

    return {
        "stdout": None,
        "stderr": None,
        "artifact": str(path),
    }