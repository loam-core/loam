#backends/tools/process.py
import shutil
import json

def run(context, args):
    cmd = args.get("argv") or args.get("cmd")

    # Validate cmd is a list of strings
    if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
        return {
            "result": {"error": "InvalidCommand"},
            "meta": {"error": "InvalidCommand"}
        }

    # Resolve the executable path
    exe = shutil.which(cmd[0])
    if exe is None:
        return {
            "result": {"error": f"ExecutableNotFound: {cmd[0]}"},
            "meta": {"error": "ExecutableNotFound"}
        }

    # Hash the executable for forensic auditability
    exe_hash = context.hash_tool_file(exe)

    try:
        # Run the subprocess via runtime
        stdin_data = args.get("stdin")
        if isinstance(stdin_data, str):
            stdin_data = stdin_data.encode("utf-8")

        result = context._execute_subprocess(cmd, stdin_data=stdin_data)


        stdout = (result.stdout or b"").decode("utf-8", errors="ignore")
        stderr = (result.stderr or b"").decode("utf-8", errors="ignore")

        return {
            "result": {
                "returncode": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
            },
            "meta": {
                "cmd": cmd,
                "executable": exe,
                "executable_hash": exe_hash,
                "returncode": result.returncode,
                "stdout_bytes": len(result.stdout or b""),
                "stderr_bytes": len(result.stderr or b""),
            }
        }

    except Exception as e:
        return {
            "result": {"error": str(e)},
            "meta": {
                "cmd": cmd,
                "error": str(e),
                "error_type": type(e).__name__,
            }
        }
 