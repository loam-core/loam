# loam/cli/run.py

from hashlib import sha256
from pathlib import Path

from loam.identity.keysources import KeySourceContext
from loam.identity.metadata import resolve_store_identifier

from loam.identity.unlock import UnlockIdentity
from loam.runtime.agent_runtime import AgentRuntime
from loam.substrate.attest_chronicle import attest_chronicle


def cmd_run(args):
    agent_args = args.args

    store_id = resolve_store_identifier(args.store_id)

    level, reason, details = attest_chronicle(store_id)
    if level != "ok":
        print_chronicle_attestation(level, reason, details)

    exec_path = Path(args.exec_path).expanduser().resolve()

    # -------------------------------
    # NEW: UnlockIdentity
    # -------------------------------
    ksctx = KeySourceContext(passphrase=args.passphrase)
    mechanism_hash = sha256(args.passphrase.encode()).hexdigest()
    session = UnlockIdentity(store_id, mechanism_hash, ksctx)

    # -------------------------------
    # NEW: Construct runtime using session
    # -------------------------------
    runtime = AgentRuntime(
        identity_path=session.identity_path,
        signer=session.signer,
        ksctx=session.ksctx,
        workdir=str(exec_path.parent),
        force_python_driver=args.python_driver,
        legacy_python=args.legacy_python,
    )

    status, result = runtime.run(
        agent_path=str(exec_path),
        agent_args=agent_args,
    )

    while status == "await_input":
        print(result["prompt"])
        user_input = input("> ")
        status, result = runtime.resume(paused_state=result, user_input=user_input)

    print("Execution finished:", status, result)
    return 0






def print_chronicle_attestation(level, reason, details):
    """
    Pretty-print Chronicle attestation results in a CLI-friendly format.
    Levels:
        ok       → normal
        notice   → benign missing/pruned
        warning  → truncated
        alert    → tampered
        error    → impossible state (but still non-blocking)
    """

    prefix = {
        "ok":     "[Chronicle Attestation] OK:",
        "notice": "[Chronicle Attestation] NOTICE:",
        "warning": "[Chronicle Attestation] WARNING:",
        "alert":  "[Chronicle Attestation] ALERT:",
        "error":  "[Chronicle Attestation] ERROR:",
    }.get(level, "[Chronicle Attestation]")

    print(f"{prefix} {reason}")

    # Print details if present
    if details:
        for k, v in details.items():
            if isinstance(v, list):
                print(f"    {k}: {len(v)} items")
            else:
                print(f"    {k}: {v}")

    print()  # blank line for spacing
