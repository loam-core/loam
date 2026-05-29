import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from loam.crypto.canonical import canonical_json



class Signer:
    def get_private_key_bytes(self) -> bytes:
        raise NotImplementedError

# -------------------------
# Raw Key Loading
# -------------------------

def load_private_key(private_key_bytes: bytes) -> Ed25519PrivateKey:
    """
    Load an Ed25519 private key from raw 32-byte seed.
    """
    return Ed25519PrivateKey.from_private_bytes(private_key_bytes)


def load_public_key(public_key_bytes: bytes) -> Ed25519PublicKey:
    """
    Load an Ed25519 public key from raw 32-byte bytes.
    """
    return Ed25519PublicKey.from_public_bytes(public_key_bytes)


# -------------------------
# Raw Signing + Verification
# -------------------------

def sign(private_key_bytes: bytes, message_bytes: bytes) -> bytes:
    """
    Sign raw message bytes using Ed25519.
    Returns raw signature bytes.
    """
    key = load_private_key(private_key_bytes)
    return key.sign(message_bytes)


def verify(public_key_bytes: bytes, message_bytes: bytes, signature_bytes: bytes) -> bool:
    """
    Verify a raw signature (bytes) for raw message bytes.
    Returns True if valid, False otherwise.
    """
    key = load_public_key(public_key_bytes)
    try:
        key.verify(signature_bytes, message_bytes)
        return True
    except Exception:
        return False


# -------------------------
# Base64 Helpers
# -------------------------

def sign_b64(private_key_bytes: bytes, message_bytes: bytes) -> str:
    sig = sign(private_key_bytes, message_bytes)
    return base64.b64encode(sig).decode()


def verify_b64(public_key_bytes: bytes, message_bytes: bytes, signature_b64: str) -> bool:
    try:
        sig = base64.b64decode(signature_b64)
    except Exception:
        return False
    return verify(public_key_bytes, message_bytes, sig)


# -------------------------
# Hashing
# -------------------------

def hash_payload(payload: dict) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()
