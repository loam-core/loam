from . import fs, state, http, process, artifact

REGISTRY = {
    "fs.read": fs.read,
    "fs.write": fs.write,
    "fs.list": fs.list_dir,
    "fs.delete": fs.delete,

    "state.read": state.read,
    "state.write": state.write,

    "http.request": http.request,
    
    "process.run": process.run,

    "artifact.emit": artifact.emit,
}