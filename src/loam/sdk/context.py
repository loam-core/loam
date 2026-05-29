# sdk/context.py

class Context:
    """
    Thin ergonomic wrapper around ARI agent methods.
    No magic. No lifecycle. No dispatch.
    """

    def __init__(self, agent):
        self.agent = agent

    # LLM
    def llm(self, prompt, **kwargs):
        return self.agent.llm_think(prompt, **kwargs)

    # Finish
    def finish(self, result, status="ok"):
        return self.agent.finish(result, status=status)

    # FS
    def read(self, path):
        return self.agent.fs_read(path)

    def write(self, path, content):
        return self.agent.fs_write(path, content)

    # HTTP
    def http(self, method, url, **kwargs):
        return self.agent.http_request(method, url, **kwargs)

    # Process
    def run(self, argv, **kwargs):
        return self.agent.process_run(argv, **kwargs)

    # Simulation
    def simulate(self, payload):
        return self.agent.simulate(payload)

    # State
    def state_read(self, path):
        return self.agent.state_read(path)

    def state_write(self, path, data):
        return self.agent.state_write(path, data)
