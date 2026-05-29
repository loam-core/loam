# loam/cli/identity.py

from datetime import datetime
from pathlib import Path
import json
import os
import tomllib
import getpass
import re

from loam.cli.ops import error
from loam.cli.run import print_chronicle_attestation
from loam.continuity.append import load_last_record
from loam.identity.dossier import verify_root_dossier
from loam.identity.folder_verifier import verify_identity_folder
from loam.identity.identity_fingerprint import build_identity_fingerprint_v1, compute_identity_fingerprint_hash_v1
from loam.identity.lineage.lineage import verify_lineage
from loam.identity.metadata import (
    resolve_store_identifier,
    load_metadata,
    save_metadata,
)
from loam.identity.issue import issue_identity
from loam.identity.mutations import inscribe_identity_mutation
from loam.identity.paths import (
    public_key_file,
    stores_root,
    store_path
)
from loam.continuity.verify import verify_chain
from loam.chronicle.verify import verify_chronicle
from loam.identity.revocation import REVOCATION_PATH, check_revocation
from loam.substrate.attest_chronicle import attest_chronicle
from loam.substrate.state_hashing import compute_state_hash

from loam.identity.keysources import KeySourceContext, load_signer_from_keysource
from loam.identity.keysources import migrate_passphrase_to_plaintext
from loam.identity.master_key import master_key_encrypted_exists, master_key_plaintext_exists, migrate_master_key_to_plaintext
from loam.identity.keysources import migrate_plaintext_to_passphrase
from loam.identity.master_key import migrate_master_key_to_passphrase
from loam.identity.keysources import load_signer_from_keysource,  _passphrase_cache 
from ..cli.session import clear_all_cached_passphrases, clear_cached_passphrase, set_cached_passphrase
 




import getpass

# ------------------------------------------------------------
# Identity Commands
# ------------------------------------------------------------

def cmd_issue(args):
    if args.name and human_name_exists(args.name):
        error("A store with that name already exists.")

    # -----------------------------
    # Determine passphrase mode
    # -----------------------------
    if args.plaintext and args.passphrase:
        error("Cannot use --plaintext and --passphrase together.")

    if args.plaintext:
        passphrase = None

    elif args.passphrase:
        passphrase = args.passphrase

    else:
        # default: encrypted, prompt user
        import getpass
        pw = getpass.getpass("Passphrase: ")
        confirm = getpass.getpass("Confirm: ")
        if pw != confirm:
            error("Passphrases do not match.")
        passphrase = pw

    print("Issuing new store identity...")
    store_id = issue_identity(passphrase=passphrase)

    if args.name:
        save_metadata(store_id, {"name": args.name})
        print(f"Issued store {args.name} ({store_id})")
    else:
        print(f"Issued store {store_id}")



def cmd_list(args):
    """
    List all local stores in ~/.loam/stores.
    """
    base = Path.home() / ".loam" / "stores"

    if not base.exists():
        print("No stores found.")
        return

    dirs = [p for p in base.iterdir() if p.is_dir()]
    if not dirs:
        print("No stores found.")
        return

    print("Stores:\n")
    print(f"{'Name':<20} {'Store ID':<38} {'Identity Fingerprint'}")
    print(f"{'-'*20} {'-'*38} {'-'*64}")

    for p in sorted(dirs, key=lambda x: x.name):
        store_id = p.name

        # Load metadata for label
        metadata = load_metadata(store_id)
        label = metadata.get("name", "(unnamed)")

        # Load dossier for identity fingerprint
        dossier_path = p / "dossier" / "root_dossier.json"
        dossier = _load_json(dossier_path) or {}
        identity_block = dossier.get("identity", {})
        fingerprint = identity_block.get("identity_fingerprint", "(none)")

        print(f"{label:<20} {store_id:<38} {fingerprint}")




def cmd_verify_identity(args):
    """
    Full diagnostic identity verification.
    Mirrors the substrate trust pipeline, but offline and without a runtime.
    Reports:
      - pass/fail for each trust boundary
      - reason + details for failures
      - overall trusted/untrusted status
    """

    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    print(f"Verifying identity: {name} ({store_id})")
    print()

    results = []

    # ------------------------------------------------------------
    # Helper to run a check and collect structured results
    # ------------------------------------------------------------
    def run_check(label, fn):
        try:
            ok, info = fn()
            if ok:
                results.append((label, True, None, None))
            else:
                results.append((label, False, info.get("reason"), info))
        except Exception as e:
            # Unexpected exception → treat as failure
            results.append((label, False, str(e), None))

    # ------------------------------------------------------------
    # 1. Duplicate identity fingerprints
    # ------------------------------------------------------------
    def check_duplicates():
        root = stores_root()
        if not root.exists():
            return True, {}

        seen = {}
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            sid = entry.name
            pub = public_key_file(sid)
            if not pub.exists():
                continue
            fp = build_identity_fingerprint_v1(sid)
            seen.setdefault(fp, []).append(sid)

        duplicates = {fp: ids for fp, ids in seen.items() if len(ids) > 1}
        if duplicates:
            return False, {"reason": "duplicate_identity_fingerprint", "duplicates": duplicates}
        return True, {}

    run_check("duplicate_identity_fingerprints", check_duplicates)

    # ------------------------------------------------------------
    # 2. Identity root (dossier + lineage + folder integrity)
    # ------------------------------------------------------------
    def check_identity_root():
        try:
            verify_root_dossier(store_id)
            verify_lineage(store_id)
            ok, info = verify_identity_folder(store_id)
            if not ok:
                return False, {"reason": info.get("reason"), "details": info}
            return True, {}
        except Exception as e:
            return False, {"reason": str(e)}

    run_check("identity_root", check_identity_root)

    # ------------------------------------------------------------
    # 3. Revocation
    # ------------------------------------------------------------
    def check_revocation_status():
        fp = build_identity_fingerprint_v1(store_id)
        try:
            check_revocation(fp)
            return True, {}
        except Exception as e:
            return False, {"reason": "revoked", "details": str(e)}

    run_check("revocation", check_revocation_status)

    # ------------------------------------------------------------
    # 4. Continuity chain
    # ------------------------------------------------------------
    def check_continuity():
        ok, info = verify_chain(store_id)
        if not ok:
            return False, {"reason": info.get("reason"), "details": info}
        return True, {}

    run_check("continuity_chain", check_continuity)

    # ------------------------------------------------------------
    # 5. Chronicle chain
    # ------------------------------------------------------------
    def check_chronicle_status():
        ok = verify_chronicle(store_id)
        if not ok:
            return False, {"reason": "chronicle_verification_failed"}
        return True, {}

    run_check("chronicle_chain", check_chronicle_status)

    # 1. Chronicle attestation (non‑blocking)
    level, reason, details = attest_chronicle(store_id)
    print_chronicle_attestation(level, reason, details)
    # ------------------------------------------------------------
    # 6. Identity fingerprint correctness
    # ------------------------------------------------------------
    def check_identity_fingerprint():
        last = load_last_record(store_id)
        if not last:
            return True, {}  # fresh identity

        identity_fp = build_identity_fingerprint_v1(store_id)
        expected_hash = compute_identity_fingerprint_hash_v1(identity_fp)

        if last.get("identity_fingerprint_hash") != expected_hash:
            return False, {
                "reason": "identity_fingerprint_mismatch",
                "details": {"last_seq": last.get("seq")}
            }
        return True, {}

    run_check("identity_fingerprint", check_identity_fingerprint)

    # ------------------------------------------------------------
    # 7. State continuity boundary
    # ------------------------------------------------------------
    def check_state_continuity():
        state_cfg = metadata.get("state", {})
        if not state_cfg.get("hashing_enabled", False):
            return True, {}  # no boundary

        state_dir = state_cfg.get("path")
        if not state_dir:
            return False, {"reason": "missing_state_path"}

        last = load_last_record(store_id)
        if not last:
            return True, {}  # no continuity yet

        last_hash = last.get("state_hash")
        current_hash = compute_state_hash(state_dir)

        if last_hash is not None and last_hash != current_hash:
            return False, {
                "reason": "state_hash_mismatch",
                "details": {
                    "last_state_hash": last_hash,
                    "current_state_hash": current_hash,
                }
            }
        return True, {}

    run_check("state_continuity", check_state_continuity)

    # ------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------
    failures = [r for r in results if not r[1]]
    passes = [r for r in results if r[1]]

    if failures:
        print("Overall status: INVALID\n")
        print("Failures:")
        for label, ok, reason, info in failures:
            print(f"  ✗ {label}")
            print(f"      reason: {reason}")
            if info:
                print(f"      details: {info}")
            print()
    else:
        print("Overall status: VALID AND TRUSTED\n")

    print("Passes:")
    for label, ok, _, _ in passes:
        print(f"  ✓ {label}")



def list_identity_ids():
    identities_root = Path(os.path.expanduser("~/.loam/stores"))
    if not identities_root.exists():
        return []

    return [
        d.name
        for d in identities_root.iterdir()
        if d.is_dir()
    ]


def human_name_exists(name):
    for ident in list_identity_ids():
        meta = load_metadata(ident)
        if meta.get("name") == name:
            return True
    return False


def cmd_name(args):
    store_id = resolve_store_identifier(args.store)
    
    if args.new_name and human_name_exists(args.new_name):
        error("That name is already in use.")

    new_name = args.new_name

    metadata = load_metadata(store_id)

    if new_name is None:
        print(metadata.get("name", store_id))
        return

    metadata["name"] = new_name
    save_metadata(store_id, metadata)

    print(f"Updated store '{store_id}' name to '{new_name}'")


def cmd_rename(args):
    store_id = resolve_store_identifier(args.store)

    if human_name_exists(args.new_name):
        error("That name is already in use.")

    new_name = args.new_name

    metadata = load_metadata(store_id)
    old_name = metadata.get("name", store_id)

    metadata["name"] = new_name
    save_metadata(store_id, metadata)

    print(f"Renamed store {old_name} ({store_id}) → {new_name}")


def _load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _parse_log_lines(path):
    if not path.exists():
        return None, 0

    entries = []
    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            # Case 1: pure JSON line
            try:
                entries.append(json.loads(line))
                continue
            except Exception:
                pass

            # Case 2: timestamp + JSON
            try:
                ts, json_part = line.split(" ", 1)
                entries.append(json.loads(json_part))
                continue
            except Exception:
                pass

            continue

    if not entries:
        return None, 0

    return entries[-1], len(entries)


def _tail_continuity(identity_dir):
    return _parse_log_lines(identity_dir / "continuity" / "continuity.log")


def _tail_chronicle(identity_dir):
    return _parse_log_lines(identity_dir / "chronicle" / "chronicle.log")


def cmd_show(args):
    store_id = resolve_store_identifier(args.store)
    base = Path(os.path.expanduser(f"~/.loam/stores/{store_id}"))

    # -----------------------------
    # Load metadata (label)
    # -----------------------------
    metadata = _load_json(base / "metadata.json") or {}
    label = metadata.get("name", "<unnamed>")

    # -----------------------------
    # Load dossier (canonical identity)
    # -----------------------------
    dossier_path = base / "dossier" / "root_dossier.json"
    dossier = _load_json(dossier_path) or {}

    identity_block = dossier.get("identity", {})
    identity_fp = identity_block.get("identity_fingerprint")
    public_key_b64 = identity_block.get("public_key_b64")

    created_at = dossier.get("created_at")
    origin = dossier.get("origin", {})
    signature = dossier.get("signature")
    schema_version = dossier.get("schema_version")

    # -----------------------------
    # Load lineage
    # -----------------------------
    lineage = _load_json(base / "lineage" / "lineage.json") or {}
    parent_id = lineage.get("parent_id")
    ancestry = lineage.get("ancestry", [])

    # -----------------------------
    # Load identity.toml
    # -----------------------------
    identity_toml = {}
    identity_toml_path = base / "identity.toml"
    if identity_toml_path.exists():
        with open(identity_toml_path, "rb") as f:
            identity_toml = tomllib.load(f)

    state_path = identity_toml.get("state", {}).get("path")
    hashing_enabled = identity_toml.get("state", {}).get("hashing_enabled")

    # -----------------------------
    # Continuity
    # -----------------------------
    cont_head, cont_count = _tail_continuity(base)
    cont_seq = cont_head.get("seq") if cont_head else None
    cont_hash = cont_head.get("hash") if cont_head else None

    # -----------------------------
    # Chronicle
    # -----------------------------
    chron_head, chron_count = _tail_chronicle(base)
    chron_event = chron_head.get("event_type") if chron_head else None
    chron_hash = chron_head.get("event_hash") if chron_head else None

    level, reason, details = attest_chronicle(store_id)

    # -----------------------------
    # Private key backend (optional)
    # -----------------------------
    desc_path = base / "keys" / "key_descriptor.json"
    desc = _load_json(desc_path) if desc_path.exists() else {}
    priv_kind = desc.get("kind", "unknown")
    priv_path = desc.get("path", "unknown")

    # -----------------------------
    # Revocation
    # -----------------------------
    revoked = False
    if REVOCATION_PATH.exists():
        rev_data = json.loads(REVOCATION_PATH.read_text())
        for entry in rev_data.get("revoked", []):
            if entry.get("identity_fingerprint") == identity_fp:
                revoked = True
                break

    # -----------------------------
    # Output
    # -----------------------------
    print(f"Name: {label}")
    print(f"Store ID: {store_id}")
    print(f"Identity: {identity_fp}")
    print(f"Directory: {base}")
    print()

    print("Created:")
    print(f"  {created_at}")
    print(f"  origin: {origin.get('user')}@{origin.get('hostname')} ({origin.get('kind')})")
    print()

    print("Keys:")
    print(f"  public key: present (base64, {len(public_key_b64)} bytes)")
    print(f"  private key: present (kind={priv_kind}, path={priv_path})")
    print(f"  descriptor: {desc_path.name if desc_path.exists() else '(none)'}")
    print()

    print("Dossier:")
    print(f"  schema_version: {schema_version}")
    print(f"  signature: {signature[:16]}...")
    print()

    print("Lineage:")
    print(f"  parent: {parent_id or 'none'}")
    print(f"  ancestry length: {len(ancestry)}")
    print()

    print("Continuity:")
    print(f"  latest seq: {cont_seq}")
    print(f"  latest hash: {cont_hash}")
    print(f"  entries: {cont_count}")
    print(f"  path: continuity/continuity.log")
    print()

    print("Chronicle:")
    print(f"  entries: {chron_count}")
    print(f"  latest event: {chron_event}")
    print(f"  latest event_hash: {chron_hash}")
    print(f"  path: chronicle/chronicle.log")
    print()
    print_chronicle_attestation(level, reason, details)
    print()

    print("Identity Config:")
    print(f"  state path: {state_path}")
    print(f"  hashing_enabled: {hashing_enabled}")
    print()

    print("Revocation:")
    print(f"  status: {'revoked' if revoked else 'not revoked'}")
    print(f"  source: {REVOCATION_PATH}")
    print()



def cmd_revoke(args):
    """
    Revoke an identity by fingerprint.
    Always writes the revocation entry.
    Attempts to attach metadata (best effort).
    """

    fp = args.fingerprint.strip().lower()

    # ------------------------------------------------------------
    # Validate fingerprint format
    # ------------------------------------------------------------
    if not re.match(r"^[0-9a-fA-F]{64}$", fp):
        print(f"Invalid fingerprint (must be 64 hex chars): {fp}")
        return

    # ------------------------------------------------------------
    # Load or initialize revocation list
    # ------------------------------------------------------------
    if REVOCATION_PATH.exists():
        data = json.loads(REVOCATION_PATH.read_text())
    else:
        data = {"revoked": []}

    # Avoid duplicates
    for entry in data.get("revoked", []):
        if entry.get("identity_fingerprint") == fp:
            print(f"Identity already revoked: {fp}")
            return

    # ------------------------------------------------------------
    # Try to resolve metadata (best effort)
    # ------------------------------------------------------------
    store_id = None
    name = None

    for sid in list_identity_ids():
        dossier_path = store_path(sid) / "dossier" / "root_dossier.json"
        if not dossier_path.exists():
            continue

        try:
            dossier = json.loads(dossier_path.read_text())
        except Exception:
            continue

        identity_block = dossier.get("identity")
        if not identity_block:
            continue

        desc_fp = identity_block.get("identity_fingerprint")
        if not desc_fp:
            continue

        if desc_fp.lower() == fp:
            store_id = sid
            meta = load_metadata(sid)
            name = meta.get("name")
            break

    # ------------------------------------------------------------
    # Optional human note
    # ------------------------------------------------------------
    note = None
    if args.note:
        note = args.note
    else:
        # Interactive prompt
        try:
            note = input("Add a note for this revocation (optional): ").strip()
            if not note:
                note = None
        except Exception:
            note = None

    # ------------------------------------------------------------
    # Build revocation entry (always written)
    # ------------------------------------------------------------
    entry = {
        "identity_fingerprint": fp,
        "store_id": store_id,
        "name": name,
        "note": note,
        "revoked_at": datetime.utcnow().isoformat() + "Z",
    }

    data["revoked"].append(entry)
    REVOCATION_PATH.write_text(json.dumps(data, indent=2))

    # ------------------------------------------------------------
    # Output
    # ------------------------------------------------------------
    print(f"Revoked identity: {fp}")
    if name:
        print(f"  Name: {name}")
    if store_id:
        print(f"  Store ID: {store_id}")
    if note:
        print(f"  Note: {note}")





def cmd_unrevoke(args):
    """
    Remove an identity from the revocation list.
    Accepts either fingerprint or name.
    """

    ident = args.fingerprint.strip().lower()

    if not REVOCATION_PATH.exists():
        print("No revocation list exists.")
        return

    data = json.loads(REVOCATION_PATH.read_text())
    revoked = data.get("revoked", [])

    # Determine if ident is a fingerprint (64 hex chars)
    is_fp = bool(re.match(r"^[0-9a-fA-F]{64}$", ident))

    matches = []

    for entry in revoked:
        fp = entry.get("identity_fingerprint", "").lower()
        name = (entry.get("name") or "").lower()

        if is_fp:
            if fp == ident:
                matches.append(entry)
        else:
            if name == ident:
                matches.append(entry)

    if not matches:
        print(f"Identity not found in revocation list: {ident}")
        return

    if len(matches) > 1:
        print(f"Multiple matches found for '{ident}', refusing to unrevoke.")
        return

    # Remove the entry
    entry = matches[0]
    revoked.remove(entry)

    # Save
    data["revoked"] = revoked
    REVOCATION_PATH.write_text(json.dumps(data, indent=2))

    print(f"Unrevoked identity: {entry.get('identity_fingerprint')}")
    if entry.get("name"):
        print(f"  Name: {entry.get('name')}")




def cmd_revoked(args):
    """
    Print all revoked identities from revocation.json.
    """
    if not REVOCATION_PATH.exists():
        print("No revoked identities.")
        return

    data = json.loads(REVOCATION_PATH.read_text())
    entries = data.get("revoked", [])

    if not entries:
        print("No revoked identities.")
        return

    print("Revoked identities:\n")

    for e in entries:
        fp = e.get("identity_fingerprint")
        name = e.get("name") or "(unknown)"
        store_id = e.get("store_id") or "(unknown)"
        note = e.get("note")  # <-- THIS is what was missing
        revoked_at = e.get("revoked_at")

        print(f"Fingerprint: {fp}")
        print(f"  Name: {name}")
        print(f"  Store ID: {store_id}")
        if note:
            print(f"  Note: {note}")
        print(f"  Revoked at: {revoked_at}")
        print()



def cmd_encrypt_identity(args):
    store_id = resolve_store_identifier(args.identity)

    pw = getpass.getpass("New passphrase: ")
    confirm = getpass.getpass("Confirm: ")
    if pw != confirm:
        error("Passphrases do not match.")

    # Identity private key migration
    migrate_plaintext_to_passphrase(store_id, pw)

    # Master key migration (only if plaintext exists)
    if master_key_plaintext_exists(store_id):
        migrate_master_key_to_passphrase(store_id, pw)

    # Record mutation
    ksctx = KeySourceContext(passphrase=pw)
    inscribe_identity_mutation(
        store_id,
        mutation_type="keysource_migration",
        ksctx=ksctx,
        old_value="raw_ed25519",
        new_value="passphrase_encrypted",
    )

    print(f"Identity {store_id} encrypted successfully.")


def cmd_decrypt_identity(args):
    store_id = resolve_store_identifier(args.identity)

    pw = getpass.getpass("Passphrase: ")

    # Identity private key migration
    migrate_passphrase_to_plaintext(store_id, pw)

    # Master key migration (only if encrypted exists)
    if master_key_encrypted_exists(store_id):
        migrate_master_key_to_plaintext(store_id, pw)

    # Record mutation
    ksctx = KeySourceContext(passphrase=pw)
    inscribe_identity_mutation(
        store_id,
        mutation_type="keysource_migration",
        ksctx=ksctx,
        old_value="passphrase_encrypted",
        new_value="raw_ed25519",
    )

    print(f"Identity {store_id} decrypted successfully.")



def cmd_unlock_identity(args):
    store_id = resolve_store_identifier(args.identity)

    pw = getpass.getpass("Passphrase: ")

    # validate passphrase by trying to load signer
    ksctx = KeySourceContext(passphrase=pw)

    # this will raise if passphrase is wrong
    load_signer_from_keysource(store_id, ksctx=ksctx)

    # cache for future processes
    set_cached_passphrase(store_id, pw)

    # optionally prime in‑process cache too
    _passphrase_cache[store_id] = pw

    print(f"Identity {store_id} unlocked for this session.")


def cmd_lock_identity(args):
    store_id = resolve_store_identifier(args.identity)
    clear_cached_passphrase(store_id)
    _passphrase_cache.pop(store_id, None)
    print(f"Identity {store_id} locked for this session.")

def cmd_lock_all_identities(args):
    clear_all_cached_passphrases()
    _passphrase_cache.clear()
    print("All identities locked for this session.")
