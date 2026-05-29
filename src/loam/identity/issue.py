from datetime import datetime, timezone
from pathlib import Path
import uuid
import json

from loam.continuity.append import append_continuity_record, create_continuity_record
from loam.identity.keysources import KeySourceContext, encrypt_private_key_with_passphrase, load_signer_from_keysource
from loam.identity.paths import (
    store_path,
    keys_dir,
    dossier_dir,
    continuity_dir,
    chronicle_dir,
    secrets_dir,
    private_key_file,
    public_key_file,
)
from loam.identity.keypair import generate_keypair
from loam.identity.dossier import create_root_dossier
from loam.identity.master_key import generate_master_key
from loam.identity.lineage.lineage import create_root_lineage
from loam.chronicle.chronicle import write_chronicle_genesis
from loam.substrate.signer_factory import create_signer
from loam.identity.identity_fingerprint import build_identity_fingerprint_v1, compute_identity_fingerprint_hash_v1



def issue_identity(passphrase: str | None = None):

    """
    Create a new identity store using the modern, unified issuance flow.
    """

    # ------------------------------------------------------------
    # 1. Generate store_id
    # ------------------------------------------------------------
    store_id = str(uuid.uuid4())

    # ------------------------------------------------------------
    # 2. Generate keypair (raw bytes)
    # ------------------------------------------------------------
    private_bytes, public_bytes = generate_keypair()

    # ------------------------------------------------------------
    # 3. Create directory layout
    # ------------------------------------------------------------
    store_path(store_id).mkdir(parents=True, exist_ok=True)
    keys_dir(store_id).mkdir(parents=True, exist_ok=True)
    dossier_dir(store_id).mkdir(parents=True, exist_ok=True)
    continuity_dir(store_id).mkdir(parents=True, exist_ok=True)
    chronicle_dir(store_id).mkdir(parents=True, exist_ok=True)
    secrets_dir(store_id).mkdir(parents=True, exist_ok=True)
    
    #4. Choose plaintext vs passphrase ---
    if passphrase is None:
        # plaintext
        private_key_file(store_id).write_bytes(private_bytes)
        public_key_file(store_id).write_bytes(public_bytes)

        descriptor = {
            "version": 1,
            "kind": "raw_ed25519",
            "path": "private_key",
            "store_id": store_id,
        }
        descriptor_path = store_path(store_id) / "keys" / "key_descriptor.json"
        descriptor_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor_path.write_text(json.dumps(descriptor, indent=2))
    else:
        # passphrase-encrypted
        public_key_file(store_id).write_bytes(public_bytes)
        descriptor = encrypt_private_key_with_passphrase(
            store_id,
            private_bytes,
            passphrase,
        )

    # 4b. Write full identity.toml (policy first, substrate last)

    identity_toml = """# ============================================
    # POLICY CONFIGURATION (USER EDITABLE)
    # ============================================

    [tools]
    allowed = [
    "fs.read",
    "fs.write",
    "fs.delete",
    "fs.list",
    "fs.search",
    "http.request",
    "process.run",
    "state.read",
    "state.write",
    "artifact.emit",
    ]

    [subprocess]
    allowed_commands = ["python3"]
    allowed_paths = ["/usr/bin", "/bin", "/usr/local/bin"]

    [filesystem.mounts]
    # output = "/home/user/documents/agent_output"

    [filesystem]
    allowed_paths = [
    "scratch://",
    "state://",
    "output://",   # example mount
    ]

    [http]
    allowed_domains = [
    "api.github.com",
    "pypi.org",
    "files.pythonhosted.org",
    ]

    [llm]
    allowed_models = ["None"]

    [approvals]
    # empty for now



    # ============================================
    # SUBSTRATE CONFIGURATION (DO NOT EDIT)
    # ============================================

    [identity]
    version = 1

    [state]
    hashing_enabled = false
    """

    toml_path = store_path(store_id) / "identity.toml"
    toml_path.write_text(identity_toml)


    # 5. Compute canonical identity fingerprint (ONE TRUE FP)
    identity_fp = build_identity_fingerprint_v1(store_id)
    identity_fp_hash = compute_identity_fingerprint_hash_v1(identity_fp)

    # 6. Create signer abstraction for identity-plane signing
    ksctx = KeySourceContext(passphrase=passphrase)
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)

    # 7. Create root dossier (signed)
    create_root_dossier(store_id, identity_fp, signer)

    # 8. Create root lineage (signed)
    create_root_lineage(store_id, identity_fp, signer)

    # 9. Continuity genesis (signed)
    record = create_continuity_record(
        store_id,
        signer,
        identity_fingerprint_hash=identity_fp_hash,
        state_hash=None,
    )
    append_continuity_record(store_id, record)

    # 10. Chronicle genesis
    write_chronicle_genesis(store_id, signer, identity_fp)

    # 11. Bootstrap extras
    generate_master_key(store_id, ksctx=ksctx)

    return store_id
