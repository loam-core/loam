# sdk/agent.py

from loam.runtime.ari import Agent as ARIAgent
from .context import Context


class Agent(ARIAgent):
    """
    Minimal SDK Agent:
    - wraps ARI Agent
    - provides ctx for ergonomic access
    - does NOT override dispatch, resume, or lifecycle
    - does NOT interfere with protocol loop
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctx = Context(self)

    def main(self):
        """
        ARI calls this automatically.
        SDK agents override this.
        """
        raise NotImplementedError("Implement main()")
