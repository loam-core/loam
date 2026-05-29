#crytpo/canonical.py

import base64
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")



def normalize(obj):
    if isinstance(obj, dict):
        return {k: normalize(normalize_value(v)) for k, v in obj.items()}

    if isinstance(obj, list):
        return [normalize(normalize_value(x)) for x in obj]

    return normalize_value(obj)


def normalize_value(v):
    # Primitive types are already fine
    if v is None or isinstance(v, (int, float, str, bool)):
        return v

    # Paths → strings
    if isinstance(v, Path):
        return str(v)

    # Bytes → base64
    if isinstance(v, bytes):
        return base64.b64encode(v).decode("ascii")

    # Datetimes → ISO8601
    if isinstance(v, datetime):
        return v.isoformat()

    # Enums → their value
    if isinstance(v, Enum):
        return v.value

    # Everything else: leave as-is, JSON will error if unsupported
    return v

TRUST_FIELDS = ("event_hash", "signature")

def canonical_chronicle_string(entry: dict) -> str:
    """
    Produce the canonical string for a Chronicle entry.
    This removes trust fields, normalizes values, injects schema versions,
    sorts keys, and produces a deterministic UTF-8 string.
    """

    # 1. KEEP trust fields
    filtered = dict(entry)

    # 2. Normalize recursively
    normalized = normalize(filtered)

    # 3. Inject schema versions
    normalized["schema_version"] = 1
    normalized["event_version"] = 1

    # 4. Canonical JSON: sorted keys, no whitespace
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":")
    )