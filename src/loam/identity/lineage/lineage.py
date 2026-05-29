from __future__ import annotations

import base64
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from loam.identity.identity_fingerprint import build_identity_fingerprint_v1
from loam.identity.paths import (
    lineage_dir,
    lineage_file,
    public_key_file,
)
from loam.crypto.canonical import canonical_json
from loam.crypto.signing import verify

# ------------------------------------------------------------
# Dataclass for final lineage schema
# ------------------------------------------------------------

@dataclass
class Lineage:
    schema_version: int
    identity_fingerprint: str
    parent_fingerprint: Optional[str]
    timestamp: str
    signature: Optional[str] = None



# ------------------------------------------------------------
# Creation
# ------------------------------------------------------------

def create_root_lineage(store_id: str, identity_fp: str, signer) -> None:
    """
    Create lineage.json for a root identity.
    Root lineage is self-signed.
    """

    lid_dir = lineage_dir(store_id)
    lid_dir.mkdir(parents=True, exist_ok=True)

    lineage = Lineage(
        schema_version=1,
        identity_fingerprint=identity_fp,
        parent_fingerprint=None,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )

    # Convert to dict without signature
    data = asdict(lineage)
    data["signature"] = None

    # Canonical bytes for signing (exclude signature)
    signing_dict = {k: v for k, v in data.items() if k != "signature"}
    message = canonical_json(signing_dict)

    # Sign using identity-plane signer abstraction
    sig_bytes = signer.sign(message)
    signature_b64 = base64.b64encode(sig_bytes).decode()

    # Insert signature
    data["signature"] = signature_b64

    # Write lineage.json
    json_path = lineage_file(store_id)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)



# ------------------------------------------------------------
# Verification
# ------------------------------------------------------------

def verify_lineage(store_id: str) -> None:
    """
    Verify lineage.json for this identity.
    v1 supports only root identities (no parent).
    """
    json_path = lineage_file(store_id)

    if not json_path.exists():
        raise RuntimeError("missing_lineage")

    data = json.loads(json_path.read_text())

    # Check schema version
    if data.get("schema_version") != 1:
        raise RuntimeError("unsupported_lineage_schema_version")

    # Check identity fingerprint matches unified fingerprint
    expected_fp = build_identity_fingerprint_v1(store_id)
    if data.get("identity_fingerprint") != expected_fp:
        raise RuntimeError("lineage_identity_fingerprint_mismatch")

    # v1: only root identities
    if data.get("parent_fingerprint") is not None:
        raise RuntimeError("unexpected_lineage_parent")

    # Extract signature
    signature_b64 = data.get("signature")
    if not signature_b64:
        raise RuntimeError("missing_lineage_signature")

    try:
        signature = base64.b64decode(signature_b64)
    except Exception:
        raise RuntimeError("invalid_lineage_signature_format")

    # Canonical bytes for verification (exclude signature)
    signing_dict = {k: v for k, v in data.items() if k != "signature"}
    message = canonical_json(signing_dict)

    # Load raw public key bytes
    public_key_bytes = public_key_file(store_id).read_bytes()

    # Verify signature
    ok = verify(public_key_bytes, message, signature)
    if not ok:
        raise RuntimeError("invalid_lineage_signature")


