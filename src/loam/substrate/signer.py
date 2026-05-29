# substrate/signer.py

'''
The Signer abstraction intentionally does not know about identity, store_id,
identity_fingerprint, or dossier semantics. It only exposes raw signing and
verification primitives for the shim.
'''

from abc import ABC, abstractmethod

class Signer(ABC):
    """
    Abstract signer interface.
    The shim uses this to sign events without knowing where the private key lives.
    """

    @abstractmethod
    def sign(self, payload: bytes) -> bytes:
        """Return a signature over the given payload."""
        raise NotImplementedError

    @abstractmethod
    def get_public_key(self) -> bytes:
        """Return the public key bytes."""
        raise NotImplementedError

    @abstractmethod
    def verify(self, payload: bytes, signature: bytes) -> bool:
        """Return True if the signature is valid for the payload."""
        raise NotImplementedError
