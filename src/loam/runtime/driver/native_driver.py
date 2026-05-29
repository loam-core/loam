#runtime/driver/native_driver.py

import os
import json
import ctypes
from ctypes import c_char_p, c_void_p, c_int, c_ulonglong
import sys
from .driver import Driver


class NativeDriver(Driver):
    def __init__(self, lib_path=None):
        if lib_path is None:
            lib_path = os.path.join(os.path.dirname(__file__), "libloam_driver.so")

        self.lib = ctypes.CDLL(lib_path)
        # exec_program(path, args_json, env_json, cwd) -> c_char_p
        self.lib.driver_exec_program.argtypes = [c_char_p, c_char_p, c_char_p, c_char_p]
        self.lib.driver_exec_program.restype = c_char_p
 

        # --- function signatures ---

        # start_agent(exec_path, args_json, env_json, cwd) -> *mut Handle
        self.lib.driver_start_agent.argtypes = [c_char_p, c_char_p, c_char_p, c_char_p]
        self.lib.driver_start_agent.restype = c_void_p

        # send_json(handle, msg_json)
        self.lib.driver_send_json.argtypes = [c_void_p, c_char_p]
        self.lib.driver_send_json.restype = None

        # read_json(handle) -> c_char_p (or NULL)
        self.lib.driver_read_json.argtypes = [c_void_p]
        self.lib.driver_read_json.restype = c_char_p

        # terminate(handle)
        self.lib.driver_terminate.argtypes = [c_void_p]
        self.lib.driver_terminate.restype = None

        # wait(handle, timeout_ms) -> int
        self.lib.driver_wait.argtypes = [c_void_p, c_ulonglong]
        self.lib.driver_wait.restype = c_int

        # run_tool(path, args_json, env_json, cwd) -> c_char_p
        self.lib.driver_run_tool.argtypes = [c_char_p, c_char_p, c_char_p, c_char_p]
        self.lib.driver_run_tool.restype = c_char_p

        # read_stderr(handle) -> c_char_p (or NULL)
        self.lib.driver_read_stderr.argtypes = [c_void_p]
        self.lib.driver_read_stderr.restype = c_char_p


    # --- Driver interface methods ---

    def start_agent(self, exec_path, args, env, cwd):
        args_json = json.dumps(args).encode("utf-8")
        env_json = json.dumps(env).encode("utf-8")

        handle = self.lib.driver_start_agent(
            exec_path.encode("utf-8"),
            args_json,
            env_json,
            cwd.encode("utf-8"),
        )
        return handle

    def send_json(self, handle, msg):
        msg_json = json.dumps(msg).encode("utf-8")
        self.lib.driver_send_json(handle, msg_json)

    def read_json(self, handle):
        raw = self.lib.driver_read_json(handle)
        if not raw:
            return None
        line = raw.decode("utf-8")
        return json.loads(line)

    def terminate(self, handle):
        self.lib.driver_terminate(handle)

    def wait(self, handle, timeout=None):
        timeout_ms = 0 if timeout is None else int(timeout * 1000)
        return self.lib.driver_wait(handle, timeout_ms)

    def run_tool(self, tool_path, args, env, cwd):
        args_json = json.dumps(args).encode("utf-8")
        env_json = json.dumps(env).encode("utf-8")

        raw = self.lib.driver_run_tool(
            tool_path.encode("utf-8"),
            args_json,
            env_json,
            cwd.encode("utf-8"),
        )
        return json.loads(raw.decode("utf-8"))

    # run a program (no protocol, no streaming)
    def exec_program(self, program_path, args, env, cwd):
        args_json = json.dumps(args).encode("utf-8")
        env_json = json.dumps(env).encode("utf-8")

        raw = self.lib.driver_exec_program(
            program_path.encode("utf-8"),
            args_json,
            env_json,
            cwd.encode("utf-8"),
        )
        return json.loads(raw.decode("utf-8"))

    def read_stderr(self, handle):
        raw = self.lib.driver_read_stderr(handle)
        return raw.decode("utf-8") if raw else ""

