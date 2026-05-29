#secret_key.py

import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_secret(secret_key: bytes, plaintext: bytes) -> bytes:
    """
    Encrypt plaintext using AES-GCM with the given secret_key.

    Returns: nonce + ciphertext (as bytes).
    """
    aesgcm = AESGCM(secret_key)

    # 12-byte nonce is standard for AES-GCM
    nonce = os.urandom(12)

    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)

    # Store nonce + ciphertext together
    return nonce + ciphertext


def decrypt_secret(secret_key: bytes, data: bytes) -> bytes:
    """
    Decrypt data produced by encrypt_secret.

    Expects: nonce (12 bytes) + ciphertext
    Returns: plaintext bytes.
    """
    aesgcm = AESGCM(secret_key)

    nonce = data[:12]
    ciphertext = data[12:]

    plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    return plaintext
