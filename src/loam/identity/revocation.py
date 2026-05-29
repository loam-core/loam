# loam/identity/revocation.py

import json
from pathlib import Path

import json
from pathlib import Path

# Global revocation registry for Loam v0.1.
# Stores a list of revoked public_key_fingerprints.
REVOCATION_PATH = Path(__file__).parent / "revocation.json"


def check_revocation(public_key_fingerprint: str) -> None:
    """
    Check whether the given public_key_fingerprint is revoked.

    Revocation in Loam v0.1 is:
    - global (not per-store)
    - identity-level (not metadata-level)
    - based solely on the public key fingerprint
    - permanent (no key rotation in v0.1)

    If the fingerprint appears in revocation.json, startup must fail.
    """
    if not REVOCATION_PATH.exists():
        return

    try:
        data = json.loads(REVOCATION_PATH.read_text())
    except Exception as e:
        raise RuntimeError(f"invalid_revocation_json: {e}")

    for entry in data.get("revoked", []):
        if entry.get("identity_fingerprint") == public_key_fingerprint:
            raise RuntimeError(f"identity_revoked: {public_key_fingerprint}")

