#identity/metadata.py
import json
from pathlib import Path
import re
import json
from pathlib import Path

from loam.identity.identity_fingerprint import build_identity_fingerprint_v1
from loam.identity.paths import (
    STORES_ROOT,
    store_path,
    dossier_file,
    metadata_file,
    secrets_dir,
)



# -------------------------------------------------------------------
# Secret usage tracking
# -------------------------------------------------------------------

def secret_usage_path(store_id: str) -> Path:
    return secrets_dir(store_id) / "usage.json"


def load_secret_usage(store_id: str) -> dict:
    path = secret_usage_path(store_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_secret_usage(store_id: str, usage: dict):
    path = secret_usage_path(store_id)
    path.write_text(json.dumps(usage, indent=2))


def update_secret_usage(
    store_id,
    secret_name,
    tool,
    envelope_hash=None,
    timestamp=None,
    had_error=False,
    rotated=False,
):
    usage = load_secret_usage(store_id)

    entry = usage.get(secret_name, {
        "usage_count": 0,
        "first_used_at": timestamp,
        "last_used_at": timestamp,
        "used_by_tools": [],
        "used_by_envelopes": [],
        "used_after_errors": False,
        "used_after_rotation": False,
    })

    entry["usage_count"] += 1
    entry["last_used_at"] = timestamp

    if tool and tool not in entry["used_by_tools"]:
        entry["used_by_tools"].append(tool)

    if envelope_hash and envelope_hash not in entry["used_by_envelopes"]:
        entry["used_by_envelopes"].append(envelope_hash)

    if had_error:
        entry["used_after_errors"] = True

    if rotated:
        entry["used_after_rotation"] = True

    usage[secret_name] = entry
    save_secret_usage(store_id, usage)
    return entry


# -------------------------------------------------------------------
# Human-friendly name identity metadata
# -------------------------------------------------------------------

def metadata_path(store_id: str) -> Path:
    return store_path(store_id) / "metadata.json"


def load_metadata(store_id: str) -> dict:
    path = metadata_path(store_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_metadata(store_id: str, metadata: dict):
    path = metadata_path(store_id)
    path.write_text(json.dumps(metadata, indent=2))




UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)

FP_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")


def resolve_store_identifier(identifier: str) -> str:
    """
    Resolve a store identifier, which may be:
      - store UUID
      - human-friendly name (metadata.json)
      - identity fingerprint (unified)
    Returns the store_id (UUID).
    Raises ValueError on failure.
    """

    # ------------------------------------------------------------
    # 1. UUID match
    # ------------------------------------------------------------
    if UUID_RE.match(identifier):
        if store_path(identifier).exists():
            return identifier
        raise ValueError(f"Unknown store UUID: {identifier}")

    # ------------------------------------------------------------
    # 2. Unified identity fingerprint match
    # ------------------------------------------------------------
    if FP_RE.match(identifier):
        for entry in STORES_ROOT.iterdir():
            if not entry.is_dir():
                continue
            store_id = entry.name
            fp = build_identity_fingerprint_v1(store_id)
            if fp == identifier:
                return store_id
        raise ValueError(f"No store with identity fingerprint: {identifier}")

    # ------------------------------------------------------------
    # 3. Name match (metadata.json)
    # ------------------------------------------------------------
    for entry in STORES_ROOT.iterdir():
        if not entry.is_dir():
            continue
        store_id = entry.name

        m_path = metadata_file(store_id)
        if not m_path.exists():
            continue

        try:
            meta = json.loads(m_path.read_text())
        except Exception:
            continue

        if meta.get("name") == identifier:
            return store_id

    # ------------------------------------------------------------
    # 4. No match
    # ------------------------------------------------------------
    raise ValueError(f"Could not resolve store identifier: {identifier}")
