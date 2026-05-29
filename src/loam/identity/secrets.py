#identity/secrets.py

"""
The identity layer owns encrypted secrets and the private key.

The shim (Layer 1 execution) is responsible for:
    - decrypting secrets on demand
    - enforcing physics (layer, simulation)
    - enforcing continuity and chronicle
    - mounting secrets into a temporary directory for tools
    - ensuring secrets never persist on disk beyond execution

The agent (user code) never sees the private key and never decrypts secrets directly.
"""

import os
import json
import hmac
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from base64 import b64encode, b64decode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Identity-layer imports
from loam.identity.master_key import load_master_key
from loam.identity.revocation import check_revocation
from loam.identity.keysources import KeySourceContext, load_signer_from_keysource
from loam.identity.identity_fingerprint import build_identity_fingerprint_v1
from loam.identity.secret_key import encrypt_secret, decrypt_secret
from loam.identity.paths import (
    store_path,
    secrets_dir,
    secret_file,
)

from loam.identity.folder_verifier import verify_identity_folder

# Crypto imports
from loam.crypto.signing import (
    verify_b64,
)
from loam.crypto.canonical import canonical_json

# Trust pipeline
from loam.continuity.append import load_last_record
from loam.continuity.verify import verify_chain
from loam.chronicle.verify import verify_chronicle
from loam.chronicle.chronicle import append_chronicle_entry


# ============================================================
# Chronicle helper (operator-plane, Layer 0)
# ============================================================

def chronicle_log(store_id: str, event_type: str, payload: dict | None = None, *, ksctx: KeySourceContext):
    """
    Emit a canonical Chronicle v1 event from the operator plane.
    This mirrors the shim's Chronicle emitter but is used for
    identity/secrets operations performed directly by operators.
    """
    if payload is None:
        payload = {}

    # Load signer for this identity
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)

    # Identity fingerprint (full, not hash)
    identity_fp = build_identity_fingerprint_v1(store_id)

    # continuity_seq is not tracked in identity layer; we read it
    head = load_last_record(store_id)
    continuity_seq = head["seq"] if head else None

    # Canonical Chronicle v1 envelope
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": event_type,
        "store_id": store_id,
        "identity_fingerprint": identity_fp,
        "continuity_seq": continuity_seq,
        "payload": payload,
    }

    # Append via Chronicle writer (adds prev_event_hash, event_hash, signature)
    append_chronicle_entry(store_id, event, signer)


# ============================================================
# Secret envelope creation
# ============================================================

def secret_create(store_id: str, name: str, value: str, *, ksctx: KeySourceContext):
    """
    Create a new encrypted secret envelope.
    """
    check_revocation(store_id)

    # 1. Per-secret symmetric key
    sym_key = os.urandom(32)

    # 2. Encrypt plaintext
    plaintext_bytes = value.encode("utf-8")
    aes_payload = encrypt_secret(sym_key, plaintext_bytes)
    nonce = aes_payload[:12]
    ciphertext = aes_payload[12:]

    # 3. Wrap symmetric key with master key
    master_key = load_master_key(store_id, ksctx=ksctx)
    aesgcm_wrap = AESGCM(master_key)
    nonce_wrap = os.urandom(12)
    wrapped_key = nonce_wrap + aesgcm_wrap.encrypt(nonce_wrap, sym_key, None)

    # 4. Build envelope
    envelope = {
        "name": name,
        "store_id": store_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "wrapped_key": b64encode(wrapped_key).decode("ascii"),
        "ciphertext": b64encode(ciphertext).decode("ascii"),
        "nonce": b64encode(nonce).decode("ascii"),
    }

    # 5. Sign envelope with identity signer
    to_sign = dict(envelope)
    to_sign.pop("signature", None)
    canonical = canonical_json(to_sign)

    signer = load_signer_from_keysource(store_id, ksctx=ksctx)
    signature_b64 = b64encode(signer.sign(canonical)).decode("ascii")
    envelope["signature"] = signature_b64

    # 6. Write to disk
    path = secret_file(store_id, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2))

    # 7. Chronicle
    chronicle_log(store_id, "secret_created", {"name": name}, ksctx=ksctx)


# ============================================================
# Secret loading (decrypt one)
# ============================================================

def secret_load(store_id: str, name: str, *, ksctx: KeySourceContext):
    """
    Load and decrypt a single secret envelope.
    """
    check_revocation(store_id)

    path = secret_file(store_id, name)
    if not path.exists():
        raise FileNotFoundError(f"Secret '{name}' not found")

    envelope = json.loads(path.read_text())

    # Identity binding
    if envelope["store_id"] != store_id:
        raise ValueError("Secret does not belong to this store")

    # Trust pipeline
    if not verify_chain(store_id):
        raise RuntimeError("Continuity_invalid")
    verify_chronicle(store_id)
    ok, err = verify_identity_folder(store_id)
    if not ok:
        raise RuntimeError(f"identity_folder_invalid: {err}")

    # Signature verification (done BEFORE decryption)
    sig_b64 = envelope.get("signature")
    if not sig_b64:
        raise RuntimeError("missing_secret_signature")

    # Build canonical signing body
    to_verify = dict(envelope)
    to_verify.pop("signature", None)
    canonical = canonical_json(to_verify)

    # Verify signature using identity signer
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)
    pub_bytes = signer.get_public_key()
    ok = verify_b64(pub_bytes, canonical, sig_b64)
    if not ok:
        raise RuntimeError("secret_signature_invalid")

    try:
        # Unwrap symmetric key
        master_key = load_master_key(store_id, ksctx=ksctx)
        aesgcm_wrap = AESGCM(master_key)

        wrapped = b64decode(envelope["wrapped_key"])
        nonce_wrap, ciphertext_wrap = wrapped[:12], wrapped[12:]
        sym_key = aesgcm_wrap.decrypt(nonce_wrap, ciphertext_wrap, None)

        # Decrypt ciphertext
        nonce = b64decode(envelope["nonce"])
        ciphertext = b64decode(envelope["ciphertext"])
        aes_payload = nonce + ciphertext
        plaintext_bytes = decrypt_secret(sym_key, aes_payload)
        plaintext = plaintext_bytes.decode("utf-8")

    except Exception as e:
        chronicle_log(store_id, "secret_load_failed", {"name": name, "error": str(e)}, ksctx=ksctx)
        raise

    chronicle_log(store_id, "secret_load_succeeded", {"name": name}, ksctx=ksctx)
    return plaintext


# ============================================================
# Safe secret loading 
# ============================================================

def secret_hmac(store_id: str, name: str, payload: bytes, *, ksctx: KeySourceContext) -> str:
    """
    Compute HMAC-SHA256(payload) using the named secret.
    Returns base64-encoded HMAC. Secret never leaves substrate.
    """
    key = secret_load(store_id, name, ksctx=ksctx)  # plaintext, but stays inside substrate
    key_bytes = key.encode("utf-8")

    mac = hmac.new(key_bytes, payload, hashlib.sha256).digest()
    return b64encode(mac).decode("ascii")


def secret_sign(store_id: str, name: str, payload: bytes, *, ksctx: KeySourceContext) -> str:
    key_bytes = secret_load(store_id, name, ksctx=ksctx).encode("utf-8")
    # Here the secret itself is an Ed25519 private key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private_key = Ed25519PrivateKey.from_private_bytes(key_bytes)
    sig = private_key.sign(payload)
    return b64encode(sig).decode("ascii")


def secret_encrypt(store_id: str, name: str, plaintext: bytes, *, ksctx: KeySourceContext) -> str:
    key_bytes = secret_load(store_id, name, ksctx=ksctx).encode("utf-8")
    aes = AESGCM(key_bytes)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext, None)
    return b64encode(nonce + ct).decode("ascii")


def secret_decrypt(store_id: str, name: str, ciphertext_b64: str, *, ksctx: KeySourceContext) -> bytes:
    key_bytes = secret_load(store_id, name, ksctx=ksctx).encode("utf-8")
    aes = AESGCM(key_bytes)
    blob = b64decode(ciphertext_b64)
    nonce, ct = blob[:12], blob[12:]
    return aes.decrypt(nonce, ct, None)


SECRET_OPERATIONS = {
    "hmac": secret_hmac,
    "sign": secret_sign,
    "encrypt": secret_encrypt,
    "decrypt": secret_decrypt,
}


# ============================================================
# Listing (metadata only)
# ============================================================

def secret_list(store_id: str):
    """
    List secrets without revealing values.
    Returns a list of metadata dicts.
    """
    sdir = secrets_dir(store_id)
    sdir.mkdir(parents=True, exist_ok=True)

    results = []
    for filename in os.listdir(sdir):
        # Only load secret envelopes, not metadata
        if not filename.endswith(".json"):
            continue
        if filename == "usage.json":
            continue

        path = sdir / filename
        try:
            envelope = json.loads(path.read_text())
        except Exception:
            continue  # skip malformed or non-envelope JSON

        # Only treat files with secret envelope fields as secrets
        if "store_id" not in envelope or "name" not in envelope:
            continue

        if envelope["store_id"] != store_id:
            continue

        results.append({
            "name": envelope["name"],
            "created_at": envelope["created_at"],
        })

    return results


# ============================================================
# Secret rotation (overwrite existing)
# ============================================================

def secret_rotate(store_id: str, name: str, new_value: str, *, ksctx: KeySourceContext) -> None:
    """
    Rotate an existing secret by overwriting its encrypted envelope.
    """
    path = secret_file(store_id, name)
    if not path.exists():
        raise FileNotFoundError(f"Secret '{name}' does not exist")

    # Reuse secret_create to overwrite the envelope
    secret_create(store_id, name, new_value, ksctx=ksctx)

    chronicle_log(store_id, "secret_rotated", {"name": name}, ksctx=ksctx)


# ============================================================
# Secret deletion
# ============================================================

def secret_delete(store_id: str, name: str, *, ksctx: KeySourceContext) -> None:
    """
    Delete a secret envelope entirely.
    """
    path = secret_file(store_id, name)
    if not path.exists():
        raise FileNotFoundError(f"Secret '{name}' does not exist")

    path.unlink()

    chronicle_log(store_id, "secret_deleted", {"name": name}, ksctx=ksctx)
