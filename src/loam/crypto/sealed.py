# loam/crypto/sealed.py
#
# Symmetric sealed‑blob encryption for export/import.
# Uses:
#   - scrypt (KDF) to derive a key from a passphrase
#   - AES‑GCM for authenticated encryption
#   - base64 for portable JSON encoding
#
# This module is intentionally small, boring, and self contained.
# It does NOT depend on identity, continuity, or secrets subsystem.

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Literal

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ---------------------------------------------------------------------------
# Sealed blob structure
# ---------------------------------------------------------------------------

@dataclass
class SealedBlob:
    """
    Portable sealed blob format for encrypted payloads.

    All fields are base64‑encoded so the blob can be serialized as JSON.
    """
    kdf: Literal["scrypt"]
    cipher: Literal["aes-gcm"]
    salt: str        # base64
    nonce: str       # base64
    ciphertext: str  # base64


# ---------------------------------------------------------------------------
# Key derivation (scrypt)
# ---------------------------------------------------------------------------

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """
    Derive a 256‑bit key from a UTF‑8 passphrase using scrypt.
    """
    kdf = Scrypt(
        salt=salt,
        length=32,     # AES‑256
        n=2**14,
        r=8,
        p=1,
    )
    return kdf.derive(passphrase.encode("utf-8"))


# ---------------------------------------------------------------------------
# Seal (encrypt)
# ---------------------------------------------------------------------------

def seal_bytes(plaintext: bytes, passphrase: str) -> SealedBlob:
    """
    Encrypt plaintext bytes using AES‑GCM with a passphrase‑derived key.
    Returns a SealedBlob suitable for JSON serialization.
    """
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    nonce = os.urandom(12)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)

    return SealedBlob(
        kdf="scrypt",
        cipher="aes-gcm",
        salt=base64.b64encode(salt).decode("ascii"),
        nonce=base64.b64encode(nonce).decode("ascii"),
        ciphertext=base64.b64encode(ciphertext).decode("ascii"),
    )


# ---------------------------------------------------------------------------
# Unseal (decrypt)
# ---------------------------------------------------------------------------

def unseal_bytes(blob: SealedBlob, passphrase: str) -> bytes:
    """
    Decrypt a SealedBlob using the provided passphrase.
    Returns the original plaintext bytes.
    """
    if blob.kdf != "scrypt" or blob.cipher != "aes-gcm":
        raise RuntimeError("unsupported_sealed_blob_format")

    salt = base64.b64decode(blob.salt)
    nonce = base64.b64decode(blob.nonce)
    ciphertext = base64.b64decode(blob.ciphertext)

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)

    return aesgcm.decrypt(nonce, ciphertext, associated_data=None)

