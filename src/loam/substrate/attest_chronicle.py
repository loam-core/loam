from loam.chronicle.verify import verify_chronicle
from loam.continuity.verify import verify_chain


def attest_chronicle(store_id):
    """
    Chronicle attestation:
      - non-blocking
      - operator-plane only
      - compares Chronicle vs Continuity
      - classifies NOTICE / WARNING / ALERT / ERROR / OK
    """

    # 1. Chronicle integrity report (cryptographic)
    chron = verify_chronicle(store_id)

    # 2. Continuity chain (authoritative)
    cont_ok, cont_info = verify_chain(store_id)

    # continuity last seq (None if no continuity yet)
    last_cont = cont_info.get("last_seq") if cont_info else None

    # chronicle last seq (verify_chronicle should expose this; if not, we extract it)
    last_chron = chron.get("last_seq")

    # ------------------------------------------------------------
    # Case 1: Chronicle missing entirely
    # ------------------------------------------------------------
    if chron["integrity"] == "incomplete" and last_chron is None:
        return (
            "notice",
            "missing_chronicle",
            {
                "chron_last_seq": last_chron,
                "cont_last_seq": last_cont,
            },
        )

    # ------------------------------------------------------------
    # Case 2: Chronicle cryptographically tampered
    # ------------------------------------------------------------
    if chron["integrity"] == "tampered":
        return (
            "alert",
            "chronicle_tampered",
            {
                "warnings": f"{len(chron.get('warnings', []))} integrity failures (hash/signature mismatches)",
                "chron_last_seq": last_chron,
                "cont_last_seq": last_cont,
            },
        )



    # ------------------------------------------------------------
    # Case 3: Continuity missing (fresh identity)
    # ------------------------------------------------------------
    if last_cont is None:
        # Chronicle exists but no continuity yet → normal
        return (
            "ok",
            "chronicle_present_no_continuity_yet",
            {
                "chron_last_seq": last_chron,
                "cont_last_seq": last_cont,
            },
        )

    # ------------------------------------------------------------
    # Case 4: Chronicle ahead of continuity (impossible)
    # ------------------------------------------------------------
    if last_chron is not None and last_chron > last_cont:
        return (
            "error",
            "chronicle_ahead_of_continuity",
            {
                "chron_last_seq": last_chron,
                "cont_last_seq": last_cont,
            },
        )

    # ------------------------------------------------------------
    # Case 5: Chronicle exactly matches continuity (normal)
    # ------------------------------------------------------------
    if last_chron == last_cont:
        return (
            "ok",
            "chronicle_in_sync",
            {
                "chron_last_seq": last_chron,
                "cont_last_seq": last_cont,
            },
        )

    # ------------------------------------------------------------
    # Case 6: Chronicle behind continuity by exactly 1 (normal crash window)
    # ------------------------------------------------------------
    if last_chron == last_cont - 1:
        return (
            "ok",
            "chronicle_lag_normal",
            {
                "chron_last_seq": last_chron,
                "cont_last_seq": last_cont,
            },
        )

    # ------------------------------------------------------------
    # Case 7: Chronicle behind continuity by >1 (truncation)
    # ------------------------------------------------------------
    if last_chron is not None and last_chron < last_cont - 1:
        return (
            "warning",
            "chronicle_truncated",
            {
                "chron_last_seq": last_chron,
                "cont_last_seq": last_cont,
            },
        )

    # ------------------------------------------------------------
    # Fallback (should never happen)
    # ------------------------------------------------------------
    return (
        "notice",
        "chronicle_unclassified_state",
        {
            "chron_last_seq": last_chron,
            "cont_last_seq": last_cont,
            "integrity": chron["integrity"],
        },
    )

