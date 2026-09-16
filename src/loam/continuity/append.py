# loam/continuity/append.py

import base64
import json
from datetime import datetime, timezone

from loam.continuity.hash import (
    canonicalize_continuity_v1,
    compute_continuity_entry_hash_v1,
)
from loam.continuity.witness import witness_publish
from loam.identity.paths import (
    continuity_log,
)


def load_last_record(store_id: str):
    """
    Returns the last continuity record dict, or None if no log exists.
    """
    log_path = continuity_log(store_id)

    if not log_path.exists():
        return None

    with open(log_path, "r") as f:
        lines = f.read().strip().splitlines()
        if not lines:
            return None
        return json.loads(lines[-1])


def create_continuity_record(
    store_id: str,
    signer,
    *,
    identity_fingerprint_hash: str,
    state_hash: str | None,
    kind: str | None = None,
) -> dict:
    """
    Create a continuity v1 record.
    Continuity is the durable identity/state ledger.
    """

    # Load previous record
    prev_record = load_last_record(store_id)

    if prev_record:
        prev_hash = prev_record["hash"]
        last_seq = prev_record["seq"]
        default_kind = "inscription"
    else:
        prev_hash = None
        last_seq = 0
        default_kind = "genesis"

    seq = last_seq + 1
    kind = kind or default_kind
    timestamp = datetime.now(timezone.utc).isoformat()

    # Build canonical payload (NO hash, NO signature)
    payload = {
        "seq": seq,
        "timestamp": timestamp,
        "kind": kind,
        "prev_hash": prev_hash,
        "identity_fingerprint_hash": identity_fingerprint_hash,
        "state_hash": state_hash,
        "code_hash": None,
        "schema_version": 1,
    }

    # Canonicalize
    canonical = canonicalize_continuity_v1(payload)

    # Compute hash
    record_hash = compute_continuity_entry_hash_v1(payload)

    # Sign using signer abstraction
    sig_bytes = signer.sign(canonical)
    signature_b64 = base64.b64encode(sig_bytes).decode()

    # Final record
    record = dict(payload)
    record["hash"] = record_hash
    record["signature"] = signature_b64

    return record



def append_continuity_record(store_id: str, record: dict):
    # --- Invariants ---
    # identity_fingerprint_hash must ALWAYS be present
    assert record.get("identity_fingerprint_hash") is not None

    kind = record.get("kind")

    if kind == "genesis":
        # Genesis: first record, prev_hash must be None
        assert record.get("prev_hash") is None

    elif kind == "inscription":
        # Execution inscriptions: state_hash may be present or None
        # No additional invariants for v1
        pass

    elif kind == "identity_mutation":
        # Identity mutations MUST NOT have a state hash in v1
        assert record.get("state_hash") is None

    elif kind == "unlock":
        # Unlock MUST carry forward the previous state hash.
        # So state_hash may be None (no continuity yet) or equal to the last record's state_hash.
        pass

    else:
        raise ValueError(f"Unknown continuity kind: {kind}")

    # --- Write record ---
    log_path = continuity_log(store_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    witness_publish(
        store_id,
        record["seq"],
        record["hash"],
        record.get("state_hash"),
    )

def create_unlock_record(store_id: str, signer, *, identity_fingerprint_hash: str, mechanism_hash: str):
    """
    Create a continuity unlock record.
    Unlock events do not mutate state, but must carry forward the last state_hash
    so the state continuity boundary remains enforced.
    """
    prev = load_last_record(store_id)
    prev_state_hash = prev.get("state_hash") if prev else None

    record = create_continuity_record(
        store_id,
        signer,
        identity_fingerprint_hash=identity_fingerprint_hash,
        state_hash=prev_state_hash,
        kind="unlock",
    )

    record["mechanism_hash"] = mechanism_hash
    return record


def append_unlock_record(store_id: str, signer, *, identity_fingerprint_hash: str, mechanism_hash: str):
    record = create_unlock_record(
        store_id,
        signer,
        identity_fingerprint_hash=identity_fingerprint_hash,
        mechanism_hash=mechanism_hash,
    )
    append_continuity_record(store_id, record)
    return record
