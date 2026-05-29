# loam/signing/message.py


"""
Signed messaging primitives for Loam.

This module defines the substrate-level envelope format for
store-to-store and agent-to-agent messages. A signed message
provides authenticated, tamper-evident communication between
Loam identities without requiring shared state, shared memory,
or a trusted transport channel.

Message envelopes include:
- store_id: the sender's identity
- timestamp: when the message was created
- message_type: semantic category of the message
- payload_hash: integrity anchor for the payload
- payload: arbitrary message data
- signature: Ed25519 signature over the canonical signing body

The signing body excludes the payload itself, allowing large or
structured payloads without inflating signature size.

This primitive is not currently wired into runtime or agent
execution. It exists to support future features such as:
- multi-agent messaging
- sub-agent delegation
- distributed Loam clusters
- continuity replication
- governance and control messages
- remote execution and RPC

In short: this is the cryptographic foundation for authenticated
messaging in Loam. The transport layer and message routing will
be implemented later.
"""

import time
from uuid import UUID

from loam.crypto.canonical import canonical_json
from loam.crypto.signing import (
    sign_b64,
    verify_b64,
    hash_payload,
    load_pem,
)
from loam.identity.paths import private_key_file, public_key_file


def sign_message(store_id: str, message_type: str, payload: dict):
    """
    Build and sign a message envelope for store-to-store or internal messaging.
    """
    timestamp = int(time.time())
    payload_hash = hash_payload(payload)

    envelope = {
        "store_id": str(store_id),
        "timestamp": timestamp,
        "message_type": message_type,
        "payload_hash": payload_hash,
        "payload": payload,
    }

    # Signing body excludes payload
    signing_body = {
        "store_id": str(store_id),
        "timestamp": timestamp,
        "message_type": message_type,
        "payload_hash": payload_hash,
    }

    private_key_path = private_key_file(store_id)
    private_key_bytes = load_pem(private_key_path)
    signature_b64 = sign_b64(private_key_bytes, canonical_json(signing_body))

    envelope["signature"] = signature_b64
    return envelope


def verify_message(envelope: dict) -> bool:
    """
    Verify a signed message envelope.
    """
    # 1. Recompute the payload hash
    computed_hash = hash_payload(envelope["payload"])

    # 2. If the stored hash doesn't match, fail immediately
    if computed_hash != envelope["payload_hash"]:
        return False

    # 3. Verify the signature over the signing body
    signing_body = {
        "store_id": envelope["store_id"],
        "timestamp": envelope["timestamp"],
        "message_type": envelope["message_type"],
        "payload_hash": envelope["payload_hash"],
    }

    store_id = envelope["store_id"]
    public_key_path = public_key_file(store_id)
    public_key_bytes = load_pem(public_key_path)

    return verify_b64(
        public_key_bytes,
        canonical_json(signing_body),
        envelope["signature"],
    )
