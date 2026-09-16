#identity/unlock.py

from loam.continuity.append import append_unlock_record
from loam.identity.identity_fingerprint import build_identity_fingerprint_v1, compute_identity_fingerprint_hash_v1
from loam.identity.keysources import KeySourceContext, load_signer_from_keysource
from loam.identity.paths import store_path
from loam.runtime.id_runtime import IdentityRuntime


class IdentitySession:
    def __init__(self, *, signer, ksctx, identity_path, mechanism_hash):
        self.signer = signer
        self.ksctx = ksctx
        self.identity_path = identity_path
        self.mechanism_hash = mechanism_hash


def UnlockIdentity(store_id: str, mechanism_hash: str, ksctx: KeySourceContext):
    # Decrypt private key via KeySource -- used only to sign the unlock
    # continuity record below; IdentityRuntime derives its own signer from
    # ksctx/passphrase internally and does not accept a pre-loaded one.
    # 1. derive signer from KeySource for unlock record
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)

    # 2. compute identity_path
    identity_path = store_path(store_id)

    # 3. write continuity unlock record
    identity_fp_hash = compute_identity_fingerprint_hash_v1(
        build_identity_fingerprint_v1(store_id)
    )
    append_unlock_record(
        store_id,
        signer,
        identity_fingerprint_hash=identity_fp_hash,
        mechanism_hash=mechanism_hash,
    )

    # 4. return IdentitySession (identity-plane only)
    return IdentitySession(
        signer=signer,
        ksctx=ksctx,
        identity_path=identity_path,
        mechanism_hash=mechanism_hash,
    )
