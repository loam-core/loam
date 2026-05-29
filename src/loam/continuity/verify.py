# loam/continuity/verify.py

import json
from pathlib import Path

from loam.continuity.hash import compute_continuity_entry_hash_v1
from loam.continuity.hash import canonicalize_continuity_v1
from loam.crypto.signing import verify_b64
from loam.continuity.witness import witness_verify

from loam.identity.paths import (
    public_key_file,
    continuity_log,
)


def verify(store_id: str) -> bool:
    ok, _ = verify_chain(store_id)
    return ok


def verify_chain(store_id: str) -> tuple[bool, dict]:
    """
    Verify the continuity chain for a store's identity (Continuity v1).
    """

    # Load public key (raw Ed25519 bytes)
    pub_path = public_key_file(store_id)
    public_key_bytes = pub_path.read_bytes()

    # Load continuity log
    log_path = continuity_log(store_id)
    if not log_path.exists():
        return False, {"reason": "Continuity log is missing."}

    try:
        raw = log_path.read_text().strip()
    except Exception as e:
        return False, {"reason": f"Continuity log unreadable: {e}"}

    if not raw:
        return False, {"reason": "Continuity log is empty."}

    lines = raw.splitlines()

    prev_hash = None
    prev_seq = 0
    prev_timestamp = None

    for index, line in enumerate(lines):
        record = json.loads(line)

        # Required fields for the NEW continuity schema
        required = [
            "seq",
            "timestamp",
            "kind",
            "prev_hash",
            "identity_fingerprint_hash",
            "state_hash",
            "code_hash",
            "schema_version",
            "hash",
            "signature",
        ]

        for k in required:
            if k not in record:
                return False, {"reason": f"Missing field '{k}' in continuity record."}

        # Schema version check
        if record["schema_version"] != 1:
            return False, {"reason": "Unsupported continuity schema version."}

        # Sequence continuity
        seq = record["seq"]
        if seq != prev_seq + 1:
            return False, {"reason": "Seq continuity violation."}

        # Hash linkage
        if record["prev_hash"] != prev_hash:
            return False, {"reason": "Chain linkage mismatch."}

        # Timestamp monotonicity
        ts = record["timestamp"]
        if prev_timestamp is not None and ts <= prev_timestamp:
            return False, {"reason": "Timestamp monotonicity violation."}

        # Reconstruct canonical payload (NO agent_id, NO envelope_hash)
        payload = {
            "seq": record["seq"],
            "timestamp": record["timestamp"],
            "kind": record["kind"],
            "prev_hash": record["prev_hash"],
            "identity_fingerprint_hash": record["identity_fingerprint_hash"],
            "state_hash": record["state_hash"],
            "code_hash": record["code_hash"],
            "schema_version": record["schema_version"],
        }

        canonical = canonicalize_continuity_v1(payload)
        computed_hash = compute_continuity_entry_hash_v1(payload)

        # Hash check
        if record["hash"] != computed_hash:
            return False, {"reason": "Hash mismatch in continuity record."}

        # Signature check
        if not verify_b64(public_key_bytes, canonical, record["signature"]):
            return False, {"reason": "Signature verification failed."}

        # Advance chain
        prev_hash = computed_hash
        prev_seq = seq
        prev_timestamp = ts

    # Witness verification (unchanged)
    ok = witness_verify(store_id, prev_seq, prev_hash, None)
    if not ok:
        return False, {"reason": "Witness mismatch."}

    return True, {
    "last_seq": prev_seq,
    "last_hash": prev_hash,
    }   
