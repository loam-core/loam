# Loam CLI Reference

The complete command surface of the Loam substrate.

This reference lists:
- every subsystem
- every subcommand
- required/optional arguments
- one-line descriptions

It is mechanical, not conceptual. For architecture and mental models, see the Architecture Overview.

### Store Identifiers

Anywhere the CLI expects a <store> argument, you may supply any of the following:

Human‑friendly name — the name you assigned with identity issue --name or identity name

Store UUID — the directory name under ~/.loam/stores/

Identity fingerprint — the cryptographic fingerprint shown in identity show

All three forms resolve to the same identity store.
If a command requires a specific form (rare), it is noted explicitly.

## Top-Level Structure

```bash
loam <system> <action> [args...]
```

### Systems

- `identity`
- `logs`
- `secret`
- `state`
- `ops`
- `run`
- `exec`

## 1. `identity` — Manage identity stores

### `identity issue`
Issue a new identity store.

```bash
loam identity issue [--name <name>] [--plaintext] [--passphrase <pw>]
```

Arguments:

- `--name` — human-friendly name
- `--plaintext` — issue unencrypted (insecure)
- `--passphrase` — non-interactive encrypted issuance

### `identity list`
List all identity stores.

```bash
loam identity list
```

### `identity show`
Show identity metadata.

```bash
loam identity show <store>
```

### `identity verify`
Verify continuity and store integrity.

```bash
loam identity verify <store>
```

### `identity name`
Get or set a store’s human-friendly name.

```bash
loam identity name <store> [new_name]
```

### `identity rename`
Rename a store.

```bash
loam identity rename <store> <new_name>
```

### `identity revoke`
Revoke an identity by fingerprint.

```bash
loam identity revoke <fingerprint> [--note <text>]
```

### `identity unrevoke`
Remove an identity from the revocation list.

```bash
loam identity unrevoke <fingerprint>
```

### `identity revoked`
List all revoked identities.

```bash
loam identity revoked
```

### `identity encrypt`
Encrypt an existing identity store.

```bash
loam identity encrypt <identity>
```

### `identity decrypt`
Decrypt an existing identity store.

```bash
loam identity decrypt <identity>
```

### `identity unlock`
Unlock an encrypted identity for this session.

```bash
loam identity unlock <identity>
```

### `identity lock`
Lock an identity for this session.

```bash
loam identity lock <identity>
```

### `identity lock-all`
Lock all identities for this session.

```bash
loam identity lock-all
```

## 2. `logs` — Inspect continuity and chronicle

### `logs show`
Show continuity or chronicle log.

```bash
loam logs show <continuity|chronicle> <store>
```

### `logs verify`
Verify continuity and chronicle logs.

```bash
loam logs verify <store>
```

### `logs interlaced`
Show continuity and chronicle interwoven.

```bash
loam logs interlaced <store>
```

## 3. `secret` — Manage identity-scoped secrets

### `secret create`
Create a secret.

```bash
loam secret create <store> <secret_name> [--value <value>]
```

### `secret list`
List secrets.

```bash
loam secret list <store>
```

### `secret load`
Load a secret (temporary command).

```bash
loam secret load <store> <secret_name>
```

### `secret rotate`
Rotate a secret.

```bash
loam secret rotate <store> <secret_name> [--value <value>]
```

### `secret delete`
Delete a secret.

```bash
loam secret delete <store> <secret_name>
```

## 4. `state` — Manage deterministic state hashing

### `state enable`
Enable state hashing.

```bash
loam state enable <store> [--path <abs-path>]
```

### `state disable`
Disable state hashing.

```bash
loam state disable <store>
```

### `state show`
Show state hashing status.

```bash
loam state show <store>
```

### `state set-path`
Set a state path without enabling hashing.

```bash
loam state set-path <store> --path <abs-path>
```

### `state unset-path`
Remove state path and disable hashing.

```bash
loam state unset-path <store>
```

## 5. `ops` — Operational tools

### `ops verifyartifact`
Verify an artifact envelope against an identity’s public key.

```bash
loam ops verifyartifact <store> <artifact>
```

### `ops export`
Export a sealed identity store.

```bash
loam ops export <store> --out <dir> [--passphrase <pw>]
```

### `ops import`
Import a sealed identity store.

```bash
loam ops import <store-dir> [--passphrase <pw>]
```

## 6. `run` — Run a Loam-native agent

```bash
loam run [--python-driver] [--legacy-python] <store> <exec_path> [--passphrase <pw>] [args...]
```

## 7. `exec` — Execute a program inside an identity

```bash
loam exec <store> <program> [--passphrase <pw>] [args...]
```

