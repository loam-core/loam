#!/usr/bin/env python3


from loam.runtime.ari import Agent
from loam.sdk.ari_helpers import llm, finish, read, write, http, secret



class MyAgent(Agent):
    def main(self):
        greeting = llm(self, "Say hello", backend="ollama", model="llama3.1:8b")

        try:
            mac = secret(self).hmac("openai_api_key", b"hello world")

        except Exception as e:
            finish(self, {"error": str(e)})
            return


        write(self, "scratch://hello.txt", greeting)
        stored = read(self, "scratch://hello.txt")

        resp = http(self, "GET", "https://example.com")

        finish(self, {
            "greeting": greeting,
            "stored": stored,
            "http": resp,
        })



if __name__ == "__main__":
    MyAgent().main()
