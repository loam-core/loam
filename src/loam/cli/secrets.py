# loam/cli/secrets.py

import getpass

from loam.identity.metadata import (
    resolve_store_identifier,
    load_metadata,
)
from loam.identity.keysources import get_passphrase_for_store, load_keysource_descriptor
from loam.identity.keysources import KeySourceContext
from loam.identity.secrets import (
    secret_create,
    secret_list,
    secret_load,   # TODO: REMOVE BEFORE RELEASE
    secret_rotate,
    secret_delete,
)


# ------------------------------------------------------------
# Helper: obtain KeySourceContext
# ------------------------------------------------------------

def _get_ksctx_for_store(store_id: str, args):
    ks = load_keysource_descriptor(store_id)
    kind = ks.get("kind")

    # If identity is plaintext → passwordless mode
    if kind == "raw_ed25519":
        return KeySourceContext(passphrase=None)

    # Otherwise identity is encrypted → passphrase required
    if getattr(args, "passphrase", None):
        return KeySourceContext(passphrase=args.passphrase)

    pw = get_passphrase_for_store(store_id)
    return KeySourceContext(passphrase=pw)


# ------------------------------------------------------------
# Secret: create
# ------------------------------------------------------------

def cmd_secret_create(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    # Determine secret value
    if args.value is not None:
        value = args.value
    else:
        value = getpass.getpass(
            f"Enter secret value for '{args.name}' (store {name} ({store_id})): "
        )

    ksctx = _get_ksctx_for_store(store_id, args)

    secret_create(store_id, args.name, value, ksctx=ksctx)
    print(f"Secret '{args.name}' created for store {name} ({store_id}).")


# ------------------------------------------------------------
# Secret: list
# ------------------------------------------------------------

def cmd_secret_list(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    secrets = secret_list(store_id)
    if not secrets:
        print(f"No secrets found for store {name} ({store_id}).")
        return

    for s in secrets:
        print(f"{s['name']}  (created {s['created_at']})")


# ------------------------------------------------------------
# Secret: load  (TEMPORARY — TODO REMOVE BEFORE RELEASE)
# ------------------------------------------------------------

def cmd_secret_load(args):
    # TODO: REMOVE BEFORE RELEASE — plaintext secrets must never be exposed
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    ksctx = _get_ksctx_for_store(store_id, args)

    try:
        value = secret_load(store_id, args.name, ksctx=ksctx)
        print(value)
    except Exception as e:
        print(f"Error loading secret '{args.name}' for store {name} ({store_id}): {e}")
        raise SystemExit(1)


# ------------------------------------------------------------
# Secret: rotate
# ------------------------------------------------------------

def cmd_secret_rotate(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    if args.value is not None:
        new_value = args.value
    else:
        new_value = getpass.getpass(
            f"Enter new secret value for '{args.name}' (store {name} ({store_id})): "
        )

    ksctx = _get_ksctx_for_store(store_id, args)

    secret_rotate(store_id, args.name, new_value, ksctx=ksctx)
    print(f"Secret '{args.name}' rotated for store {name} ({store_id}).")


# ------------------------------------------------------------
# Secret: delete
# ------------------------------------------------------------

def cmd_secret_delete(args):
    store_id = resolve_store_identifier(args.store)
    metadata = load_metadata(store_id)
    name = metadata.get("name", store_id)

    ksctx = _get_ksctx_for_store(store_id, args)

    try:
        secret_delete(store_id, args.name, ksctx=ksctx)
        print(f"Secret '{args.name}' deleted for store {name} ({store_id}).")
    except Exception as e:
        print(f"Error deleting secret '{args.name}': {e}")
        raise SystemExit(1)
