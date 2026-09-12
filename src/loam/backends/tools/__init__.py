from . import fs, state, http, process, artifact, discord

REGISTRY = {
    "fs.read": fs.read,
    "fs.write": fs.write,
    "fs.list": fs.list_dir,
    "fs.delete": fs.delete,

    "state.read": state.read,
    "state.write": state.write,
    "state.write_begin": state.write_begin,
    "state.write_chunk": state.write_chunk,
    "state.write_commit": state.write_commit,
    "state.write_abort": state.write_abort,

    "http.request": http.request,
    
    "process.run": process.run,

    "artifact.emit": artifact.emit,

    "discord.send_message": discord.send_message,
    "discord.fetch_messages": discord.fetch_messages,
    "discord.fetch_reactions": discord.fetch_reactions,
}