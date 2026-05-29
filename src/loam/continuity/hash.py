# loam/continuity/hash.py

import hashlib
import json
from pathlib import Path


def canonicalize_continuity_v1(payload: dict) -> bytes:
    """
    Canonical JSON for Continuity v1.
    - Only the allowed fields
    - Deterministic key order
    - No whitespace
    - UTF-8 bytes
    """
    allowed_keys = [
        "seq",
        "timestamp",
        "kind",
        "prev_hash",
        "identity_fingerprint_hash",
        "state_hash",
        "schema_version",
    ]

    # Ensure no extra fields sneak in
    clean = {k: payload.get(k) for k in allowed_keys}

    return json.dumps(
        clean,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_continuity_entry_hash_v1(payload: dict) -> str:
    """
    Compute the hash of a continuity v1 payload.
    Payload must NOT include 'hash' or 'signature'.
    """
    canonical = canonicalize_continuity_v1(payload)
    return hashlib.sha256(canonical).hexdigest()


def compute_file_hash(path: Path) -> str:
    """
    Compute SHA-256 hash of a file's raw bytes.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
