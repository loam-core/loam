#backends/tools/state.py
import json
import uuid
from loam.continuity.hash import compute_file_hash


def _resolve_state_path(context, rel_path):
    """Resolve rel_path under the identity's state root, enforcing the boundary.

    Returns (full_path, None) on success, or (None, error_dict) on failure.
    """
    state_root = context._state_root()
    if state_root is None:
        return None, {
            "result": {"error": "StateNotEnabled"},
            "meta": {"error": "StateNotEnabled"}
        }

    full_path = (state_root / rel_path).resolve()

    try:
        state_root_resolved = state_root.resolve()
        if not str(full_path).startswith(str(state_root_resolved)):
            return None, {
                "result": {"error": "StatePathViolation"},
                "meta": {"error": "StatePathViolation"}
            }
    except Exception:
        return None, {
            "result": {"error": "StatePathViolation"},
            "meta": {"error": "StatePathViolation"}
        }

    return full_path, None


def _reject_if_simulation(context):
    if getattr(context, "simulation_mode", False):
        return {
            "result": {"error": "StateWriteForbiddenDuringSimulation"},
            "meta": {"error": "StateWriteForbiddenDuringSimulation"}
        }
    return None


def _abort_session(context, handle):
    sessions = getattr(context, "_state_write_sessions", None)
    if not sessions:
        return
    session = sessions.pop(handle, None)
    if session is None:
        return
    try:
        if not session["fh"].closed:
            session["fh"].close()
    except Exception:
        pass
    try:
        if session["tmp_path"].exists():
            session["tmp_path"].unlink()
    except Exception:
        pass


def read(context, args):
    # 1. Check state enabled + resolve/boundary-check path
    rel_path = args["path"]
    full_path, err = _resolve_state_path(context, rel_path)
    if err:
        return err

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
    sim_err = _reject_if_simulation(context)
    if sim_err:
        return sim_err

    rel_path = args["path"]
    data = args.get("data", "").encode("utf-8")

    # 3. Resolve/boundary-check path
    full_path, err = _resolve_state_path(context, rel_path)
    if err:
        return err

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


def write_begin(context, args):
    # 1. Check state enabled
    state_root = context._state_root()
    if state_root is None:
        return {
            "result": {"error": "StateNotEnabled"},
            "meta": {"error": "StateNotEnabled"}
        }

    # 2. Reject writes during simulation
    sim_err = _reject_if_simulation(context)
    if sim_err:
        return sim_err

    rel_path = args["path"]

    # 3. Resolve/boundary-check path
    full_path, err = _resolve_state_path(context, rel_path)
    if err:
        return err

    handle = uuid.uuid4().hex
    # Session-scoped tmp name -- NOT full_path.with_suffix(".tmp"): that scheme
    # truncates real extensions and isn't unique per concurrent session.
    tmp_path = full_path.with_name(full_path.name + f".{handle}.tmp")

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(tmp_path, "wb")
    except Exception as e:
        return {
            "result": {"error": str(e)},
            "meta": {"error": str(e)}
        }

    if not hasattr(context, "_state_write_sessions"):
        context._state_write_sessions = {}

    context._state_write_sessions[handle] = {
        "fh": fh,
        "tmp_path": tmp_path,
        "full_path": full_path,
        "rel_path": rel_path,
        "bytes_written": 0,
    }

    return {
        "result": {"handle": handle},
        "meta": {"path": rel_path, "full_path": str(full_path)},
    }


def write_chunk(context, args):
    handle = args.get("handle")
    sessions = getattr(context, "_state_write_sessions", None)
    session = sessions.get(handle) if sessions else None
    if session is None:
        return {
            "result": {"error": "StateWriteSessionNotFound"},
            "meta": {"error": "StateWriteSessionNotFound"}
        }

    data = args.get("data", "").encode("utf-8")
    try:
        session["fh"].write(data)
        session["fh"].flush()
        session["bytes_written"] += len(data)
    except Exception as e:
        _abort_session(context, handle)
        return {
            "result": {"error": str(e)},
            "meta": {"error": str(e)}
        }

    return {
        "result": {"ok": True},
        "meta": {"path": session["rel_path"], "bytes": len(data)}
    }


def write_commit(context, args):
    handle = args.get("handle")
    sessions = getattr(context, "_state_write_sessions", None)
    session = sessions.pop(handle, None) if sessions else None
    if session is None:
        return {
            "result": {"error": "StateWriteSessionNotFound"},
            "meta": {"error": "StateWriteSessionNotFound"}
        }

    try:
        session["fh"].close()
        session["tmp_path"].replace(session["full_path"])

        if context.state_enabled:
            context._update_state_hash()

    except Exception as e:
        try:
            if session["tmp_path"].exists():
                session["tmp_path"].unlink()
        except Exception:
            pass
        return {
            "result": {"error": str(e)},
            "meta": {"error": str(e)}
        }

    return {
        "result": {"ok": True},
        "meta": {
            "path": session["rel_path"],
            "bytes": session["bytes_written"],
            "full_path": str(session["full_path"]),
        }
    }


def write_abort(context, args):
    handle = args.get("handle")
    _abort_session(context, handle)
    return {"result": {"ok": True}, "meta": {}}

