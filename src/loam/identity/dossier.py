# loam/identity/dossier.py

import base64
import json
import socket
import getpass
from datetime import datetime, timezone

from loam.identity.paths import (
    public_key_file,
    dossier_file,
)
from loam.crypto.canonical import canonical_json
from loam.crypto.signing import verify_b64
from loam.identity.identity_fingerprint import build_identity_fingerprint_v1



SCHEMA_VERSION = 1


# ------------------------------------------------------------
# Creation
# ------------------------------------------------------------

def create_root_dossier(store_id: str, identity_fp: str, signer) -> None:
    """
    Create the root dossier for an identity store.
    """

    # Load raw public key bytes
    public_key_bytes = public_key_file(store_id).read_bytes()
    public_key_b64 = base64.b64encode(public_key_bytes).decode()

    identity_block = {
        "identity_fingerprint": identity_fp,
        "public_key_b64": public_key_b64,
    }

    origin = {}
    hostname = socket.gethostname()
    user = getpass.getuser()

    if hostname:
        origin["hostname"] = hostname
    if user:
        origin["user"] = user
    if origin:
        origin["kind"] = "local"

    base_dossier = {
        "store_id": store_id,
        "identity": identity_block,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "schema_version": SCHEMA_VERSION,
    }

    if origin:
        base_dossier["origin"] = origin

    canonical = canonical_json(base_dossier)

    # Sign using the identity-plane signer abstraction
    sig_bytes = signer.sign(canonical)
    signature_b64 = base64.b64encode(sig_bytes).decode()

    dossier = dict(base_dossier)
    dossier["signature"] = signature_b64

    path = dossier_file(store_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            dossier,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )




# ------------------------------------------------------------
# Verification
# ------------------------------------------------------------

def verify_root_dossier(store_id: str) -> None:
    """
    Verify the root dossier for an identity store.
    Raises ValueError on any failure.
    """
    path = dossier_file(store_id)
    if not path.exists():
        raise ValueError("root_dossier_missing")

    dossier = json.loads(path.read_text())

    # 1. store_id matches directory
    if dossier.get("store_id") != store_id:
        raise ValueError("root_dossier_store_id_mismatch")

    # 2. schema_version is known
    schema_version = dossier.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError("root_dossier_schema_version_unsupported")

    # 3. identity block exists
    identity = dossier.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("root_dossier_missing_identity_block")

    # 4. identity_fingerprint matches unified fingerprint
    expected_fp = build_identity_fingerprint_v1(store_id)
    if identity.get("identity_fingerprint") != expected_fp:
        raise ValueError("root_dossier_identity_fingerprint_mismatch")

    # 4b. public_key matches disk (raw bytes → base64)
    public_key_bytes = public_key_file(store_id).read_bytes()
    expected_b64 = base64.b64encode(public_key_bytes).decode()

    if identity.get("public_key_b64") != expected_b64:
        raise ValueError("root_dossier_public_key_mismatch")

    # 5. signature verifies over canonical dossier (minus signature)
    sig_b64 = dossier.get("signature")
    if not sig_b64:
        raise ValueError("root_dossier_missing_signature")

    dossier_copy = dict(dossier)
    dossier_copy.pop("signature", None)
    canonical = canonical_json(dossier_copy)

    # Decode signature
    try:
        sig_bytes = base64.b64decode(sig_b64)
    except Exception:
        raise ValueError("root_dossier_signature_invalid_base64")

    # Verify using raw public key bytes
    if not verify_b64(public_key_bytes, canonical, sig_b64):
        raise ValueError("root_dossier_signature_verification_failed")

