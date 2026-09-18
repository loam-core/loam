# sdk/context.py

from typing import Any, Dict, List, Optional

from .secret import Secrets


class Context:
    """
    Thin ergonomic wrapper around ARI agent methods.
    No magic. No lifecycle. No dispatch.

    This is the single ergonomic surface for SDK agents. It supersedes the
    old ari_helpers module-level functions and the bind() positional-tuple
    helper — both covered a different, overlapping subset of ARI methods.

    Every method below is a direct pass-through to the corresponding
    loam.runtime.ari.Agent method, so it raises the same exceptions that
    method does (see the "Error handling convention" section in
    docs/agent_dev_guide.md, §7.1, and loam.runtime.ari's module docstring —
    documented once, there, not repeated per-method here).
    """

    def __init__(self, agent):
        self.agent = agent
        self.secret = Secrets(agent)

    @property
    def capabilities(self) -> Optional[Dict[str, Any]]:
        """Summarized policy view sent at init: allowed tools/http domains/
        filesystem paths/llm models/subprocess commands. See
        PolicyEnforcer.capability_manifest() in runtime/id_runtime.py."""
        return self.agent.capabilities

    # LLM
    def llm(self, prompt, **kwargs) -> str:
        return self.agent.llm_think(prompt, **kwargs)

    # Human input
    def input(self, prompt) -> str:
        return self.agent.input(prompt)

    # Finish
    def finish(self, result, status="ok") -> None:
        return self.agent.finish(result, status=status)

    # FS
    def read(self, path) -> Optional[str]:
        return self.agent.fs_read(path)

    def write(self, path, content) -> bool:
        return self.agent.fs_write(path, content)

    def delete(self, path) -> bool:
        return self.agent.fs_delete(path)

    def listdir(self, path) -> List[Dict[str, Any]]:
        return self.agent.fs_list(path)

    def search(self, path, pattern="", recursive=False) -> List[Any]:
        return self.agent.fs_search(path, pattern, recursive)

    # HTTP
    def http(self, method, url, **kwargs) -> Dict[str, Any]:
        return self.agent.http_request(method, url, **kwargs)

    # Process
    def run(self, argv, **kwargs) -> Dict[str, Any]:
        return self.agent.process_run(argv, **kwargs)

    # Simulation
    def simulate(self, payload) -> Dict[str, Any]:
        return self.agent.simulate(payload)

    # Continuity
    def continuity_info(self) -> Dict[str, Any]:
        """Read-only: last seq/state_hash/kind, and whether this identity
        has any continuity history yet. See Agent.continuity_info()."""
        return self.agent.continuity_info()

    # State
    def state_read(self, path) -> Optional[str]:
        return self.agent.state_read(path)

    def state_write(self, path, data) -> bool:
        return self.agent.state_write(path, data)

    def state_write_detailed(self, path, data) -> Dict[str, Any]:
        return self.agent.state_write_detailed(path, data)

    # Artifacts
    def emit(self, path, description=None) -> Dict[str, str]:
        return self.agent.artifact_emit(path, description)
