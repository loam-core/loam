Loam Core CLI Reference

The complete command surface of the Loam substrate.

This reference lists:
    • every subsystem
    • every subcommand
    • required/optional arguments
    • one‑line descriptions

It is mechanical, not conceptual. For architecture and mental models, see the Architecture 
Overview.
Top‑Level Structure
Code
loam <system> <action> [args...]

Systems:
    • identity
    • logs
    • secret
    • state
    • ops
    • run
    • exec

1. identity — Manage identity stores
identity issue
Issue a new identity store.
Code
loam identity issue [--name <name>] [--plaintext] [--passphrase <pw>]
Arguments:
    • --name — human‑friendly name
    • --plaintext — issue unencrypted (insecure)
    • --passphrase — non‑interactive encrypted issuance

identity list
List all identity stores.
Code
loam identity list

identity show
Show identity metadata.
Code
loam identity show <store>

identity verify
Verify continuity + store integrity.
Code
loam identity verify <store>

identity name
Get or set a store’s human‑friendly name.
Code
loam identity name <store> [new_name]

identity rename
Rename a store.
Code
loam identity rename <store> <new_name>

identity revoke
Revoke an identity by fingerprint.
Code
loam identity revoke <fingerprint> [--note <text>]

identity unrevoke
Remove an identity from the revocation list.
Code
loam identity unrevoke <fingerprint>

identity revoked
List all revoked identities.
Code
loam identity revoked

identity encrypt
Encrypt an existing identity store.
Code
loam identity encrypt <identity>

identity decrypt
Decrypt an existing identity store.
Code
loam identity decrypt <identity>

identity unlock
Unlock an encrypted identity for this session.
Code
loam identity unlock <identity>

identity lock
Lock an identity for this session.
Code
loam identity lock <identity>

identity lock-all
Lock all identities for this session.
Code
loam identity lock-all

2. logs — Inspect continuity + chronicle
logs show
Show continuity or chronicle log.
Code
loam logs show <continuity|chronicle> <store>

logs verify
Verify continuity and chronicle logs.
Code
loam logs verify <store>

logs interlaced
Show continuity + chronicle interwoven.
Code
loam logs interlaced <store>

3. secret — Manage identity‑scoped secrets
secret create
Create a secret.
Code
loam secret create <store> <name> [--value <value>]

secret list
List secrets.
Code
loam secret list <store>

secret load (temporary)
Load a secret (temporary command).
Code
loam secret load <store> <name>

secret rotate
Rotate a secret.
Code
loam secret rotate <store> <name> [--value <value>]

secret delete
Delete a secret.
Code
loam secret delete <store> <name>

4. state — Manage deterministic state hashing
state enable
Enable state hashing.
Code
loam state enable <store> [--path <abs-path>]

state disable
Disable state hashing.
Code
loam state disable <store>

state show
Show state hashing status.
Code
loam state show <store>

state set-path
Set a state path without enabling hashing.
Code
loam state set-path <store> --path <abs-path>

state unset-path
Remove state path and disable hashing.
Code
loam state unset-path <store>

5. ops — Operational tools
ops verifyartifact
Verify an artifact envelope against an identity’s public key.
Code
loam ops verifyartifact <store> <artifact>

ops export
Export a sealed identity store.
Code
loam ops export <store> --out <dir> [--passphrase <pw>]

ops import
Import a sealed identity store.
Code
loam ops import <store-dir> [--passphrase <pw>]

6. run — Run a Loam‑native agent
Code
loam run [--passphrase <pw>] [--python-driver] [--legacy-python] <store> <exec_path> [args...]

7. exec — Execute a program inside an identity
Code
loam exec [--passphrase <pw>] <store> <program> [args...]

