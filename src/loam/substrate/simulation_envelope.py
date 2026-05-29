# substrate/envelope.py

import json
import hashlib
import uuid
from datetime import datetime, timezone


def create_simulation_envelope(self):
    run_id = uuid.uuid4().hex

    envelope = {
        "schema_version": 1,
        "run_id": run_id,
        "simulation_depth": getattr(self, "simulation_depth", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "identity_fingerprint_hash": self.identity_fingerprint_hash(),
        "store_id": self.store_id,
    }

    self.run_id = run_id
    return envelope


def hash_envelope(env: dict) -> str:
    payload = json.dumps(env, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
