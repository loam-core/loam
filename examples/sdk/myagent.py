#!/usr/bin/env python3

from loam.sdk import Agent


class MyAgent(Agent):
    def main(self):
        greeting = self.ctx.llm("Say hello", backend="ollama", model="llama3.1:8b")

        try:
            mac = self.ctx.secret.hmac("openai_api_key", b"hello world")
        except Exception as e:
            self.ctx.finish({"error": str(e)})
            return

        self.ctx.write("scratch://hello.txt", greeting)
        stored = self.ctx.read("scratch://hello.txt")

        resp = self.ctx.http("GET", "https://example.com")

        self.ctx.finish({
            "greeting": greeting,
            "stored": stored,
            "http": resp,
        })


if __name__ == "__main__":
    MyAgent().main()
