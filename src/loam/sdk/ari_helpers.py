# ari_helpers.py

# A tiny ergonomic layer over ARI's raw methods.
# No decorators. No magic. No lifecycle interference.
# Just syntax cleanup.

def llm(agent, prompt, **kwargs):
    return agent.llm_think(prompt, **kwargs)

def finish(agent, result, status="ok"):
    agent.finish(result, status=status)

# -------------------------
# Filesystem helpers
# -------------------------

def read(agent, path):
    return agent.fs_read(path)

def write(agent, path, content):
    return agent.fs_write(path, content)

def delete(agent, path):
    return agent.fs_delete(path)

def listdir(agent, path):
    return agent.fs_list(path)

def search(agent, path, pattern="", recursive=False):
    return agent.fs_search(path, pattern, recursive)

# -------------------------
# State helpers
# -------------------------

def state_read(agent, path):
    return agent.state_read(path)

def state_write(agent, path, data):
    return agent.state_write(path, data)

# -------------------------
# HTTP helpers
# -------------------------

def http(agent, method, url, headers=None, body=None):
    return agent.http_request(method, url, headers=headers, body=body)

# -------------------------
# Process helpers
# -------------------------

def run(agent, argv, stdin=None, timeout=None):
    return agent.process_run(argv, stdin=stdin, timeout=timeout)

# -------------------------
# Simulation helpers
# -------------------------

def simulate(agent, payload):
    return agent.simulate(payload)

# -------------------------
# Artifact helpers
# -------------------------

def emit(agent, path, description=None):
    return agent.artifact_emit(path, description)

from loam.sdk.secret import Secrets

# -------------------------
# Secrets helpers
# -------------------------

from loam.sdk.secret import Secrets

def secret(agent):
    return Secrets(agent)

# -------------------------
# Binding helper
# -------------------------
def bind(agent):
    """
    Bind all SDK helper functions to a specific Agent instance.
    Returns a namespace of callables with `agent` pre‑applied.
    """
    return (
        lambda *args, **kwargs: llm(agent, *args, **kwargs),
        lambda *args, **kwargs: http(agent, *args, **kwargs),
        lambda *args, **kwargs: read(agent, *args, **kwargs),
        lambda *args, **kwargs: write(agent, *args, **kwargs),
        lambda *args, **kwargs: delete(agent, *args, **kwargs),
        lambda *args, **kwargs: listdir(agent, *args, **kwargs),
        lambda *args, **kwargs: search(agent, *args, **kwargs),
        lambda *args, **kwargs: state_read(agent, *args, **kwargs),
        lambda *args, **kwargs: state_write(agent, *args, **kwargs),
        lambda *args, **kwargs: run(agent, *args, **kwargs),
        lambda *args, **kwargs: simulate(agent, *args, **kwargs),
        lambda *args, **kwargs: emit(agent, *args, **kwargs),
        lambda *args, **kwargs: secret(agent, *args, **kwargs),
        lambda *args, **kwargs: finish(agent, *args, **kwargs),
        lambda prompt: agent.input(prompt),
    )

