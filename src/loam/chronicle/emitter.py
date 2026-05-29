# chronicle/emitter.py
import hashlib
from datetime import datetime, timezone

from loam.chronicle.chronicle import append_chronicle_entry
from loam.continuity.append import load_last_record
from loam.identity.identity_fingerprint import build_identity_fingerprint_v1
from loam.crypto.canonical import canonical_json
from loam.continuity.hash import compute_file_hash


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def emit_chronicle_event(store_id: str, event_type: str, payload: dict | None = None, signer=None):
    """
    Semantic Chronicle emitter.
    Assumes payload has already been sanitized by the dispatcher.
    Performs light normalization + enrichment, then delegates to append_chronicle_entry.
    """

    if payload is None:
        payload = {}

    # 1. Normalize keys (shallow)
    payload = {str(k): v for k, v in payload.items()}

    # 2. Event-type specific enrichment
    if event_type == "tool_start":
        payload = enrich_tool_start(payload)

    elif event_type == "tool_finished":
        payload = enrich_tool_finished(payload)

    elif event_type == "tool_error":
        payload = enrich_tool_error(payload)

    elif event_type == "execution_start":
        payload = enrich_execution_start(payload)

    elif event_type == "execution_finished":
        payload = enrich_execution_finished(payload)

    # 3. Identity fingerprint
    identity_fp = build_identity_fingerprint_v1(store_id)

    # 4. Continuity sequence
    head = load_last_record(store_id)
    continuity_seq = head["seq"] if head else None

    # 5. Build Chronicle event
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": event_type,
        "store_id": store_id,
        "identity_fingerprint": identity_fp,
        "continuity_seq": continuity_seq,
        "payload": payload,
    }

    # 6. Delegate to physics layer
    return append_chronicle_entry(store_id, event, signer)


# ---------------------------------------------------------------------------
# Enrichment functions (safe, structural, no raw payloads)
# ---------------------------------------------------------------------------

def enrich_tool_start(payload):
    tool = payload.get("tool")

    enriched = {
        **payload,
        # hash of structural params only
        "params_hash": sha256_bytes(canonical_json(payload)),
    }

    # URL hash (safe)
    if "url" in payload:
        enriched["url_hash"] = sha256_str(payload["url"])

    # Path hash (safe)
    if "path" in payload:
        enriched["path_hash"] = sha256_str(payload["path"])

    # Command hash (safe)
    if tool == "process.run" and "cmd" in payload:
        enriched["cmd_hash"] = sha256_bytes(canonical_json(payload["cmd"]))

    return enriched


def enrich_tool_finished(payload):
    tool = payload.get("tool")

    enriched = {
        **payload,
        # hash of structural params only
        "params_hash": sha256_bytes(canonical_json(payload)),
    }

    # fs.write / state.write — compute file_hash_after
    if tool in ("fs.write", "state.write"):
        full = payload.get("full_path")
        if full:
            try:
                enriched["file_hash_after"] = compute_file_hash(full)
            except Exception:
                enriched["file_hash_after"] = None

    # fs.delete — file_hash_before already provided by backend
    if tool == "fs.delete":
        enriched["file_hash_before"] = payload.get("file_hash_before")

    # artifact.emit — compute canonical_hash
    if tool == "artifact.emit":
        full = payload.get("full_path")
        if full:
            try:
                enriched["canonical_hash"] = compute_file_hash(full)
            except Exception:
                enriched["canonical_hash"] = None

    return enriched


def enrich_tool_error(payload):
    return {
        **payload,
        "params_hash": sha256_bytes(canonical_json(payload)),
    }


def enrich_execution_start(payload):
    args = payload.get("args")
    args_hash = sha256_bytes(canonical_json(args)) if args is not None else None

    exec_path = payload.get("exec_path")
    exec_path_hash = sha256_str(exec_path) if exec_path else None

    return {
        **payload,
        "args_hash": args_hash,
        "exec_path_hash": exec_path_hash,
    }


def enrich_execution_finished(payload):
    status = payload.get("status")
    status_hash = sha256_str(str(status)) if status is not None else None

    # v2: no raw result, no result_hash
    return {
        **payload,
        "status_hash": status_hash,
    }



# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
