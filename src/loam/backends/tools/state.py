#backends/tools/state.py
import json
from loam.continuity.hash import compute_file_hash

def read(context, args):
    # 1. Check state enabled
    state_root = context._state_root()
    if state_root is None:
        return {
            "result": {"error": "StateNotEnabled"},
            "meta": {"error": "StateNotEnabled"}
        }

    rel_path = args["path"]
    full_path = (state_root / rel_path).resolve()

    # 2. Enforce boundary
    try:
        state_root_resolved = state_root.resolve()
        if not str(full_path).startswith(str(state_root_resolved)):
            return {
                "result": {"error": "StatePathViolation"},
                "meta": {"error": "StatePathViolation"}
            }
    except Exception:
        return {
            "result": {"error": "StatePathViolation"},
            "meta": {"error": "StatePathViolation"}
        }

    # 3. Read file
    try:
        content_bytes = full_path.read_bytes()
    except FileNotFoundError:
        return {
            "result": {"error": "StateFileNotFound"},
            "meta": {"error": "StateFileNotFound"}
        }

    content_str = content_bytes.decode("utf-8", errors="replace")

    return {
        "result": {"data": content_str},
        "meta": {
            "path": rel_path,
            "bytes": len(content_bytes),
            "full_path": str(full_path),
            # content_hash is safe — emitter will hash it later
            "content": content_str
        }
    }

def write(context, args):
    # 1. Check state enabled
    state_root = context._state_root()
    if state_root is None:
        return {
            "result": {"error": "StateNotEnabled"},
            "meta": {"error": "StateNotEnabled"}
        }

    # 2. Reject writes during simulation
    if getattr(context, "simulation_mode", False):
        return {
            "result": {"error": "StateWriteForbiddenDuringSimulation"},
            "meta": {"error": "StateWriteForbiddenDuringSimulation"}
        }

    rel_path = args["path"]
    data = args.get("data", "").encode("utf-8")

    full_path = (state_root / rel_path).resolve()

    # 3. Enforce boundary
    try:
        state_root_resolved = state_root.resolve()
        if not str(full_path).startswith(str(state_root_resolved)):
            return {
                "result": {"error": "StatePathViolation"},
                "meta": {"error": "StatePathViolation"}
            }
    except Exception:
        return {
            "result": {"error": "StatePathViolation"},
            "meta": {"error": "StatePathViolation"}
        }

    # 4. Write file (atomic)
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = full_path.with_suffix(".tmp")
        tmp_path.write_bytes(data)
        tmp_path.replace(full_path)

        if context.state_enabled:
            context._update_state_hash()

    except Exception as e:
        return {
            "result": {"error": str(e)},
            "meta": {"error": str(e)}
        }

    return {
        "result": {"ok": True},
        "meta": {
            "path": rel_path,
            "bytes": len(data),
            "full_path": str(full_path),
            # emitter will compute file_hash_after
        }
    }

