# keypair.py

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


def generate_keypair():
    """
    Generate a raw Ed25519 keypair and return (private_bytes, public_bytes).
    Both are 32 bytes long.
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Raw 32-byte private key
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Raw 32-byte public key
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    return private_bytes, public_bytes
