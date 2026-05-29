# loam/cli/main.py

import argparse
import sys

# Identity subsystem
from loam.cli.identity import (
    cmd_decrypt_identity,
    cmd_encrypt_identity,
    cmd_issue,
    cmd_list,
    cmd_lock_all_identities,
    cmd_lock_identity,
    cmd_revoke,
    cmd_revoked,
    cmd_show,
    cmd_unlock_identity,
    cmd_unrevoke,
    cmd_verify_identity,
    cmd_name,
    cmd_rename,
)

# Logs subsystem
from loam.cli.logs import (
    cmd_interlaced_logs,
    cmd_show_logs,
    cmd_verify_logs,
)

# Secrets subsystem
from loam.cli.secrets import (
    cmd_secret_create,
    cmd_secret_delete,
    cmd_secret_list,
    cmd_secret_load,
    cmd_secret_rotate,
)

# State subsystem
from loam.cli.state import (
    cmd_state_enable,
    cmd_state_disable,
    cmd_state_set_path,
    cmd_state_show,
    cmd_state_unset_path,
)

# Ops subsystem
from loam.cli.ops import (
    cmd_init,
    cmd_verify_artifact,
    cmd_export_identity,
    cmd_import_identity,
)

# Run subsystem
from loam.cli.run import cmd_run
# Exec subsystem
from loam.cli.exec import cmd_exec

def build_parser():
    parser = argparse.ArgumentParser(prog="loam", description="Loam substrate CLI")
    subparsers = parser.add_subparsers(dest="system", required=True)
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show full Python tracebacks for debugging"
    )

    # ------------------------------------------------------------
    # Identity subsystem
    # ------------------------------------------------------------
    identity = subparsers.add_parser("identity", help="Manage identity stores")
    id_sub = identity.add_subparsers(dest="action", required=True)

    #issue
    p = id_sub.add_parser("issue", help="Issue a new identity store")
    p.add_argument("--name", help="Human-friendly name for the new store")

    # NEW: issuance mode flags
    p.add_argument(
        "--plaintext",
        action="store_true",
        help="Issue a plaintext identity (insecure; default is encrypted)"
    )

    p.add_argument(
        "--passphrase",
        help="Passphrase for encrypted issuance (non-interactive)"
    )

    p.set_defaults(func=cmd_issue)

    # identity list
    p = id_sub.add_parser("list", help="List all identity stores")
    p.set_defaults(func=cmd_list)

    # identity show
    p = id_sub.add_parser("show", help="Show store details")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_show)

    # identity verify
    p = id_sub.add_parser("verify", help="Verify store integrity")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_verify_identity)

    # identity name
    p = id_sub.add_parser("name", help="Get or set a store's human-friendly name")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.add_argument("new_name", nargs="?", help="New name (omit to show current)")
    p.set_defaults(func=cmd_name)

    # identity rename
    p = id_sub.add_parser("rename", help="Rename a store")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.add_argument("new_name", help="New name for the store")
    p.set_defaults(func=cmd_rename)

    # identity revoke
    p = id_sub.add_parser("revoke", help="Revoke an identity by identity fingerprint")
    p.add_argument(
        "fingerprint",
        help="Identity fingerprint (sha256:...) to revoke"
    )
    p.add_argument(
        "--note",
        help="Optional human note to attach to the revocation entry",
    )
    p.set_defaults(func=cmd_revoke)

    # identity unrevoke
    p = id_sub.add_parser("unrevoke", help="Remove an identity from the revocation list")
    p.add_argument(
        "fingerprint",
        help="Identity fingerprint (sha256:...) to unrevoke"
    )
    p.set_defaults(func=cmd_unrevoke)

    # identity revoked
    p = id_sub.add_parser("revoked", help="List all revoked identities")
    p.set_defaults(func=cmd_revoked)

    #encrypt keys
    p = id_sub.add_parser("encrypt", help="Encrypt an existing identity store")
    p.add_argument(
        "identity",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_encrypt_identity)
    
    #decrypt keys
    p = id_sub.add_parser("decrypt", help="Decrypt an existing identity store")
    p.add_argument(
        "identity",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_decrypt_identity)

    # session unlock
    p = id_sub.add_parser("unlock", help="Unlock an encrypted identity for this session")
    p.add_argument(
        "identity",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_unlock_identity)

    # session lock
    p = id_sub.add_parser("lock", help="Lock an identity for this session")
    p.add_argument(
        "identity",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_lock_identity)

    # session lock-all
    p = id_sub.add_parser("lock-all", help="Lock all identities for this session")
    p.set_defaults(func=cmd_lock_all_identities)



    # ------------------------------------------------------------
    # Logs subsystem
    # ------------------------------------------------------------
    logs = subparsers.add_parser(
        "logs",
        help="Inspect continuity and chronicle logs"
    )
    logs_sub = logs.add_subparsers(dest="action", required=True)

    # logs show
    p = logs_sub.add_parser("show", help="Show continuity or chronicle log")
    p.add_argument(
        "chain_type",
        choices=["continuity", "chronicle"],
        help="Which log to show"
    )
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_show_logs)

    # logs verify
    p = logs_sub.add_parser("verify", help="Verify continuity and chronicle logs")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_verify_logs)

    # logs interlaced
    p = logs_sub.add_parser(
        "interlaced",
        help="Show continuity and chronicle logs interlaced"
    )
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_interlaced_logs)



    # ------------------------------------------------------------
    # Secrets subsystem
    # ------------------------------------------------------------
    secret = subparsers.add_parser("secret", help="Manage secrets")
    secret_sub = secret.add_subparsers(dest="action", required=True)

    # secret create
    p = secret_sub.add_parser("create", help="Create a secret")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.add_argument("name", help="Secret name")
    p.add_argument("--value", help="Secret value (optional; will prompt if omitted)")
    p.set_defaults(func=cmd_secret_create)

    # secret list
    p = secret_sub.add_parser("list", help="List secrets")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_secret_list)

    # secret load (TEMPORARY)
    p = secret_sub.add_parser("load", help="Load a secret (TEMPORARY — will be removed)")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.add_argument("name", help="Secret name")
    p.set_defaults(func=cmd_secret_load)

    # secret rotate
    p = secret_sub.add_parser("rotate", help="Rotate a secret")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.add_argument("name", help="Secret name")
    p.add_argument("--value", help="New secret value (optional; will prompt if omitted)")
    p.set_defaults(func=cmd_secret_rotate)

    # secret delete
    p = secret_sub.add_parser("delete", help="Delete a secret")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.add_argument("name", help="Secret name")
    p.set_defaults(func=cmd_secret_delete)

    # ------------------------------------------------------------
    # State subsystem
    # ------------------------------------------------------------
    state = subparsers.add_parser("state", help="Manage agent state hashing")
    st_sub = state.add_subparsers(dest="action", required=True)

    # state enable
    p = st_sub.add_parser("enable", help="Enable state hashing for an agent")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.add_argument(
        "--path",
        help="Absolute path to the agent's state directory"
    )
    p.set_defaults(func=cmd_state_enable)

    # state disable
    p = st_sub.add_parser("disable", help="Disable state hashing for an agent")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_state_disable)

    # state show
    p = st_sub.add_parser("show", help="Show state hashing status for an agent")
    p.add_argument(
        "store",
        help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_state_show)

    # state set-path
    p = st_sub.add_parser(
        "set-path",
        help="Set a state path without enabling hashing (identity becomes stateful, hashing disabled)."
    )
    p.add_argument(
    "store",
    help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.add_argument("--path", required=True, help="Absolute path to the state directory.")
    p.set_defaults(func=cmd_state_set_path)

    # state unset-path
    p = st_sub.add_parser(
        "unset-path",
        help="Remove the state path and disable hashing (identity becomes stateless)."
    )
    p.add_argument(
    "store",
    help="Store identifier (name, identity fingerprint, or store UUID)"
    )
    p.set_defaults(func=cmd_state_unset_path)

    
    
    # ------------------------------------------------------------
    # Ops subsystem
    # ------------------------------------------------------------
    ops = subparsers.add_parser(
        "ops",
        help="Operational tools",
        description="Low-level tools for exporting and importing identity stores."
    )
    ops_sub = ops.add_subparsers(dest="action", required=True)
   
    # -------------------------
    # ops init
    # -------------------------
    p = ops_sub.add_parser(
    "init",
    help="Initialize the Loam substrate",
    description="Create ~/.loam and namespace.json if missing."
)
    p.set_defaults(func=cmd_init)

    # -------------------------
    # ops verifyartifact
    # -------------------------
    p = ops_sub.add_parser(
        "verifyartifact",
        help="Verify an artifact (tool or file) against a store's public key",
        description=(
            "Verify an artifact envelope and its signature.\n\n"
            "Examples:\n"
            "  loam ops verifyartifact wintermute2 ./artifact.json\n"
            "  loam ops verifyartifact ed25519:ab12cd... /tmp/x.artifact.json\n"
        )
    )

    p.add_argument(
        "store",
        help="Store identifier (human name, identity fingerprint, or store UUID)"
    )

    p.add_argument(
        "artifact",
        help="Path to the artifact envelope (.artifact.json)"
    )

    p.set_defaults(func=cmd_verify_artifact)

    # -------------------------
    # ops export
    # -------------------------
    p = ops_sub.add_parser(
        "export",
        help="Export a sealed identity store",
        description=(
            "Export a sealed identity store (a store) for transfer or backup.\n\n"
            "Examples:\n"
            "  loam ops export nic --out ./store\n"
            "  loam ops export ed25519:ab12cd... --out /tmp/nic\n"
        )
    )

    p.add_argument(
        "store",
        help="Store identifier (human name, identity fingerprint, or store UUID)"
    )

    p.add_argument(
        "--out",
        required=True,
        metavar="DIR",
        help="Output directory for the exported store"
    )

    p.add_argument(
        "--passphrase",
        help="Passphrase for sealed export (optional; will prompt if omitted)"
    )

    p.set_defaults(func=cmd_export_identity)

    # -------------------------
    # ops import
    # -------------------------
    p = ops_sub.add_parser(
        "import",
        help="Import a sealed identity store",
        description=(
            "Import a sealed identity store previously created with 'loam ops export'.\n\n"
            "Example:\n"
            "  loam ops import ./store\n"
        )
    )

    p.add_argument(
        "store",
        help="Path to the exported identity store directory"
    )

    p.add_argument(
        "--passphrase",
        help="Passphrase for sealed stores (optional; will prompt if omitted)"
    )

    p.set_defaults(func=cmd_import_identity)


    # ------------------------------------------------------------
    # Run subsystem
    # ------------------------------------------------------------
    run = subparsers.add_parser(
        "run",
        help="Run a command inside a Loam store identity"
    )
    #Loam flags
    run.add_argument(
    "--passphrase",
    help="Passphrase for decrypting encrypted identities",
    )
    run.add_argument(
        "--python-driver",
        action="store_true",
        help="Use the LocalPythonDriver instead of the native driver"
    )
    run.add_argument(
        "--legacy-python",
        action="store_true",
        help="Run agent as a legacy Python module (agent()/main())"
    )
    #positionals
    run.add_argument(
        "store_id",
        help="Store identifier (name, identity fingerprint, or UUID)"
    )
    run.add_argument(
        "exec_path",
        help="Path to the executable or script to run"
    )
    run.add_argument(
    "args",
    nargs="*",
    help="Arguments passed to the executable (use -- to separate agent flags)"
    )

    run.set_defaults(func=cmd_run)

    # ------------------------------------------------------------
    # Exec subsystem
    # ------------------------------------------------------------
    exec_p = subparsers.add_parser(
        "exec",
        help="Execute a program inside a Loam store identity"
    )

    # Loam flags
    exec_p.add_argument(
        "--passphrase",
        help="Passphrase for decrypting encrypted identities",
    )

    # positionals
    exec_p.add_argument(
        "store_id",
        help="Store identifier (name, identity fingerprint, or UUID)"
    )
    exec_p.add_argument(
        "program",
        help="Path to the program to execute"
    )

    # program args
    exec_p.add_argument(
        "args",
        nargs="*",
        help="Arguments passed to the program (use -- to separate Loam flags)"
    )

    exec_p.set_defaults(func=cmd_exec)


    return parser


def _main(args):
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        return _main(args)
    except RuntimeError as e:
        if args.debug:
            raise
        print(f"error: {e}")
        sys.exit(1)
    except Exception as e:
        if args.debug:
            raise
        print(f"unexpected error: {e}")
        sys.exit(1)


