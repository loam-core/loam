# loam/continuity/witness.py

from typing import Optional


def witness_enabled() -> bool:
    """
    Witnessing is disabled in v0.1.
    Future versions may enable this via config, Calyx, or governance bindings.
    """
    return False


def witness_publish(
    store_id: str,
    head_seq: int,
    head_hash: str,
    state_hash: Optional[str],
) -> None:
    """
    Publish the current continuity head to a remote or local witness.

    This is a no-op stub for v0.1.
    Future implementations may:
      - push to Calyx
      - push to a governance quorum
      - push to a witness mesh
      - push to a local tamper-evident store
    """
    if not witness_enabled():
        return
    # TODO: implement via Calyx/Mandle or governance witness mesh
    return


def witness_verify(
    store_id: str,
    head_seq: int,
    head_hash: str,
    state_hash: Optional[str],
) -> bool:
    """
    Verify the current continuity head against a witness.

    Returns True if:
      - witnessing is disabled, or
      - the witness agrees with the provided head.

    In v0.1, witnessing is disabled and always returns True.
    """
    if not witness_enabled():
        return True
    # TODO: implement via Calyx/Mantle or governance witness mesh
    return True
