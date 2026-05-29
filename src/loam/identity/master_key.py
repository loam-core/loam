# loam/identity/master_key.py

import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from loam.crypto.crypto import derive_key_from_passphrase
from loam.identity.keysources import (
    KeySourceContext,
    load_keysource_descriptor,
    load_signer_from_keysource,
)
from loam.identity.paths import (
    keys_dir,
    master_key_file,
    master_key_sig_file,
    secrets_dir,
)

MASTER_KEY_LENGTH = 32  # 256-bit symmetric key
ENCRYPTED_MASTER_KEY_NAME = "master_key.enc"


# ============================================================
# Identity Signer / Verifier (via KeySource)
# ============================================================

def _load_identity_signer(store_id: str, ksctx: KeySourceContext):
    """
    Load the identity's signer abstraction via KeySource.
    Works for plaintext, encrypted, KMS, TPM, agent, etc.
    """
    return load_signer_from_keysource(store_id, ksctx=ksctx)


def _load_identity_verifier(store_id: str, ksctx: KeySourceContext):
    """
    Load the identity's public key via the signer abstraction.
    """
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)
    return signer.get_public_key()


# ============================================================
# Master Key Generation (plaintext + encrypted)
# ============================================================

def generate_master_key(store_id: str, *, ksctx: KeySourceContext) -> bytes:
    """
    Create a new master key. For plaintext identities, store it as raw bytes + signature.
    For passphrase-encrypted identities, encrypt it with the passphrase-derived key.
    """
    ks = load_keysource_descriptor(store_id)
    kind = ks.get("kind")

    if kind == "raw_ed25519":
        # NOTE: plaintext issuance still supported
        return _generate_master_key_plaintext(store_id, ksctx)

    elif kind == "passphrase_encrypted":
        passphrase = ksctx.passphrase
        if passphrase is None:
            raise ValueError("Passphrase required to generate encrypted master key")
        return _generate_master_key_encrypted(store_id, ks, ksctx)

    else:
        raise ValueError(f"Unsupported KeySource kind for master key generation: {kind}")


def _generate_master_key_plaintext(store_id: str, ksctx: KeySourceContext) -> bytes:
    """
    Generate a plaintext master key and sign it with the identity signer.
    """
    key_path = master_key_file(store_id)
    sig_path = master_key_sig_file(store_id)

    key_path.parent.mkdir(parents=True, exist_ok=True)

    signer = load_signer_from_keysource(store_id, ksctx=ksctx)

    master_key = os.urandom(MASTER_KEY_LENGTH)

    key_path.write_bytes(master_key)

    signature = signer.sign(master_key)
    sig_path.write_bytes(signature)

    return master_key


def _generate_master_key_encrypted(store_id: str, ks: dict, ksctx: KeySourceContext) -> bytes:
    """
    Generate a new master key and encrypt it using the passphrase,
    using the JSON self-describing format and the identity's KDF config.
    """
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)

    passphrase = ksctx.passphrase
    if passphrase is None:
        raise ValueError("Passphrase required to generate encrypted master key")

    master_key = os.urandom(MASTER_KEY_LENGTH)

    kdf_info = ks["kdf"]  # reuse the identity's KDF config

    blob_text = _encrypt_master_key_to_json_blob(master_key, passphrase, kdf_info)
    blob_bytes = blob_text.encode("utf-8")

    signature = signer.sign(blob_bytes)

    enc_path = secrets_dir(store_id) / ENCRYPTED_MASTER_KEY_NAME
    sig_path = master_key_sig_file(store_id)

    enc_path.write_text(blob_text)
    sig_path.write_bytes(signature)

    return master_key




# ============================================================
# Master Key Loading (plaintext + encrypted)
# ============================================================

def load_master_key(store_id: str, *, ksctx: KeySourceContext) -> bytes:
    """
    Load the master key using the unified KeySourceContext.
    This replaces the old passphrase-based API.
    """
    ks = load_keysource_descriptor(store_id)
    kind = ks.get("kind")

    if kind == "raw_ed25519":
        return _load_master_key_plaintext(store_id, ksctx)

    elif kind == "passphrase_encrypted":
        return _load_master_key_encrypted(store_id, ks, ksctx)

    else:
        raise ValueError(f"Unsupported KeySource kind for master key loading: {kind}")


def _load_master_key_plaintext(store_id: str, ksctx: KeySourceContext) -> bytes:
    """
    Load a plaintext master key and verify its signature.
    """
    key_path = master_key_file(store_id)
    sig_path = master_key_sig_file(store_id)

    if not key_path.exists() or not sig_path.exists():
        raise RuntimeError("master_key_or_signature_missing")

    master_key = key_path.read_bytes()
    signature = sig_path.read_bytes()

    signer = load_signer_from_keysource(store_id, ksctx=ksctx)
    pub = signer.get_public_key()

    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(signature, master_key)
    except Exception as e:
        raise RuntimeError(f"invalid_master_key_signature: {e}")

    return master_key


def _load_master_key_encrypted(store_id: str, ks: dict, ksctx: KeySourceContext) -> bytes:
    """
    Load and decrypt a JSON-format encrypted master key.
    """
    passphrase = ksctx.passphrase
    if passphrase is None:
        raise ValueError("Passphrase required to decrypt master key")

    enc_path = secrets_dir(store_id) / ENCRYPTED_MASTER_KEY_NAME
    sig_path = master_key_sig_file(store_id)

    if not enc_path.exists() or not sig_path.exists():
        raise RuntimeError("encrypted_master_key_or_signature_missing")

    blob_text = enc_path.read_text()
    blob_bytes = blob_text.encode("utf-8")

    # Verify signature over the JSON blob
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)
    pub = signer.get_public_key()
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(
            sig_path.read_bytes(), blob_bytes
        )
    except Exception as e:
        raise RuntimeError(f"invalid_master_key_signature: {e}")

    # Decrypt using JSON metadata
    try:
        master_key = _decrypt_master_key_from_json_blob(blob_text, passphrase)
    except Exception as e:
        raise RuntimeError(f"failed_to_decrypt_master_key: {e}")

    return master_key



# ============================================================
# Migration Helpers (plaintext ↔ encrypted)
# ============================================================


def _encrypt_master_key_to_json_blob(
    master_key: bytes,
    passphrase: str,
    kdf_info: dict,
) -> str:
    key = derive_key_from_passphrase(passphrase, kdf_info)

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, master_key, None)

    blob = {
        "version": 1,
        "kdf": kdf_info,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ct).decode("ascii"),
    }

    return json.dumps(blob, separators=(",", ":"))




def _decrypt_master_key_from_json_blob(blob_text: str, passphrase: str) -> bytes:
    blob = json.loads(blob_text)

    if blob.get("version") != 1:
        raise RuntimeError(f"unsupported_master_key_blob_version: {blob.get('version')}")

    kdf_info = blob["kdf"]
    nonce = base64.b64decode(blob["nonce"])
    ct = base64.b64decode(blob["ciphertext"])

    key = derive_key_from_passphrase(passphrase, kdf_info)
    aesgcm = AESGCM(key)

    return aesgcm.decrypt(nonce, ct, None)


def migrate_master_key_to_passphrase(store_id: str, passphrase: str) -> None:
    mk_path = master_key_file(store_id)
    if not mk_path.exists():
        raise FileNotFoundError("Plaintext master key not found")

    master_key = mk_path.read_bytes()

    # Load identity descriptor so we can reuse its KDF config
    ks = load_keysource_descriptor(store_id)
    kdf_info = ks["kdf"]

    enc_path = secrets_dir(store_id) / ENCRYPTED_MASTER_KEY_NAME
    enc_path.parent.mkdir(parents=True, exist_ok=True)

    # NEW: pass kdf_info explicitly
    blob_text = _encrypt_master_key_to_json_blob(master_key, passphrase, kdf_info)
    enc_path.write_text(blob_text)

    # Re-sign the encrypted blob
    signer = load_signer_from_keysource(store_id, ksctx=KeySourceContext(passphrase=passphrase))
    signature = signer.sign(blob_text.encode("utf-8"))
    master_key_sig_file(store_id).write_bytes(signature)

    mk_path.unlink()




def migrate_master_key_to_plaintext(store_id: str, passphrase: str) -> None:
    enc_path = secrets_dir(store_id) / ENCRYPTED_MASTER_KEY_NAME
    if not enc_path.exists():
        raise FileNotFoundError("Encrypted master key not found")

    blob_text = enc_path.read_text()
    master_key = _decrypt_master_key_from_json_blob(blob_text, passphrase)

    mk_path = master_key_file(store_id)
    mk_path.parent.mkdir(parents=True, exist_ok=True)
    mk_path.write_bytes(master_key)

    signer = load_signer_from_keysource(store_id, ksctx=KeySourceContext(passphrase=passphrase))
    signature = signer.sign(master_key)
    master_key_sig_file(store_id).write_bytes(signature)

    enc_path.unlink()


def master_key_plaintext_exists(store_id: str) -> bool:
    return master_key_file(store_id).exists()


def master_key_encrypted_exists(store_id: str) -> bool:
    return (secrets_dir(store_id) / ENCRYPTED_MASTER_KEY_NAME).exists()

