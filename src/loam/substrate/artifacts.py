# loam/artifacts.py

import base64
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

from loam.crypto.canonical import canonical_json
from loam.crypto.signing import verify_b64
from loam.identity.paths import (
    public_key_file,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_artifact_hash(stdout: bytes, stderr: bytes) -> str:
    """
    Compute SHA-256 hash of stdout+stderr bytes.
    """
    h = hashlib.sha256()
    h.update(stdout)
    h.update(stderr)
    return h.hexdigest()


def build_tool_artifact_envelope(
    store_id: str,
    identity_fingerprint_hash: str,
    tool: str,
    stdout: bytes,
    stderr: bytes,
    exit_code: int,
) -> Tuple[Dict, bytes]:

    artifact_hash = compute_artifact_hash(stdout, stderr)
    created_at = _now_iso()

    envelope = {
        "store_id": store_id,
        "identity_fingerprint_hash": identity_fingerprint_hash,
        "artifact_type": "tool_output",
        "tool": tool,
        "created_at": created_at,
        "hash": artifact_hash,
        "metadata": {
            "exit_code": exit_code,
            "stdout_len": len(stdout),
            "stderr_len": len(stderr),
        },
    }

    canonical = canonical_json(envelope)
    return envelope, canonical


def build_file_artifact_envelope(
    store_id: str,
    identity_fingerprint_hash: str,
    path: str,
    description: str,
    size: int,
    file_hash: str,
) -> Tuple[Dict, bytes]:

    created_at = _now_iso()

    envelope = {
        "store_id": store_id,
        "identity_fingerprint_hash": identity_fingerprint_hash,
        "artifact_type": "file",
        "path": path,
        "description": description,
        "created_at": created_at,
        "hash": file_hash,
        "metadata": {
            "size": size,
        },
    }

    canonical = canonical_json(envelope)
    return envelope, canonical


def sign_artifact_envelope(signer, canonical: bytes) -> str:
    """
    Sign the canonical envelope bytes using the runtime's signer.
    Returns base64-encoded signature.
    """
    sig_bytes = signer.sign(canonical)
    return base64.b64encode(sig_bytes).decode()




def write_tool_artifact_files(
    tool: str,
    stdout: bytes,
    stderr: bytes,
    envelope: Dict,
    artifacts_path: Path,
    ) -> Path:
    adir = artifacts_path
    adir.mkdir(parents=True, exist_ok=True)

    ts = envelope["created_at"].replace(":", "-")
    base = f"{ts}-{tool}"

    stdout_path = adir / f"{base}.stdout"
    stderr_path = adir / f"{base}.stderr"
    envelope_path = adir / f"{base}.artifact.json"

    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    envelope_path.write_text(json.dumps(envelope, indent=2, sort_keys=True))

    return envelope_path


def write_file_artifact(
    store_id: str,
    envelope: Dict,
    data: bytes,
    artifacts_path: Path,
    ) -> Path:
    """
    Write a file artifact:
      - envelope JSON
      - data blob
    Returns the path to the envelope file.
    """
    artifacts_path.mkdir(parents=True, exist_ok=True)

    ts = envelope["created_at"].replace(":", "-")
    base = f"{ts}-file"

    data_path = artifacts_path / f"{base}.bin"
    envelope_path = artifacts_path / f"{base}.artifact.json"

    # Write the file data
    data_path.write_bytes(data)

    # Write the envelope
    envelope_path.write_text(
        json.dumps(envelope, indent=2, sort_keys=True)
    )

    return envelope_path

def load_artifact_envelope(envelope_path: Path) -> dict:
    """
    Load an artifact envelope JSON file without verifying it.
    """
    return json.loads(envelope_path.read_text())


def verify_artifact_envelope(envelope_path: Path) -> bool:
    """
    Verify the artifact envelope and its signature against the store's public key.
    Also recompute the hash from stdout+stderr and compare.
    """
    envelope = json.loads(envelope_path.read_text())

    store_id = envelope["store_id"]
    signature_b64 = envelope.get("signature")
    if not signature_b64:
        raise ValueError("Envelope missing signature")

    # Rebuild canonical bytes (without signature)
    env_copy = dict(envelope)
    env_copy.pop("signature", None)
    canonical = canonical_json(env_copy)

    # Verify signature
    public_key_path = public_key_file(store_id)
    public_key_bytes = public_key_path.read_bytes()
    verify_b64(public_key_bytes, canonical, signature_b64)

    # Recompute hash from stdout+stderr
    adir = envelope_path.parent
    base = envelope_path.name.replace(".artifact.json", "")
    stdout_path = adir / f"{base}.stdout"
    stderr_path = adir / f"{base}.stderr"

    stdout = stdout_path.read_bytes()
    stderr = stderr_path.read_bytes()

    recomputed = compute_artifact_hash(stdout, stderr)
    if recomputed != envelope["hash"]:
        raise ValueError("Artifact hash mismatch")

    return True
