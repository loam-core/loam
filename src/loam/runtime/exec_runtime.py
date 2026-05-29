#runtime/exec_runtime

import time
import hashlib
from pathlib import Path
import os

from loam.runtime.id_runtime import IdentityRuntime
from loam.substrate.simulation_envelope import hash_envelope
from loam.runtime.driver.native_driver import NativeDriver
from loam.runtime.driver.driver import LocalPythonDriver

class ExecRuntime(IdentityRuntime):
    """
    Identity-bearing program execution (no protocol loop).
    """

    def __init__(self, identity_path: Path, workdir=None, **kwargs):
        # IdentityRuntime now handles passphrase + KeySource
        super().__init__(identity_path, **kwargs)

        self.workdir = workdir or os.getcwd()

        driver_env = os.getenv("LOAM_DRIVER")

        if driver_env == "python":
            self.driver = LocalPythonDriver()
        else:
            default_lib = os.path.join(
                os.path.dirname(__file__),
                "driver",
                "libloam_driver.so",
            )
            lib_path = driver_env or default_lib
            self.driver = NativeDriver(lib_path=lib_path)

    def is_simulation(self):
        return False


    def run_program(self, program_path, program_args):
        # 1. Trust pipeline
        self.initialize_authority()

        # 2. Envelope
        self.envelope = self.create_execution_envelope(simulation_depth=0)
        self.run_id = self.envelope["run_id"]
        self.envelope_hash = hash_envelope(self.envelope)

        # 3. Chronicle: execution_start
        resolved_path = str(Path(program_path).resolve())

        args_hash = (
            hashlib.sha256(" ".join(program_args).encode()).hexdigest()
            if program_args else None
        )

        self.chronicle(
            "execution_start",
            {
                "exec_path": program_path,
                "exec_path_resolved": resolved_path,
                "exec_basename": os.path.basename(program_path),
                "exec_code_hash": hash_file(program_path),
                "exec_path_hash": hashlib.sha256(resolved_path.encode()).hexdigest(),
                "cwd": self.workdir,
                "args_count": len(program_args),
                "args_hash": args_hash,
                "driver": self.driver.__class__.__name__,
                "run_id": self.run_id,
                "envelope_hash": self.envelope_hash,
            },
        )

        start_time = time.time()

        try:
            # 4. Execute program (native synchronous exec)
            result = self.driver.exec_program(
                program_path,
                program_args,
                env=os.environ.copy(),
                cwd=self.workdir,
            )

            exit_code = result["exit_code"]
            stdout = result["stdout"]
            stderr = result["stderr"]

            # 5. Finalize continuity
            self.finalize_continuity()

            # 6. Chronicle: execution_finished
            duration_ms = int((time.time() - start_time) * 1000)

            stdout_hash = hashlib.sha256(stdout.encode()).hexdigest() if stdout else None
            stderr_hash = hashlib.sha256(stderr.encode()).hexdigest() if stderr else None

            self.chronicle(
                "execution_finished",
                {
                    "exec_path": program_path,
                    "exec_path_resolved": resolved_path,
                    "exec_basename": os.path.basename(program_path),
                    "exec_code_hash": hash_file(program_path),
                    "status": exit_code,
                    "status_hash": hashlib.sha256(str(exit_code).encode()).hexdigest(),
                    "stdout_hash": stdout_hash,
                    "stderr_hash": stderr_hash,
                    "duration_ms": duration_ms,
                    "run_id": self.run_id,
                    "envelope_hash": self.envelope_hash,
                },
            )

            return exit_code, stdout, stderr

        except Exception as e:
            self.chronicle(
                "execution_failed",
                {
                    "exec_path": program_path,
                    "exec_path_resolved": resolved_path,
                    "exec_basename": os.path.basename(program_path),
                    "exec_code_hash": hash_file(program_path),
                    "error_hash": hashlib.sha256(str(e).encode()).hexdigest(),
                    "run_id": self.run_id,
                    "envelope_hash": self.envelope_hash,
                },
            )
            raise



def hash_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None