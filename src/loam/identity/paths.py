# loam/identity/paths.py

from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# -------------------------------------------------------------------
# Canonical operator-plane store root
# -------------------------------------------------------------------

STORES_ROOT = Path.home() / ".loam" / "stores"
ARTIFACTS_ROOT = Path.home() / ".loam" / "artifacts"

# -------------------------------------------------------------------
# Canonical directory names
# -------------------------------------------------------------------

KEYS_DIR = "keys"
DOSSIER_DIR = "dossier"
CONTINUITY_DIR = "continuity"
CHRONICLE_DIR = "chronicle"
SECRETS_DIR = "secrets"
LINEAGE_DIR = "lineage"
ARTIFACTS_DIR = "artifacts"
STATE_DIR = "state"

# -------------------------------------------------------------------
# Canonical filenames
# -------------------------------------------------------------------

PRIVATE_KEY = "private_key"
PUBLIC_KEY = "public_key"
ROOT_DOSSIER = "root_dossier.json"

CONTINUITY_LOG = "continuity.log"
CHRONICLE_LOG = "chronicle.log"
LINEAGE_JSON = "lineage.json"
LINEAGE_SIG = "lineage.json.sig"

MASTER_KEY = "master_key.bin"
MASTER_KEY_SIG = "master_key.sig"

# -------------------------------------------------------------------
# Store directory helpers
# -------------------------------------------------------------------

def stores_root() -> Path:
    """
    Return the canonical root directory containing all identity stores.
    """
    return STORES_ROOT

def store_path(store_id: str) -> Path:
    """
    Return the canonical directory for an identity store.
    """
    return STORES_ROOT / store_id

def keys_dir(store_id: str) -> Path:
    return store_path(store_id) / KEYS_DIR

def private_key_file(store_id: str) -> Path:
    return keys_dir(store_id) / PRIVATE_KEY

def public_key_file(store_id: str) -> Path:
    return keys_dir(store_id) / PUBLIC_KEY

def dossier_dir(store_id: str) -> Path:
    return store_path(store_id) / DOSSIER_DIR

def dossier_file(store_id: str) -> Path:
    return dossier_dir(store_id) / ROOT_DOSSIER

def continuity_dir(store_id: str) -> Path:
    return store_path(store_id) / CONTINUITY_DIR

def continuity_log(store_id: str) -> Path:
    return continuity_dir(store_id) / CONTINUITY_LOG

def artifacts_root() -> Path:
    return ARTIFACTS_ROOT

def artifacts_dir(store_id: str) -> Path:
    """
    Operator-plane artifact directory for this store.
    """
    return ARTIFACTS_ROOT / store_id


def state_dir(store_id: str) -> Path:
    return store_path(store_id) / STATE_DIR

def chronicle_dir(store_id: str) -> Path:
    return store_path(store_id) / CHRONICLE_DIR

def chronicle_log(store_id: str) -> Path:
    return chronicle_dir(store_id) / CHRONICLE_LOG

def lineage_dir(store_id: str) -> Path:
    return store_path(store_id) / LINEAGE_DIR

def lineage_file(store_id: str) -> Path:
    return lineage_dir(store_id) / LINEAGE_JSON

def lineage_sig_file(store_id: str) -> Path:
    return lineage_dir(store_id) / LINEAGE_SIG

def secrets_dir(store_id: str) -> Path:
    return store_path(store_id) / SECRETS_DIR

def master_key_file(store_id: str) -> Path:
    return secrets_dir(store_id) / MASTER_KEY

def master_key_sig_file(store_id: str) -> Path:
    return secrets_dir(store_id) / MASTER_KEY_SIG

def secret_file(store_id: str, name: str) -> Path:
    return secrets_dir(store_id) / f"{name}.json"

def metadata_file(store_id: str) -> Path:
    return store_path(store_id) / "metadata.json"

# -------------------------------------------------------------------
# Cryptography helpers
# -------------------------------------------------------------------

def load_public_key(store_id: str):
    raw = public_key_file(store_id).read_bytes()
    return Ed25519PublicKey.from_public_bytes(raw)