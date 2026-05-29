#cli/exec.py
import sys
from pathlib import Path
from loam.identity.metadata import resolve_store_identifier
from loam.identity.paths import store_path
from loam.runtime.exec_runtime import ExecRuntime

def cmd_exec(args):
    # Resolve human name / identity fingerprint / UUID → canonical store_id
    store_id = resolve_store_identifier(args.store_id)

    # Split program args from Loam args using --
    if "--" in args.args:
        sep = args.args.index("--")
        program_args = args.args[sep+1:]
    else:
        program_args = args.args

    # Construct runtime for this execution
    runtime = ExecRuntime(
        identity_path=store_path(store_id),
        workdir=str(Path(args.program).resolve().parent),
        passphrase=args.passphrase,
    )

    # Execute the program inside the store envelope
    code, out, err = runtime.run_program(args.program, program_args)

    print(out)
    if err:
        print(err, file=sys.stderr)

    return code