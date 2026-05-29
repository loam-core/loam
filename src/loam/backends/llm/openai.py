# /loam/backends/llm/openai.py

import sys
import openai
from .base import LLMBackend

class Backend(LLMBackend):
    provider_name = "openai"
    vendor_name = "openai"

    supports_streaming = False
    supports_embeddings = False
    supports_tools = False

    def __init__(self, rt):
        print("[OPENAI BACKEND INIT]", file=sys.stderr)
        super().__init__(rt)

        # Load plaintext API key from identity store
        self.api_key = rt.get_secret("openai_api_key")

        # Configure client
        openai.api_key = self.api_key

    def think(self, input, model=None, tags=None):
        try:
            model = self.normalize_model_name(model or "gpt-4.1-mini")
            tags = tags or {}

            # Real OpenAI request schema (2024+)
            resp = openai.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": input}],
                **tags,
            )

            msg = resp.choices[0].message["content"]

            return {
                "output": msg,
                "usage": {
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                    "total_tokens": resp.usage.total_tokens,
                },
                "model": model,
                "vendor": self.vendor_name,
            }

        except Exception as e:
            # Canonical error envelope
            return {
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                }
            }
