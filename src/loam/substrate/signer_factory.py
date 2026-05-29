# loam/substrate/signer_factory.py

from __future__ import annotations

from typing import Any

from loam.identity.keysources import KeySourceContext, load_signer_from_keysource
from .signer import Signer


def create_signer(config: dict[str, Any], *, ksctx: KeySourceContext) -> Signer:
    """
    Substrate-facing signer factory.

    This is now just a thin shim over the identity KeySource system.
    The only thing we care about here is: which store_id are we signing as?
    """
    if not isinstance(config, dict):
        raise TypeError("create_signer expects a dict config")

    store_id = config.get("store_id")
    if not store_id:
        raise ValueError("create_signer requires 'store_id' in config")

    # Delegate to the real identity-plane signer loader
    return load_signer_from_keysource(store_id, ksctx=ksctx)


