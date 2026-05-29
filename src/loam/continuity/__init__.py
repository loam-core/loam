# loam/continuity/__init__.py

import json
from loam.identity.paths import continuity_log
from .verify import verify_chain

def load_continuity(agent_id: str):
    """
    Load continuity log as a list of dicts.
    Returns [] if missing or empty.
    """
    log_path = continuity_log(agent_id)
    if not log_path.exists():
        return []

    raw = log_path.read_text().strip()
    if not raw:
        return []

    records = []
    for line in raw.splitlines():
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records

def pretty_continuity(records):
    """
    Pretty-print continuity records.
    """
    out = []
    for r in records:
        out.append(
            f"[{r['seq']}] {r['kind']} "
            f"idfp={r['identity_fingerprint_hash'][:8]} "
            f"state={str(r['state_hash'])[:8]} "
            f"hash={r['hash'][:8]}"
        )
    return "\n".join(out)

