# substrate/trust.py

import os
import hashlib
from logging import log

from loam.chronicle.verify import verify_chronicle
from loam.identity.dossier import verify_root_dossier
from loam.identity.folder_verifier import verify_identity_folder
from loam.identity.lineage import verify_lineage
from loam.identity.paths import stores_root, public_key_file
from loam.identity.revocation import check_revocation

from loam.continuity.append import load_last_record
from loam.continuity.verify import verify_chain
from loam.identity.identity_fingerprint import (
    build_identity_fingerprint_v1,
    compute_identity_fingerprint_hash_v1,
)
from loam.substrate.state_hashing import compute_state_hash


def verify_trust_boundaries(runtime):
    if runtime.is_simulation():
        # Simulations must never enter the trust pipeline
        raise RuntimeError("simulation_cannot_enter_trust_pipeline")


    _verify_no_duplicate_identity_fingerprints(runtime)
    _verify_identity_root(runtime)
    _verify_identity_revocation(runtime)
    _verify_continuity_chain(runtime)
    _verify_chronicle_chain(runtime)   
    _verify_identity_fingerprint(runtime)
    _verify_state_continuity_boundary(runtime)



def _verify_identity_root(runtime):
    verify_root_dossier(runtime.store_id)
    verify_lineage(runtime.store_id)

    ok, info = verify_identity_folder(runtime.store_id)
    if not ok:
        # Normalize info to a dict
        if not isinstance(info, dict):
            info = {"reason": str(info)}

        msg = (
            "\nERROR: Identity folder integrity verification failed.\n"
            f"Reason: {info.get('reason')}\n\n"
            "This indicates the agent's identity folder is missing required files, "
            "contains invalid data, or has been modified outside of normal execution.\n\n"
        )
        payload = {
            "boundary": "identity_folder_integrity",
            "reason": info.get("reason", "unknown"),
            "details": info,
            "simulation": runtime.is_simulation(),
        }
        try:
            runtime.chronicle("identity_verification_failed", payload)
        except:    
            raise RuntimeError(msg)


def _verify_identity_revocation(runtime):
    identity_fingerprint = runtime.identity["identity_fingerprint"]
    check_revocation(identity_fingerprint)



def _verify_continuity_chain(runtime):
    ok, info = verify_chain(runtime.store_id)
    if not ok:
        msg = (
            "\nERROR: Continuity chain verification failed.\n"
            f"Reason: {info.get('reason')}\n\n"
            "This indicates the agent's continuity log has been modified, truncated, "
            "corrupted, or is otherwise inconsistent with its recorded history.\n\n"
        )
        payload = {
            "boundary": "runtime_continuity",
            "reason": info.get("reason"),
            "details": info,
            "simulation": runtime.is_simulation(),
        }
        runtime.chronicle("startup_verification_failed", payload)
        raise RuntimeError(msg)


def _verify_chronicle_chain(runtime):
    ok = verify_chronicle(runtime.store_id)
    if not ok:
        msg = (
            "\nERROR: Chronicle verification failed.\n"
            "The chronicle log has been modified, truncated, corrupted, "
            "or contains invalid signatures.\n\n"
        )
        payload = {
            "boundary": "chronicle_integrity",
            "reason": "chronicle_verification_failed",
            "simulation": runtime.is_simulation(),
        }
        runtime.chronicle("chronicle_verification_failed", payload)
        raise RuntimeError(msg)


def _verify_identity_fingerprint(runtime):
    last = load_last_record(runtime.store_id)
    if not last:
        # Fresh agent: no continuity yet, nothing to compare
        runtime.current_continuity_seq = 0
        return

    identity_fingerprint = build_identity_fingerprint_v1(runtime.store_id)
    expected_hash = compute_identity_fingerprint_hash_v1(identity_fingerprint)


    if last.get("identity_fingerprint_hash") != expected_hash:
        msg = (
            "\nERROR: Startup verification failed.\n"
            "Reason: identity_fingerprint_mismatch\n\n"
            "This indicates the agent's identity, continuity chain, or "
            "identity fingerprint has been modified or is inconsistent with "
            "the recorded history.\n\n"
        )
        payload = {
            "boundary": "startup_identity_continuity",
            "reason": "identity_fingerprint_mismatch",
            "details": {"last_seq": last.get("seq")},
            "simulation": runtime.is_simulation(),
        }
        runtime.chronicle("startup_verification_failed", payload)
        raise RuntimeError(msg)

    runtime.current_continuity_seq = last["seq"]


def _verify_state_continuity_boundary(runtime):
    state_cfg = runtime.state_cfg

    # If hashing disabled → no boundary
    if not getattr(state_cfg, "hashing_enabled", False):
        return

    state_dir = getattr(state_cfg, "path", None)
    if not state_dir:
        msg = (
            "\nERROR: State continuity enabled but no state.path configured.\n"
            "This indicates a misconfigured agent identity.\n"
        )
        payload = {
            "boundary": "state_continuity",
            "reason": "missing_state_path",
            "simulation": runtime.is_simulation(),
        }
        runtime.chronicle("state_continuity_failed", payload)
        raise RuntimeError(msg)


    last = load_last_record(runtime.store_id)
    if last is None:
        # No continuity yet → nothing to enforce
        return

    last_state_hash = last.get("state_hash")
    current_state_hash = compute_state_hash(state_dir)

    if last_state_hash is not None and last_state_hash != current_state_hash:
        msg = (
            "\nERROR: State continuity mismatch.\n"
            "The agent's state directory has changed since the last execution.\n"
            "This indicates a rollback, tamper, or external modification.\n"
        )
        payload = {
            "boundary": "state_continuity",
            "reason": "state_hash_mismatch",
            "details": {
                "last_state_hash": last_state_hash,
                "current_state_hash": current_state_hash,
            },
            "simulation": runtime.is_simulation(),
        }
        runtime.chronicle("state_continuity_failed", payload)
        raise RuntimeError(msg)

def _verify_no_duplicate_identity_fingerprints(runtime):
    root = stores_root()
    if not root.exists():
        return

    # fingerprint → [store_id1, store_id2, ...]
    seen = {}

    for entry in root.iterdir():
        if not entry.is_dir():
            continue

        store_id = entry.name
        pub = public_key_file(store_id)
        if not pub.exists():
            continue

        identity_fingerprint = build_identity_fingerprint_v1(store_id)
        fp = compute_identity_fingerprint_hash_v1(identity_fingerprint)

        seen.setdefault(fp, []).append(store_id)

    # detect duplicates
    duplicates = {fp: uuids for fp, uuids in seen.items() if len(uuids) > 1}
    if not duplicates:
        return

    # Build operator-friendly message
    lines = ["\nERROR: Duplicate identity detected on this substrate.\n"]
    for fp, uuids in duplicates.items():
        lines.append(f"Identity fingerprint: {fp}")
        for u in uuids:
            lines.append(f"  - {u}")
        lines.append("")

    lines.append(
        "This means multiple identity directories contain the same public key.\n"
        "This violates the identity uniqueness invariant:\n"
        "    one identity fingerprint → one active instance\n\n"
        "Resolve by deleting or relocating the duplicate identity directories.\n"
    )

    msg = "\n".join(lines)
    payload = {
        "boundary": "duplicate_identity_fingerprint",
        "reason": "duplicate_identity",
        "details": duplicates,
        "simulation": runtime.is_simulation(),
    }
    runtime.chronicle("duplicate_identity_detected", payload)
    raise RuntimeError(msg)