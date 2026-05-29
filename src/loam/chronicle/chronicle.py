# loam/chronicle/chronicle.py

import base64
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from loam.crypto.canonical import canonical_chronicle_string, normalize
from loam.continuity.append import load_last_record
from loam.identity.paths import private_key_file, chronicle_log
from loam.identity.paths import CHRONICLE_DIR, CHRONICLE_LOG


MAX_CHRONICLE_SIZE = 1_000_000  # 1 MB for v0.1

def append_chronicle_entry(store_id: str, event: dict, signer):

    """
    Append a canonical Chronicle v1 event.

    Writer and verifier must agree on:
      - which fields are excluded from the hash/signature payload
      - normalization
      - canonicalization
    """

    store_dir = Path(store_id)
    log_path = chronicle_log(store_id)

    # Detect previous entry (hash chain)
    prev_event_hash = None
    if log_path.exists() and log_path.stat().st_size > 0:
        with open(log_path, "r") as f:
            last = json.loads(f.readlines()[-1])
            prev_event_hash = last.get("event_hash")

    # Continuity anchoring
    head = load_last_record(store_id)
    if head:
        event["continuity_hash"] = head["hash"]
        event["continuity_seq"] = head["seq"]
    else:
        event["continuity_hash"] = None
        event["continuity_seq"] = None


    # Add prev_event_hash
    if prev_event_hash is not None:
        event["prev_event_hash"] = prev_event_hash

    # Inject schema + event version BEFORE canonicalization
    event["schema_version"] = 1
    event["event_version"] = 1

    # ---- MUST MATCH VERIFIER ----
    event_for_canonical = {
        k: v for k, v in event.items()
        if k not in ("event_hash", "signature", "prev_event_hash")
    }

    normalized = normalize(event_for_canonical)
    canonical_for_hash = canonical_chronicle_string(normalized).encode("utf-8")

    # Hash
    event_hash = hashlib.sha256(canonical_for_hash).hexdigest()

    # Sign using signer abstraction
    sig_bytes = signer.sign(canonical_for_hash)
    signature_b64 = base64.b64encode(sig_bytes).decode()

    event["event_hash"] = event_hash
    event["signature"] = signature_b64
    # ---- END ----

    _rotate_if_needed(store_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a") as f:
        f.write(json.dumps(event, separators=(",", ":")) + "\n")

    return event

# ---------------------------------------------------------------------
# ROTATION
# ---------------------------------------------------------------------
def _rotate_if_needed(store_dir):
    store_dir = Path(store_dir)
    chronicle_dir = store_dir / CHRONICLE_DIR
    active = chronicle_dir / CHRONICLE_LOG

    if not active.exists():
        return
    if active.stat().st_size < MAX_CHRONICLE_SIZE:
        return

    # Find next index
    idx = 1
    while True:
        rotated = chronicle_dir / f"chronicle.{idx}.log"
        if not rotated.exists():
            break
        idx += 1

    # Rotate
    active.rename(rotated)

    # Create fresh active file
    active.touch()


# ---------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------
def reset_chronicle(store_dir):
    store_dir = Path(store_dir)
    log_path = chronicle_log(store_dir.name)
    if log_path.exists():
        log_path.unlink()


def now_rfc3339():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# ---------------------------------------------------------------------
# Genesis
# ---------------------------------------------------------------------
def write_chronicle_genesis(store_id: str, signer, identity_fp: str):
    append_chronicle_entry(store_id, {
        "event_type": "genesis",
        "note": "Life from the Loam",
        "identity_fingerprint": identity_fp,
    }, signer)

