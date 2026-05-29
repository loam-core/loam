# loam/identity/identity_fingerprint.py

import hashlib
from loam.identity.paths import public_key_file


def build_identity_fingerprint_v1(store_id: str) -> str:
    """
    Identity fingerprint = sha256(public_key_bytes)
    """
    pub_bytes = public_key_file(store_id).read_bytes()
    return hashlib.sha256(pub_bytes).hexdigest()


def compute_identity_fingerprint_hash_v1(fingerprint: str) -> str:
    """
    Hash of the identity fingerprint string.
    Used in continuity records.
    """
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


