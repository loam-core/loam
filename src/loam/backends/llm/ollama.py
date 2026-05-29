import requests
import json
from .base import LLMBackend


class Backend(LLMBackend):
    provider_name = "ollama"
    vendor_name = "ollama"

    supports_streaming = False
    supports_embeddings = False
    supports_tools = False

    def __init__(self, rt):
        super().__init__(rt)  # just store rt, even if you don't use it yet

    def think(self, input, model=None, tags=None):
        try:
            model = self.normalize_model_name(model or "llama3.1:8b")
            tags = tags or {}

            payload = {
                "model": model,
                "prompt": input,
                "stream": True,   # Ollama streams internally; substrate does not
                "num_predict": 50,
            }

            # Sampling params
            if "temperature" in tags:
                payload["temperature"] = tags["temperature"]
            if "top_p" in tags:
                payload["top_p"] = tags["top_p"]
            if "top_k" in tags:
                payload["top_k"] = tags["top_k"]

            r = requests.post(
                "http://192.168.1.123:11434/api/generate",
                json=payload,
                stream=True,
                timeout=10,
            )

            output = []

            for line in r.iter_lines():
                if not line:
                    continue

                try:
                    chunk = json.loads(line.decode("utf-8"))
                except Exception:
                    continue

                if "response" in chunk:
                    output.append(chunk["response"])

                if chunk.get("done"):
                    break

            return {
                "output": "".join(output),
                "usage": {
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                },
                "model": model,
                "vendor": self.vendor_name,
            }

        except Exception as e:
            return {
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                }
            }
