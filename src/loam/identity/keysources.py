from __future__ import annotations

import getpass
import os
import json
import base64
from pathlib import Path
from typing import Any, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from loam.cli.session import get_cached_passphrase
from loam.crypto.crypto import derive_key_from_passphrase, make_kdf_info_scrypt
from loam.identity.paths import keys_dir, private_key_file, secrets_dir, master_key_file

# ============================================================
# Constants
# ============================================================

KEY_DESCRIPTOR_NAME = "key_descriptor.json"
ENCRYPTED_MASTER_KEY_NAME = "master_key.enc"


# ============================================================
# Signer Protocol
# ============================================================

class Signer(Protocol):
    def sign(self, data: bytes) -> bytes: ...
    def get_public_key(self) -> bytes: ...
    def verify(self, payload: bytes, signature: bytes) -> bool: ...
    def get_private_key_bytes(self) -> bytes: ...


# ============================================================
# KeySourceContext
# ============================================================

class KeySourceContext:
    """
    Opaque container for all KeySource-specific parameters.
    Runtime constructs this once and passes it downward.
    KeySources pull what they need from it.
    """
    def __init__(self, *, passphrase=None, kms=None, tpm=None, agent=None):
        self.passphrase = passphrase
        self.kms = kms
        self.tpm = tpm
        self.agent = agent

    def require(self, field: str):
        val = getattr(self, field)
        if val is None:
            raise ValueError(f"KeySource requires '{field}' but it was not provided.")
        return val


# ============================================================
# Descriptor Helpers
# ============================================================

def _key_descriptor_path(store_id: str) -> Path:
    return keys_dir(store_id) / KEY_DESCRIPTOR_NAME


def load_keysource_descriptor(store_id: str) -> dict[str, Any]:
    path = _key_descriptor_path(store_id)
    if not path.exists():
        raise FileNotFoundError(f"Key descriptor not found for store {store_id}: {path}")
    return json.loads(path.read_text())


# ============================================================
# Signer Dispatcher
# ============================================================

def load_signer_from_keysource(store_id: str, *, ksctx: KeySourceContext) -> Signer:
    ks = load_keysource_descriptor(store_id)

    kind = ks.get("kind")
    if not kind:
        raise ValueError(f"KeySource descriptor missing 'kind' for store {store_id}")

    if kind == "raw_ed25519":
        return _signer_raw_ed25519(store_id, ks, ksctx)

    if kind == "passphrase_encrypted":
        return _signer_passphrase_encrypted(store_id, ks, ksctx)

    if kind == "kms":
        return _signer_kms(store_id, ks, ksctx)

    if kind == "agent":
        return _signer_agent(store_id, ks, ksctx)

    if kind == "custom":
        return _signer_custom(store_id, ks, ksctx)

    if kind == "webcrypto":
        return _signer_webcrypto(store_id, ks, ksctx)

    raise ValueError(f"Unknown KeySource kind '{kind}' for store {store_id}")


# ============================================================
# KeySource Handlers
# ============================================================

# -------------------------
# raw_ed25519
# -------------------------

def _signer_raw_ed25519(store_id: str, ks: dict[str, Any], ksctx) -> Signer:
    rel_path = ks.get("path") or "private_key"
    priv_path = keys_dir(store_id) / rel_path

    if not priv_path.exists():
        raise FileNotFoundError(f"Raw Ed25519 private key not found: {priv_path}")

    raw = priv_path.read_bytes()
    priv = Ed25519PrivateKey.from_private_bytes(raw)
    pub = priv.public_key()

    class _RawEd25519Signer(Signer):
        def sign(self, data: bytes) -> bytes:
            return priv.sign(data)

        def get_public_key(self) -> bytes:
            return pub.public_bytes_raw()

        def verify(self, payload: bytes, signature: bytes) -> bool:
            try:
                pub.verify(signature, payload)
                return True
            except Exception:
                return False

        def get_private_key_bytes(self) -> bytes:
            return priv.private_bytes_raw()

    return _RawEd25519Signer()


# -------------------------
# passphrase_encrypted
# -------------------------

_passphrase_cache: dict[str, str] = {}

def get_passphrase_for_store(store_id: str) -> str:
    if store_id in _passphrase_cache:
        return _passphrase_cache[store_id]

    cached = get_cached_passphrase(store_id)
    if cached is not None:
        _passphrase_cache[store_id] = cached
        return cached

    pw = getpass.getpass(f"Passphrase for identity {store_id}: ")
    _passphrase_cache[store_id] = pw
    return pw


def _signer_passphrase_encrypted(store_id: str, ks: dict[str, Any], ksctx) -> Signer:
    passphrase = ksctx.passphrase
    if passphrase is None:
        passphrase = get_passphrase_for_store(store_id)
        ksctx.passphrase = passphrase

    if passphrase is None:
        raise ValueError("Passphrase required for passphrase_encrypted KeySource")

    rel_path = ks.get("path") or "private_key.enc"
    enc_path = keys_dir(store_id) / rel_path

    if not enc_path.exists():
        raise FileNotFoundError(f"Encrypted Ed25519 private key not found: {enc_path}")

    blob = enc_path.read_bytes()
    if len(blob) < 12 + 16:
        raise ValueError(f"Encrypted private key blob too short: {enc_path}")

    nonce = blob[:12]
    ct_and_tag = blob[12:]

    kdf_info = ks.get("kdf")
    if not kdf_info:
        raise ValueError("Missing 'kdf' info in KeySource descriptor for passphrase_encrypted key")

    key = derive_key_from_passphrase(passphrase, kdf_info)
    aesgcm = AESGCM(key)

    try:
        priv_bytes = aesgcm.decrypt(nonce, ct_and_tag, None)
    except Exception as e:
        raise ValueError(f"Failed to decrypt private key: {e}")

    priv = Ed25519PrivateKey.from_private_bytes(priv_bytes)
    pub = priv.public_key()

    class _PassphraseEd25519Signer(Signer):
        def sign(self, data: bytes) -> bytes:
            return priv.sign(data)

        def get_public_key(self) -> bytes:
            return pub.public_bytes_raw()

        def verify(self, payload: bytes, signature: bytes) -> bool:
            try:
                pub.verify(signature, payload)
                return True
            except Exception:
                return False

        def get_private_key_bytes(self) -> bytes:
            return priv.private_bytes_raw()

    return _PassphraseEd25519Signer()


# -------------------------
# Unimplemented KeySources
# -------------------------

def _signer_kms(store_id: str, ks: dict[str, Any], ksctx) -> Signer:
    raise NotImplementedError("kms KeySource not implemented yet")


def _signer_agent(store_id: str, ks: dict[str, Any], ksctx) -> Signer:
    raise NotImplementedError("agent KeySource not implemented yet")


def _signer_custom(store_id: str, ks: dict[str, Any], ksctx) -> Signer:
    raise NotImplementedError("custom KeySource not implemented yet")


def _signer_webcrypto(store_id: str, ks: dict[str, Any], ksctx) -> Signer:
    raise NotImplementedError("webcrypto KeySource not implemented yet")


# ============================================================
# Encryption Helper
# ============================================================

def encrypt_private_key_with_passphrase(
    store_id: str,
    private_bytes: bytes,
    passphrase: str,
) -> dict[str, Any]:
    kdf_info = make_kdf_info_scrypt()
    key = derive_key_from_passphrase(passphrase, kdf_info)

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, private_bytes, None)
    blob = nonce + ciphertext

    enc_path = keys_dir(store_id) / "private_key.enc"
    enc_path.parent.mkdir(parents=True, exist_ok=True)
    enc_path.write_bytes(blob)

    descriptor = {
        "version": 1,
        "kind": "passphrase_encrypted",
        "path": "private_key.enc",
        "store_id": store_id,
        "kdf": kdf_info,
    }

    descriptor_path = _key_descriptor_path(store_id)
    descriptor_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor_path.write_text(json.dumps(descriptor, indent=2))

    return descriptor


# ============================================================
# Migration Helpers
# ============================================================

def migrate_plaintext_to_passphrase(store_id: str, passphrase: str) -> None:
    ks = load_keysource_descriptor(store_id)
    if ks.get("kind") != "raw_ed25519":
        raise ValueError(f"Cannot migrate non-plaintext KeySource for store {store_id}")

    rel_path = ks.get("path") or "private_key"
    priv_path = keys_dir(store_id) / rel_path
    if not priv_path.exists():
        raise FileNotFoundError(f"Plaintext private key not found: {priv_path}")

    private_bytes = priv_path.read_bytes()

    descriptor = encrypt_private_key_with_passphrase(store_id, private_bytes, passphrase)

    priv_path.unlink()

    descriptor_path = _key_descriptor_path(store_id)
    descriptor_path.write_text(json.dumps(descriptor, indent=2))


def migrate_passphrase_to_plaintext(store_id: str, passphrase: str) -> None:
    ks = load_keysource_descriptor(store_id)
    if ks.get("kind") != "passphrase_encrypted":
        raise ValueError(f"Cannot decrypt non-encrypted KeySource for store {store_id}")

    ksctx = KeySourceContext(passphrase=passphrase)
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)

    priv_bytes = signer.get_private_key_bytes()

    private_key_file(store_id).write_bytes(priv_bytes)

    descriptor = {
        "version": 1,
        "kind": "raw_ed25519",
        "path": "private_key",
        "store_id": store_id,
    }

    descriptor_path = _key_descriptor_path(store_id)
    descriptor_path.write_text(json.dumps(descriptor, indent=2))

    enc_path = keys_dir(store_id) / "private_key.enc"
    if enc_path.exists():
        enc_path.unlink()
