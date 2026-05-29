#loam/runtime/driver/driver.py

import json
import subprocess

class Driver:
        """
        Driver interface: defines how the substrate launches and communicates with an agent.

        A driver is responsible ONLY for:
        - starting the agent process (start_agent)
        - sending JSON messages to the agent (send_json)
        - reading JSON messages from the agent (read_json)
        - terminating or waiting on the process (terminate, wait)
        - running external tools as subprocesses (run_tool)

        Driver selection:
        - ExecRuntime chooses the driver at runtime.
        - If the environment variable LOAM_DRIVER is set, the NativeDriver is used
            and the agent must be a real executable that speaks the Loam protocol.
        - Otherwise, LocalPythonDriver is used, which hosts Python module-based
            agents inside the Python interpreter.

        The driver does NOT interpret protocol messages. It only moves bytes.
        All protocol semantics (init, call_tool, finish, simulate) are handled
        by the ExecRuntime above this layer.
        """

        def start_agent(self, exec_path, args, env, cwd):
            raise NotImplementedError

        def send_json(self, handle, message):
            raise NotImplementedError

        def read_json(self, handle, timeout=None):
            raise NotImplementedError

        def terminate(self, handle):
            raise NotImplementedError

        def wait(self, handle, timeout=None):
            raise NotImplementedError

        def run_tool(self, tool_path, args, env, cwd, limits=None):
            raise NotImplementedError
        
        def read_stderr(self, handle):
            raise NotImplementedError


class LocalPythonDriver(Driver):
    
    def start_agent(self, exec_path, args, env, cwd):
        return subprocess.Popen(
            [exec_path] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
            cwd=cwd,
        )

    def send_json(self, handle, message):
        handle.stdin.write(json.dumps(message) + "\n")
        handle.stdin.flush()

    def read_json(self, handle, timeout=None):
        line = handle.stdout.readline()
        if not line:
            return None
        return json.loads(line)

    def terminate(self, handle):
        handle.terminate()

    def wait(self, handle, timeout=None):
        return handle.wait(timeout=timeout)

    def run_tool(self, tool_path, args, env, cwd, limits=None):
        return subprocess.run(
            [tool_path] + args,
            capture_output=True,
            text=False,
            env=env,
            cwd=cwd,
            )
    
    def read_stderr(self, handle):
        return handle.stderr.readline()
