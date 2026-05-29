mod handle;
mod tool;

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int};
use handle::Handle;
use tool::ToolResult;

// Convert C string → Rust String
fn cstr_to_string(ptr: *const c_char) -> String {
    unsafe { CStr::from_ptr(ptr).to_string_lossy().into_owned() }
}

// Convert Rust String → C string
fn string_to_cchar(s: String) -> *mut c_char {
    CString::new(s).unwrap().into_raw()
}

#[no_mangle]
pub extern "C" fn driver_start_agent(
    exec_path: *const c_char,
    args_json: *const c_char,
    env_json: *const c_char,
    cwd: *const c_char,
) -> *mut Handle {
    let exec = cstr_to_string(exec_path);
    let args = cstr_to_string(args_json);
    let env = cstr_to_string(env_json);
    let cwd = cstr_to_string(cwd);

    Handle::start(exec, args, env, cwd)
}

#[no_mangle]
pub extern "C" fn driver_send_json(
    handle: *mut Handle,
    msg: *const c_char,
) {
    let message = cstr_to_string(msg);
    unsafe { (*handle).send_json(message) };
}

#[no_mangle]
pub extern "C" fn driver_read_json(
    handle: *mut Handle,
) -> *mut c_char {
    let result = unsafe { (*handle).read_json() };
    match result {
        Some(line) => string_to_cchar(line),
        None => std::ptr::null_mut(),
    }
}

#[no_mangle]
pub extern "C" fn driver_read_stderr(
    handle: *mut Handle,
) -> *mut c_char {
    let result = unsafe { (*handle).read_stderr() };
    match result {
        Some(line) => string_to_cchar(line),
        None => std::ptr::null_mut(),
    }
}

#[no_mangle]
pub extern "C" fn driver_terminate(handle: *mut Handle) {
    unsafe { (*handle).terminate() };
}

#[no_mangle]
pub extern "C" fn driver_wait(
    handle: *mut Handle,
    timeout_ms: u64,
) -> c_int {
    unsafe { (*handle).wait(timeout_ms) }
}

#[no_mangle]
pub extern "C" fn driver_run_tool(
    tool_path: *const c_char,
    args_json: *const c_char,
    env_json: *const c_char,
    cwd: *const c_char,
) -> *mut c_char {
    let path = cstr_to_string(tool_path);
    let args = cstr_to_string(args_json);
    let env = cstr_to_string(env_json);
    let cwd = cstr_to_string(cwd);

    let result = ToolResult::run(path, args, env, cwd);
    string_to_cchar(serde_json::to_string(&result).unwrap())
}

#[no_mangle]
pub extern "C" fn driver_exec_program(
    program_path: *const c_char,
    args_json: *const c_char,
    env_json: *const c_char,
    cwd: *const c_char,
) -> *mut c_char {
    let path = cstr_to_string(program_path);
    let args = cstr_to_string(args_json);
    let env = cstr_to_string(env_json);
    let cwd = cstr_to_string(cwd);

    let result = ToolResult::run(path, args, env, cwd);
    string_to_cchar(serde_json::to_string(&result).unwrap())
}
