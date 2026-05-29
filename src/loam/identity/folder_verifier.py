#identity/folder_verfier.py
import json
import base64
from typing import Tuple

from loam.identity.identity_fingerprint import build_identity_fingerprint_v1
from loam.identity.master_key import ENCRYPTED_MASTER_KEY_NAME
from loam.identity.paths import (
    secrets_dir,
    store_path,
    public_key_file,
    dossier_file,
    master_key_file,
    master_key_sig_file,
)
from loam.crypto.signing import verify


def verify_identity_folder(store_id: str) -> Tuple[bool, str | None]:
    try:
        # 0. Identity folder existence
        identity_path = store_path(store_id)
        if not identity_path.exists():
            return False, "missing_identity_folder"

        # 1. Public key integrity (raw bytes)
        pub_path = public_key_file(store_id)
        try:
            public_key_bytes = pub_path.read_bytes()
        except Exception as e:
            return False, f"missing_or_unreadable_public_key: {e}"

        if not public_key_bytes:
            return False, "missing_public_key"

        # 2. Dossier integrity + binding
        d_path = dossier_file(store_id)
        if not d_path.exists():
            return False, "missing_root_dossier"

        try:
            dossier = json.loads(d_path.read_text())
        except Exception as e:
            return False, f"invalid_dossier_json: {e}"

        if not isinstance(dossier, dict):
            return False, "invalid_dossier_format"

        if dossier.get("store_id") != store_id:
            return False, "dossier_store_id_mismatch"

        # unified identity fingerprint
        expected_fp = build_identity_fingerprint_v1(store_id)
        if dossier.get("identity", {}).get("identity_fingerprint") != expected_fp:
            return False, "dossier_identity_fingerprint_mismatch"

        # public key must match exactly (base64 raw bytes)
        expected_b64 = base64.b64encode(public_key_bytes).decode()
        if dossier.get("identity", {}).get("public_key_b64") != expected_b64:
            return False, "dossier_public_key_mismatch"

        # 3. Master key integrity
        mk_path = master_key_file(store_id)
        mk_sig_path = master_key_sig_file(store_id)
        enc_mk_path = secrets_dir(store_id) / ENCRYPTED_MASTER_KEY_NAME

        has_plain = mk_path.exists()
        has_enc = enc_mk_path.exists()

        if not (has_plain or has_enc):
            return False, "missing_master_key"
        if not mk_sig_path.exists():
            return False, "missing_master_key_signature"

        try:
            master_key_bytes = mk_path.read_bytes() if has_plain else enc_mk_path.read_bytes()
        except Exception as e:
            return False, f"unreadable_master_key: {e}"

        try:
            master_key_sig = mk_sig_path.read_bytes()
        except Exception as e:
            return False, f"unreadable_master_key_signature: {e}"

        # Verify master key signature using raw Ed25519 verify()
        ok = verify(public_key_bytes, master_key_bytes, master_key_sig)
        if not ok:
            return False, "master_key_signature_invalid"

        # 4. All checks passed
        return True, None

    except Exception as e:
        return False, f"identity_verification_exception: {e}"
