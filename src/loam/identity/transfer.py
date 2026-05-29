# loam/identity/transfer.py

from __future__ import annotations

import errno
import json
import os
import secrets
import shutil
import tarfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import tempfile
from typing import Optional

from loam.crypto.canonical import canonical_json
from loam.crypto.signing import sign
from loam.crypto.sealed import seal_bytes, unseal_bytes, SealedBlob
from loam.chronicle.chronicle import append_chronicle_entry
from loam.identity.identity_fingerprint import build_identity_fingerprint_v1
from loam.identity.keysources import KeySourceContext, load_signer_from_keysource
from loam.identity.paths import (
    store_path,
    private_key_file,
    public_key_file,
)


@dataclass
class TransferEnvelope:
    """
    Signed description of a sealed identity backup.

    NOTE: The signature is over the canonical JSON of this structure.
    """
    store_id: str               # original store UUID (identity store container)
    identity_fingerprint: str   # sha256(public_key_bytes)
    exported_at: str            # ISO8601 UTC timestamp
    nonce: str                  # random 32-byte hex string
    payload_hash: str           # sha256 over deterministic tarball


def _deterministic_tar_payload(payload_dir: Path) -> bytes:
    """
    Create a deterministic tar.gz of payload_dir.
    Ensures stable ordering, timestamps, uid/gid, and metadata.
    """
    buf = BytesIO()

    def reset(ti: tarfile.TarInfo):
        ti.uid = 0
        ti.gid = 0
        ti.uname = ""
        ti.gname = ""
        ti.mtime = 0
        return ti

    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for path in sorted(payload_dir.rglob("*")):
            if path.is_file():
                arcname = "/".join(path.relative_to(payload_dir).parts)
                tf.add(path, arcname=arcname, filter=reset)

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_identity_fingerprint_from_pubkey_bytes(pub_bytes: bytes) -> str:
    """
    Identity fingerprint = sha256(public_key_file_bytes)
    """
    return sha256(pub_bytes).hexdigest()


def _ensure_empty_dir(path: Path) -> None:
    """
    Create `path` as an empty directory. If it exists and is non-empty, fail.
    """
    if path.exists():
        if any(path.iterdir()):
            raise RuntimeError(f"export_dir_not_empty: {path}")
    else:
        path.mkdir(parents=True, exist_ok=True)


def _copy_if_exists(src: Path, dst: Path) -> None:
    """
    Copy a file or directory from src to dst if src exists.
    """
    if not src.exists():
        return

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------

def build_payload(store_id: str, payload_dir: Path) -> None:
    """
    Copy the entire identity store directory into payload_dir.
    Sealed export is a full identity store backup.
    """
    root = store_path(store_id)

    for item in root.iterdir():
        dst = payload_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst)


# ---------------------------------------------------------------------------
# Payload hashing
# ---------------------------------------------------------------------------

def _untar_payload(tar_bytes: bytes, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    buf = BytesIO(tar_bytes)
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        tf.extractall(path=target_dir)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_identity(
    store_id: str,
    export_dir: Path,
    passphrase: Optional[str] = None,
) -> None:
    # 1. Prepare directories
    _ensure_empty_dir(export_dir)
    payload_dir = export_dir / "payload"
    payload_dir.mkdir(parents=True, exist_ok=True)

    # 2. Build payload (full identity store backup)
    build_payload(store_id, payload_dir)

    # 3. Compute deterministic tarball + hash
    if not passphrase:
        raise RuntimeError("sealed_export_requires_passphrase")

    tar_bytes = _deterministic_tar_payload(payload_dir)
    payload_hash = sha256(tar_bytes).hexdigest()

    # 4. Build envelope
    pub_bytes = public_key_file(store_id).read_bytes()
    identity_fingerprint = _compute_identity_fingerprint_from_pubkey_bytes(pub_bytes)

    envelope = {
        "store_id": store_id,
        "identity_fingerprint": identity_fingerprint,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "nonce": secrets.token_hex(32),
        "payload_hash": payload_hash,
    }

    # 5. Sign envelope
    message = canonical_json(envelope)
    ksctx = KeySourceContext(passphrase=passphrase)
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)
    signature = signer.sign(message)

    # 6. Write transfer.json + signature
    (export_dir / "transfer.json").write_text(
        json.dumps(envelope, indent=2), encoding="utf-8"
    )
    (export_dir / "transfer.json.sig").write_bytes(signature)

    # 7. Write sealed payload
    sealed = seal_bytes(tar_bytes, passphrase)
    (export_dir / "payload.sealed").write_text(
        json.dumps(asdict(sealed), indent=2), encoding="utf-8"
    )

    # Remove unencrypted payload directory
    shutil.rmtree(payload_dir)

    # 8. Chronicle entry
    chronicle_log(store_id, "export", {
        "mode": "sealed",
        "exported_at": envelope["exported_at"],
        "payload_hash": payload_hash,
        },
        ksctx=ksctx,
    )



# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_identity(input_dir: Path, passphrase: Optional[str] = None) -> str:
    """
    Import a sealed identity backup produced by export_identity().
    Restores the identity store EXACTLY:
      - same store_id (UUID directory)
      - same keys
      - same continuity
      - same chronicle
      - same dossier/lineage/secrets/artifacts

    This is a true identity restore, not a clone/fork.
    """

    # 1. Load transfer.json
    transfer_json_path = input_dir / "transfer.json"
    if not transfer_json_path.exists():
        raise RuntimeError(f"missing_transfer_json: {transfer_json_path}")

    envelope_data = json.loads(transfer_json_path.read_text(encoding="utf-8"))
    envelope = TransferEnvelope(**envelope_data)

    # 2. Load sealed payload
    sealed_path = input_dir / "payload.sealed"
    if not sealed_path.exists():
        raise RuntimeError(f"missing_payload_sealed: {sealed_path}")
    if not passphrase:
        raise RuntimeError("sealed_import_requires_passphrase")

    sealed_data = json.loads(sealed_path.read_text(encoding="utf-8"))
    sealed_blob = SealedBlob(**sealed_data)

    # 3. Decrypt sealed tarball
    tar_bytes = unseal_bytes(sealed_blob, passphrase)

    # 4. Verify tarball hash BEFORE extraction
    computed_hash = sha256(tar_bytes).hexdigest()
    if computed_hash != envelope.payload_hash:
        raise RuntimeError("payload_hash_mismatch")

    # 5. Extract payload into a temporary directory
    payload_dir = input_dir / "payload"
    if payload_dir.exists():
        shutil.rmtree(payload_dir)
    _untar_payload(tar_bytes, payload_dir)

    # 6. Prepare atomic restore
    store_id = envelope.store_id
    root = store_path(store_id)

    if root.exists() and any(root.iterdir()):
        raise RuntimeError(f"store_dir_not_empty: {root}")

    # Create a temporary restore directory
    temp_restore = Path(tempfile.mkdtemp(prefix="loam-restore-"))

    try:
        # Copy everything from payload into temp_restore
        for item in payload_dir.iterdir():
            dst = temp_restore / item.name
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst)

        # 7. Atomic commit: rename temp_restore → root
        try:
            os.rename(temp_restore, root)
        except OSError as e:
            if e.errno == errno.EXDEV:
                # Cross-device link: fallback to copy + delete
                shutil.copytree(temp_restore, root)
                shutil.rmtree(temp_restore, ignore_errors=True)
            else:
                # Unexpected error: clean up and rethrow
                shutil.rmtree(temp_restore, ignore_errors=True)
                raise

        # Chronicle entry (must succeed before committing)
        ksctx = KeySourceContext(passphrase=passphrase)
        chronicle_log(
            store_id,
            "import",
            {
                "source_store_id": envelope.store_id,
                "source_identity_fingerprint": envelope.identity_fingerprint,
                "exported_at": envelope.exported_at,
                "imported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "mode": "sealed",
            },
            ksctx=ksctx,
        )
    except Exception:
        # Cleanup temp dir on failure
        shutil.rmtree(temp_restore, ignore_errors=True)
        raise
    return store_id


# ============================================================
# Chronicle helper (operator-plane, Layer 0)
# ============================================================

def chronicle_log(store_id: str, event: str, payload: dict | None = None, ksctx=None):
    """
    Emit a canonical Chronicle v1 event for identity transfer operations.
    """
    if payload is None:
        payload = {}

    signer = load_signer_from_keysource(store_id, ksctx=ksctx)
    
    identity_fp = build_identity_fingerprint_v1(store_id)

    event_dict = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event,
        "identity_fingerprint": identity_fp,
        "payload": payload,
    }

    append_chronicle_entry(store_id, event_dict, signer)