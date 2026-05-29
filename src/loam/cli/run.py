# loam/cli/run.py

from pathlib import Path

from loam.identity.metadata import resolve_store_identifier
from loam.identity.paths import store_path

from loam.runtime.agent_runtime import AgentRuntime
from loam.substrate.attest_chronicle import attest_chronicle


def cmd_run(args):
    # Split Loam args from agent args using --
    if "--" in args.args:
        sep = args.args.index("--")
        agent_args = args.args[sep+1:]
    else:
        agent_args = []

    # Resolve human name / identity fingerprint / UUID → canonical store_id
    store_id = resolve_store_identifier(args.store_id)

    # 1. Chronicle attestation (non‑blocking)
    level, reason, details = attest_chronicle(store_id)
    if level != "ok":
        print_chronicle_attestation(level, reason, details)

    # Resolve the executable path the operator provided
    exec_path = Path(args.exec_path).resolve()

    # Construct runtime for this execution
    runtime = AgentRuntime(
        identity_path=store_path(store_id),
        workdir=str(exec_path.parent),
        force_python_driver=args.python_driver,
        legacy_python=args.legacy_python,
        passphrase=args.passphrase,
    )

    # Execute the command inside the store envelope
    status, result = runtime.run(
        agent_path=args.exec_path,
        agent_args=agent_args,
    )

    # Loop until the agent finishes
    while status == "await_input":
        print(result["prompt"])
        user_input = input("> ")

        status, result = runtime.resume(
            paused_state=result,
            user_input=user_input,
        )

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
