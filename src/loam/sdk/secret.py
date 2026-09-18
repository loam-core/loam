# loam/sdk/secrets.py

from typing import Any


class Secrets:
    """
    High-level wrapper for secret_use operations.
    """

    def __init__(self, agent):
        self._agent = agent

    def use(self, name: str, op: str, payload: bytes) -> Any:
        """Return type depends on `op`: see hmac/sign/encrypt (str) vs decrypt (bytes)."""
        return self._agent.secret_use(name, op, payload)

    def hmac(self, name: str, payload: bytes) -> str:
        return self._agent.secret_hmac(name, payload)

    def sign(self, name: str, payload: bytes) -> str:
        return self._agent.secret_sign(name, payload)

    def encrypt(self, name: str, plaintext: bytes) -> str:
        return self._agent.secret_encrypt(name, plaintext)

    def decrypt(self, name: str, ciphertext: bytes) -> bytes:
        return self._agent.secret_decrypt(name, ciphertext)
