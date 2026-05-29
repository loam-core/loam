# loam/sdk/secrets.py

class Secrets:
    """
    High-level wrapper for secret_use operations.
    """

    def __init__(self, agent):
        self._agent = agent

    def use(self, name: str, op: str, payload: bytes):
        return self._agent.secret_use(name, op, payload)

    def hmac(self, name: str, payload: bytes):
        return self._agent.secret_hmac(name, payload)

    def sign(self, name: str, payload: bytes):
        return self._agent.secret_sign(name, payload)

    def encrypt(self, name: str, plaintext: bytes):
        return self._agent.secret_encrypt(name, plaintext)

    def decrypt(self, name: str, ciphertext: bytes):
        return self._agent.secret_decrypt(name, ciphertext)
