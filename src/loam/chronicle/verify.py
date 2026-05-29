# loam/chronicle/verify.py

import base64
import json
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from loam.crypto.canonical import canonical_chronicle_string, normalize
from loam.identity.paths import (
    chronicle_dir,
    public_key_file,
    CHRONICLE_LOG,
)



def verify_chronicle(store_id: str) -> dict:
    """
    Verify the Chronicle log for a store.

    Chronicle is a trustable but pruneable audit log:
      - hash-chained
      - signed
      - canonicalized
      - anchored to continuity
      - expected to be pruned/rotated

    This verifier:
      - NEVER fails closed
      - classifies integrity
      - emits warnings for suspicious/tampered states
    """
    report = {
        "ok": True,                 # overall "is this usable?"
        "integrity": "intact",      # "intact" | "incomplete" | "suspicious" | "tampered"
        "warnings": [],             # human-readable warnings
        "files_checked": [],
        "entries_checked": 0,
        "last_seq": None,
    }

    chron_dir = chronicle_dir(store_id)

    if not chron_dir.exists():
        # No chronicle at all is allowed; just means no audit trail.
        report["integrity"] = "incomplete"
        report["warnings"].append("No Chronicle directory found for store.")
        return report

    # Gather all chronicle files (rotated + active)
    files = []
    for name in chron_dir.iterdir():
        if name.name == CHRONICLE_LOG:
            # active file always last
            files.append((999999, name))
        elif name.name.startswith("chronicle.") and name.name.endswith(".log"):
            try:
                idx = int(name.name.split(".")[1])
                files.append((idx, name))
            except ValueError:
                continue

    if not files:
        report["integrity"] = "incomplete"
        report["warnings"].append("Chronicle directory exists but contains no log files.")
        return report

    files.sort(key=lambda x: x[0])
    report["files_checked"] = [str(p) for _, p in files]

    # Load public key
    pub_path = public_key_file(store_id)
    with open(pub_path, "rb") as f:
        public_key = Ed25519PublicKey.from_public_bytes(f.read())

    last_hash = ""
    last_entry_seen = False

    # Stream entries across all files
    for _, path in files:
        with open(path, "r") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                except Exception:
                    report["ok"] = False
                    report["integrity"] = "tampered"
                    report["warnings"].append(f"Malformed JSON entry in {path}.")
                    continue

                report["entries_checked"] += 1
                last_entry_seen = True

                seq = entry.get("continuity_seq")
                if seq is not None:
                    report["last_seq"] = seq

                prev_hash = entry.get("prev_event_hash")
                event_hash = entry.get("event_hash")
                signature_b64 = entry.get("signature")


                # 1. Check prev_hash linkage (hash chain)
                if last_hash == "":
                    # First entry in the log: allow no prev_event_hash (genesis or first segment)
                    pass
                else:
                    if prev_hash != last_hash:
                        report["ok"] = False
                        report["integrity"] = "tampered"
                        report["warnings"].append(
                            f"Hash chain break detected in {path}: prev_event_hash does not match last event_hash."
                        )

                # 2. Rebuild canonical string (schema-flexible, trust fields removed)
                entry_for_canonical = {
                    k: v for k, v in entry.items()
                    if k not in ("event_hash", "signature", "prev_event_hash")
                }

                # NEW: normalize before canonicalizing
                normalized = normalize(entry_for_canonical)
                canonical_for_hash = canonical_chronicle_string(normalized).encode("utf-8")

                # 3. Recompute hash
                computed_hash = hashlib.sha256(canonical_for_hash).hexdigest()
                if computed_hash != event_hash:
                    report["ok"] = False
                    report["integrity"] = "tampered"
                    report["warnings"].append(
                        f"[HASH] mismatch in {path}: computed={computed_hash}, stored={event_hash}"
                    )

                # 4. Verify signature
                try:
                    sig = base64.b64decode(signature_b64)
                    public_key.verify(sig, canonical_for_hash)
                except Exception as e:
                    report["ok"] = False
                    report["integrity"] = "tampered"
                    report["warnings"].append(
                        f"[SIG] verification failed in {path}: {e!r}"
                    )



                # 5. Update rolling state
                last_hash = event_hash

    if not last_entry_seen:
        report["integrity"] = "incomplete"
        report["warnings"].append("Chronicle logs are present but contain no entries.")
        return report

    # If we saw issues but never upgraded to "tampered", mark as "suspicious"
    if report["ok"] and report["warnings"]:
        report["integrity"] = "suspicious"
    elif report["ok"] and not report["warnings"]:
        report["integrity"] = "intact"

    return report
