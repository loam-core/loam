# loam/cli/logs.py

from datetime import datetime, timezone
from pathlib import Path
import json

from loam.identity.metadata import resolve_store_identifier, load_metadata
from loam.identity.paths import continuity_log, chronicle_log
from loam.continuity.verify import verify_chain
from loam.chronicle.verify import verify_chronicle


# ------------------------------------------------------------
# logs show (continuity / chronicle)
# ------------------------------------------------------------

def cmd_show_logs(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    chain_type = args.chain_type

    if chain_type == "continuity":
        path = continuity_log(store_id)
    else:
        path = chronicle_log(store_id)

    if not path.exists():
        print(f"No {chain_type} log found for store {name} ({store_id}).")
        return

    entries = []
    for line in path.read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except Exception:
            pass

    pretty_print(entries)


# ------------------------------------------------------------
# logs verify (continuity + chronicle only)
# ------------------------------------------------------------

def cmd_verify_logs(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    print(f"Verifying logs for store {name} ({store_id})...")
    print()

    # Continuity
    cont_path = continuity_log(store_id)
    cont_exists = cont_path.exists()
    print("Continuity:")
    print(f"  exists: {'yes' if cont_exists else 'no'}")
    if cont_exists:
        cont_ok, cont_info = verify_chain(store_id)
        print(f"  verification: {'OK' if cont_ok else 'FAILED'}")
        if not cont_ok:
            print(f"    {cont_info}")
    print()

    # Chronicle
    chron_path = chronicle_log(store_id)
    chron_exists = chron_path.exists()
    print("Chronicle:")
    print(f"  exists: {'yes' if chron_exists else 'no'}")
    if chron_exists:
        chron_ok = verify_chronicle(store_id)
        print(f"  verification: {'OK' if chron_ok else 'FAILED'}")
    print()


# ------------------------------------------------------------
# logs interlaced (continuity + chronicle merged, colored)
# ------------------------------------------------------------

GREEN = "\033[92m"
YELLOW = "\033[93m"
DIM = "\033[2m"
RESET = "\033[0m"

def cmd_interlaced_logs(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    cont_path = continuity_log(store_id)
    chron_path = chronicle_log(store_id)

    entries = []

    # Load continuity
    if cont_path.exists():
        for line in cont_path.read_text().splitlines():
            try:
                obj = json.loads(line)
                entries.append({
                    "timestamp": obj.get("timestamp", 0),
                    "type": "continuity",
                    "data": obj,
                })
            except Exception:
                pass

    # Load chronicle
    if chron_path.exists():
        for line in chron_path.read_text().splitlines():
            try:
                obj = json.loads(line)
                entries.append({
                    "timestamp": obj.get("timestamp", 0),
                    "type": "chronicle",
                    "data": obj,
                })
            except Exception:
                pass

    if not entries:
        print(f"No logs found for store {name} ({store_id}).")
        return

    # Sort by timestamp
    entries.sort(key=lambda e: normalize_ts(e["timestamp"]))

    print(f"Interlaced logs for store {name} ({store_id}):")
    print()

    for e in entries:
        ts = e["timestamp"]
        typ = e["type"]
        data = e["data"]

        if typ == "continuity":
            color = GREEN
            label = "CONTINUITY"
        else:
            color = YELLOW
            label = "CHRONICLE"

        print(f"{DIM}[{ts}]{RESET} {color}{label:<10}{RESET} {json.dumps(data, indent=2)}")
        print()

# ------------------------------------------------------------
# Pretty printer
# ------------------------------------------------------------
def abbrev(h):
    return h[:12] if h else ""

def pretty_print(entries):
    """
    Full-field pretty printer with semantic ordering.
    No filtering. No omission.
    """

    for e in entries:
        # --- 1. TOP: timestamp ---
        ts = e.get("timestamp")
        if ts:
            print(f"timestamp: {ts}")

        # --- 2. NEXT: seq or event_type ---
        if "seq" in e:
            print(f"seq: {e['seq']}")
            print(f"kind: {e.get('kind')}")
        if "event_type" in e:
            print(f"event_type: {e['event_type']}")

        # --- 3. Identity + store metadata ---
        for key in ["identity_fingerprint", "identity_fingerprint_hash", "store_id", "agent_id", "layer"]:
            if key in e:
                print(f"{key}: {e[key]}")

        # --- 4. Payload (full, sorted) ---
        payload = e.get("payload")
        if isinstance(payload, dict):
            print("payload:")
            for subkey in sorted(payload.keys()):
                print(f"  {subkey}: {payload[subkey]}")

        # --- 5. Everything else except hashes/signature ---
        skip = {
            "timestamp", "seq", "kind", "event_type",
            "identity_fingerprint", "identity_fingerprint_hash",
            "store_id", "layer",
            "payload",
            "hash", "prev_hash",
            "event_hash", "prev_event_hash",
            "continuity_hash", "continuity_seq",
            "signature"
        }

        for key in sorted(e.keys()):
            if key not in skip:
                print(f"{key}: {e[key]}")

        # --- 6. BOTTOM: hashes + signature ---
        for key in ["hash", "prev_hash", "event_hash", "prev_event_hash", "continuity_hash", "continuity_seq", "signature"]:
            if key in e:
                print(f"{key}: {e[key]}")

        print()


def normalize_ts(ts):
    if isinstance(ts, int):
        # old continuity format
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        # chronicle + new continuity format
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    raise TypeError(f"Unknown timestamp type: {type(ts)}")