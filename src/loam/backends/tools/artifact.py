#backends/tools/artifact.py
import json
from loam.continuity.hash import compute_file_hash
from loam.substrate.artifacts import (
    build_file_artifact_envelope,
    write_file_artifact,
    sign_artifact_envelope,
    )

def emit(context, args):
    path = args["path"]
    desc = args.get("description")

    # Resolve sandbox path
    p = context._sandbox_path(path)
    data = p.read_bytes()

    size = len(data)
    file_hash = compute_file_hash(p)

    # Build envelope
    envelope, canonical = build_file_artifact_envelope(
        context.store_id,
        context.identity_fingerprint_hash(),
        path,
        desc,
        size,
        file_hash,
    )

    # Sign envelope
    envelope["signature"] = sign_artifact_envelope(context.signer, canonical)

    # Write artifact files
    artifact_path = write_file_artifact(
        store_id=context.store_id,
        envelope=envelope,
        data=data,
        artifacts_path=context.artifacts_path,
    )

    return {
        "result": {
            "artifact": str(artifact_path),
            "bytes": size,
        },
        "meta": {
            "path": path,
            "bytes": size,
            "artifact_path": str(artifact_path),
            "full_path": str(p),
            "file_hash": file_hash,
            # envelope_hash is computed inside build_file_artifact_envelope
            # emitter will add canonical_hash later
        }
    }

