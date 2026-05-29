# loam/cli/ops.py

import json
import os
import sys
#import json
import getpass
from pathlib import Path

#from loam.identity.namespace import initialize_namespace
from loam.continuity.hash import compute_file_hash
from loam.crypto.canonical import canonical_json
from loam.crypto.signing import load_public_key, verify_b64
from loam.identity.metadata import load_metadata, resolve_store_identifier
from loam.identity.namespace import load_namespace_id
from loam.identity.paths import public_key_file, store_path
from loam.identity.transfer import export_identity, import_identity
from loam.identity.revocation import check_revocation

from loam.substrate.artifacts import (
    verify_artifact_envelope,
    load_artifact_envelope,
)

# ------------------------------------------------------------
# Loam namespace initialization
# ------------------------------------------------------------

def cmd_init(args):
    """
    Initialize the Loam substrate.

    Creates ~/.loam and ~/.loam/stores if missing,
    and ensures namespace.json exists.
    """
    root = Path.home() / ".loam"
    stores = root / "stores"

    root.mkdir(parents=True, exist_ok=True)
    stores.mkdir(parents=True, exist_ok=True)

    ns_path = root / "namespace.json"
    existed = ns_path.exists()

    # This will create namespace.json if missing
    ns_id = load_namespace_id()

    if existed:
        print("Loam substrate already initialized.")
    else:
        print("Initialized Loam substrate.")

    print(f"Namespace ID: {ns_id}")

# ------------------------------------------------------------
# Artifact Verification
# ------------------------------------------------------------

def cmd_verify_artifact(args):
    store_id = resolve_store_identifier(args.store)
    envelope_path = Path(args.artifact)

    envelope = load_artifact_envelope(envelope_path)
    atype = envelope.get("artifact_type")

    if atype == "tool_output":
        ok = verify_artifact_envelope(envelope_path)
        if not ok:
            raise ValueError("Tool artifact verification failed")
        print("Tool artifact verified ✓")
        return

    if atype == "file":
        cmd_verify_file_artifact(args)
        return

    raise ValueError(f"Unknown artifact_type: {atype}")


def cmd_verify_file_artifact(args):
    # Use args.artifact, not args.path
    envelope_path = Path(args.artifact)

    # Load envelope
    envelope = load_artifact_envelope(envelope_path)

    # Extract signature
    signature_b64 = envelope["signature"]

    # Canonicalize envelope without signature
    unsigned = dict(envelope)
    unsigned.pop("signature", None)
    canonical = canonical_json(unsigned)

    # Load store public key
    store_id = resolve_store_identifier(args.store)
    public_key_path = public_key_file(store_id)
    public_key_bytes = public_key_path.read_bytes()

    # Verify signature using your existing crypto primitive
    verify_b64(public_key_bytes, canonical, signature_b64)

    # Recompute file hash
    base = envelope_path.name.replace(".artifact.json", "")
    data_path = envelope_path.parent / f"{base}.bin"
    computed_hash = compute_file_hash(data_path)

    if computed_hash != envelope["hash"]:
        raise ValueError("File hash mismatch")

    # Check revocation
    store_root = Path(os.path.expanduser("~/.loam/stores")) / store_id
    dossier_path = store_path(store_id) / "dossier" / "root_dossier.json"

    dossier = json.loads(dossier_path.read_text())
    identity_block = dossier.get("identity", {})

    fingerprint = identity_block.get("identity_fingerprint")
    check_revocation(fingerprint)

    print("Artifact verified ✓")

# ------------------------------------------------------------
# Export Store Identity
# ------------------------------------------------------------

def cmd_export_identity(args):
    store_id = resolve_store_identifier(args.store)
    out_dir = Path(args.out)

    # sealed-only: passphrase required (prompt if missing)
    passphrase = args.passphrase
    if not passphrase:
        passphrase = getpass.getpass("Enter export passphrase: ")

    print(f"Exporting store identity {store_id}")
    print(f"  out:  {out_dir}")

    export_identity(store_id, out_dir, passphrase=passphrase)

    print("Export complete.")


# ------------------------------------------------------------
# Import Store Identity
# ------------------------------------------------------------

def cmd_import_identity(args):
    bundle_dir = Path(args.store)

    # sealed-only: passphrase required (prompt if missing)
    passphrase = args.passphrase
    if not passphrase:
        passphrase = getpass.getpass("Import passphrase: ")

    print(f"Importing store identity from: {bundle_dir}")

    new_store_id = import_identity(bundle_dir, passphrase=passphrase)

    print("Import complete.")
    print(f"Restored store UUID = {new_store_id}")


# ------------------------------------------------------------
# Error
# ------------------------------------------------------------

def error(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)




