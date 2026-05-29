# loam/cli/state.py

import json
import tomllib
import tomli_w
from pathlib import Path
from datetime import datetime

from loam.identity.keysources import get_passphrase_for_store, KeySourceContext, load_keysource_descriptor
from loam.identity.mutations import inscribe_identity_mutation
from loam.identity.metadata import load_metadata, resolve_store_identifier
from loam.identity.paths import store_path, continuity_log, chronicle_log
from loam.identity.toml_loader import load_identity_toml
from loam.substrate.state_hashing import compute_state_hash


def _get_ksctx_for_store(store_id: str) -> KeySourceContext:
    ks = load_keysource_descriptor(store_id)
    kind = ks.get("kind")

    if kind == "raw_ed25519":
        return KeySourceContext(passphrase=None)

    pw = get_passphrase_for_store(store_id)
    return KeySourceContext(passphrase=pw)


# ------------------------------------------------------------
# STATE ENABLE
# ------------------------------------------------------------

def cmd_state_enable(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    toml_path = store_path(store_id) / "identity.toml"
    data = load_identity_toml(toml_path) if toml_path.exists() else {}

    state_cfg = data.get("state", {}) or {}

    if not args.path:
        raise ValueError("State path must be provided (args.path missing).")

    p = Path(args.path)
    if not p.is_absolute():
        raise ValueError(f"State path must be absolute, got: {args.path}")

    state_cfg["path"] = str(p)
    state_cfg["hashing_enabled"] = True
    data["state"] = state_cfg

    with open(toml_path, "wb") as f:
        tomli_w.dump(data, f)

    ksctx = _get_ksctx_for_store(store_id)

    inscribe_identity_mutation(
        store_id,
        mutation_type="state_enable",
        ksctx=ksctx,
        old_value=False,
        new_value=True,
    )

    print(f"State hashing ENABLED for identity {name} ({store_id}).")


# ------------------------------------------------------------
# STATE DISABLE
# ------------------------------------------------------------

def cmd_state_disable(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    toml_path = store_path(store_id) / "identity.toml"
    data = load_identity_toml(toml_path)

    state_cfg = data.get("state", {}) or {}
    state_cfg["hashing_enabled"] = False
    data["state"] = state_cfg

    with open(toml_path, "wb") as f:
        tomli_w.dump(data, f)

    ksctx = _get_ksctx_for_store(store_id)

    inscribe_identity_mutation(
        store_id,
        mutation_type="state_disable",
        ksctx=ksctx,
        old_value=True,
        new_value=False,
    )

    print(f"State hashing DISABLED for identity {name} ({store_id}).")

# ------------------------------------------------------------
# STATE SET-PATH (declare state path without enabling hashing)
# ------------------------------------------------------------

def cmd_state_set_path(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    if not args.path:
        raise ValueError("State path must be provided (args.path missing).")

    p = Path(args.path)
    if not p.is_absolute():
        raise ValueError(f"State path must be absolute, got: {args.path}")

    toml_path = store_path(store_id) / "identity.toml"
    data = load_identity_toml(toml_path) if toml_path.exists() else {}

    state_cfg = data.get("state", {}) or {}
    old_path = state_cfg.get("path")

    state_cfg["path"] = str(p)
    state_cfg["hashing_enabled"] = False
    data["state"] = state_cfg

    with open(toml_path, "wb") as f:
        tomli_w.dump(data, f)

    ksctx = _get_ksctx_for_store(store_id)

    inscribe_identity_mutation(
        store_id,
        mutation_type="state_set_path",
        ksctx=ksctx,
        old_value=old_path,
        new_value=str(p),
    )

    print(f"State path SET for identity {name} ({store_id}). Hashing remains DISABLED.")

# ------------------------------------------------------------
# STATE UNSET-PATH (remove state path, disable hashing)
# ------------------------------------------------------------

def cmd_state_unset_path(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    toml_path = store_path(store_id) / "identity.toml"
    data = load_identity_toml(toml_path) if toml_path.exists() else {}

    state_cfg = data.get("state", {}) or {}
    old_path = state_cfg.get("path")

    # Remove the path key entirely
    if "path" in state_cfg:
        del state_cfg["path"]

    # Disable hashing
    state_cfg["hashing_enabled"] = False

    # If state_cfg is now empty, remove the whole [state] table
    if not state_cfg:
        if "state" in data:
            del data["state"]
    else:
        data["state"] = state_cfg


    with open(toml_path, "wb") as f:
        tomli_w.dump(data, f)

    ksctx = _get_ksctx_for_store(store_id)

    inscribe_identity_mutation(
        store_id,
        mutation_type="state_unset_path",
        ksctx=ksctx,
        old_value=old_path,
        new_value=None,
    )

    print(f"State path UNSET for identity {name} ({store_id}). Identity is now STATELESS.")

# ------------------------------------------------------------
# STATE SHOW
# ------------------------------------------------------------

def cmd_state_show(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    print(f"State status for identity {name} ({store_id}):")

    toml_path = store_path(store_id) / "identity.toml"
    if not toml_path.exists():
        print("  ERROR: identity.toml missing — identity incomplete.")
        print("  State hashing: UNKNOWN")
        return

    try:
        with open(toml_path, "rb") as f:
            cfg = tomllib.load(f)
    except Exception as e:
        print(f"  ERROR: Failed to parse identity.toml: {e}")
        return

    state_cfg = cfg.get("state", {})
    enabled = state_cfg.get("hashing_enabled", False)
    state_path = state_cfg.get("path")

    print(f"  State hashing: {'ENABLED' if enabled else 'DISABLED'}")
    print(f"  State path: {state_path if state_path else 'None'}")

    # Check state directory
    if state_path:
        p = Path(state_path)
        if not p.exists():
            print("  WARNING: State path does not exist on disk.")
        elif not p.is_dir():
            print("  WARNING: State path exists but is not a directory.")

    # Continuity log
    cont_path = continuity_log(store_id)
    if not cont_path.exists():
        print("  ERROR: No continuity log found.")
        return

    continuity_entries = []
    with cont_path.open("r") as f:
        for line in f:
            continuity_entries.append(json.loads(line))

    last_entry = continuity_entries[-1] if continuity_entries else None

    # Last baseline
    last_baseline_hash = None
    last_baseline_seq = None
    for entry in reversed(continuity_entries):
        if entry.get("state_hash") is not None:
            last_baseline_hash = entry["state_hash"]
            last_baseline_seq = entry["seq"]
            break

    # Compute current hash
    if enabled and state_path:
        try:
            current_hash = compute_state_hash(Path(state_path))
        except Exception as e:
            current_hash = "<error>"
            print(f"  ERROR: Failed to compute current state hash: {e}")
    else:
        current_hash = None

    # Chronicle identity mutations (Chronicle v1)
    chron_path = chronicle_log(store_id)
    identity_mutations = []
    if chron_path.exists():
        with chron_path.open("r") as f:
            for line in f:
                evt = json.loads(line)
                if evt.get("event_type") == "identity_mutation":
                    identity_mutations.append(evt)

    if identity_mutations:
        print("  Recent identity mutations:")
        for evt in identity_mutations[-3:]:
            payload = evt.get("payload", {})
            mut = payload.get("mutation_type", "unknown")
            ts = evt.get("timestamp")

            print(f"    @ {ts}: {mut}")
    else:
        print("  No identity mutations recorded.")

    # Health
    if enabled:
        print(f"  Last baseline: seq {last_baseline_seq} ({last_baseline_hash})")
        print(f"  Current state hash: {current_hash}")

        if current_hash == last_baseline_hash:
            print("  Status: HEALTHY (state matches baseline)")
        else:
            print("  Status: MISMATCH (trust boundary will fire on next run)")
    else:
        print("  Trust boundary: INACTIVE")
        if last_entry:
            print(f"  Last continuity seq: {last_entry['seq']}")
