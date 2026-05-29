# loam/identity/namespace.py

import json
import uuid
from pathlib import Path

# -------------------------------------------------------------------
# Substrate-plane root
# -------------------------------------------------------------------

def substrate_root() -> Path:
    """
    Return the canonical substrate root (~/.loam).
    This is where namespace.json lives.
    """
    return Path.home() / ".loam"

# -------------------------------------------------------------------
# Namespace file
# -------------------------------------------------------------------

def namespace_file() -> Path:
    return substrate_root() / "namespace.json"

# -------------------------------------------------------------------
# Load namespace_id
# -------------------------------------------------------------------

def load_namespace_id() -> str:
    """
    Load the substrate-plane namespace_id.
    If missing or corrupted, initialize it.
    """
    ns_path = namespace_file()

    if not ns_path.exists():
        return initialize_namespace()

    try:
        data = json.loads(ns_path.read_text())
        return data["namespace_id"]
    except Exception:
        # Corrupted namespace.json → regenerate
        return initialize_namespace()

# -------------------------------------------------------------------
# Initialize namespace_id
# -------------------------------------------------------------------

def initialize_namespace() -> str:
    """
    Create a new namespace_id for this substrate.
    This is done once per machine/environment.
    """
    ns = str(uuid.uuid4())
    ns_path = namespace_file()
    ns_path.parent.mkdir(parents=True, exist_ok=True)
    ns_path.write_text(json.dumps({"namespace_id": ns}, indent=2))
    return ns