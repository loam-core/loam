#cli/exec.py
from hashlib import sha256
import sys
from pathlib import Path

from loam.identity.keysources import KeySourceContext
from loam.identity.metadata import resolve_store_identifier
from loam.identity.unlock import UnlockIdentity
from loam.runtime.exec_runtime import ExecRuntime

def cmd_exec(args):
    store_id = resolve_store_identifier(args.store_id)

    # Split program args from Loam args using --
    if "--" in args.args:
        sep = args.args.index("--")
        program_args = args.args[sep+1:]
    else:
        program_args = args.args

    program_path = Path(args.program).expanduser().resolve()

    # -------------------------------
    # NEW: UnlockIdentity
    # -------------------------------
    ksctx = KeySourceContext(passphrase=args.passphrase)
    mechanism_hash = sha256(args.passphrase.encode()).hexdigest()
    session = UnlockIdentity(store_id, mechanism_hash, ksctx)

    # -------------------------------
    # NEW: Construct ExecRuntime using session
    # -------------------------------
    runtime = ExecRuntime(
        identity_path=session.identity_path,
        signer=session.signer,
        ksctx=session.ksctx,
        workdir=str(program_path.parent),
    )

    code, out, err = runtime.run_program(str(program_path), program_args)

    print(out)
    if err:
        print(err, file=sys.stderr)

    return code

