#identity/mutations.py

from loam.identity.identity_fingerprint import (
    build_identity_fingerprint_v1,
    compute_identity_fingerprint_hash_v1,
)
from loam.chronicle.emitter import emit_chronicle_event
from loam.continuity.append import append_continuity_record, create_continuity_record
from loam.identity.keysources import load_signer_from_keysource

def inscribe_identity_mutation(store_id, mutation_type, ksctx, old_value=None, new_value=None):
    """
    Record an identity mutation in both Continuity and Chronicle.
    """

    # Load signer ONCE — use it for both Chronicle and Continuity
    signer = load_signer_from_keysource(store_id, ksctx=ksctx)


    # 1. Identity fingerprint (physics)
    identity_fp = build_identity_fingerprint_v1(store_id)
    identity_fp_hash = compute_identity_fingerprint_hash_v1(identity_fp)

    # 2. Chronicle event (semantic)
    emit_chronicle_event(
        store_id,
        "identity_mutation",
        {
            "mutation": mutation_type,
            "old_value": old_value,
            "new_value": new_value,
        },
        signer=signer,   
    )

    # 3. Continuity record (physics)
    state_hash = None  # identity mutations never include a state hash

    record = create_continuity_record(
        store_id,
        identity_fingerprint_hash=identity_fp_hash,
        state_hash=state_hash,
        kind="identity_mutation",
        signer=signer,  
    )

    append_continuity_record(store_id, record)

    return True


