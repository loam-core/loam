# loam/backends/llm/base.py

from typing import Dict, Any


from typing import Dict, Any

class LLMBackend:
    """
    Canonical substrate-level protocol for LLM backends (v0.1).
    All LLM backends MUST implement this interface.
    """

    provider_name: str = "unknown"
    vendor_name: str = "unknown"

    supports_streaming: bool = False
    supports_embeddings: bool = False
    supports_tools: bool = False

    def __init__(self, rt):
        # Runtime object (identity, secrets, policy, provenance, etc.)
        self.rt = rt

    def think(self, input: str, model: str | None, tags: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def normalize_model_name(name: str | None) -> str | None:
        if name is None:
            return None
        return name.strip().lower()


    # ------------------------------------------------------------
    # Required method
    # ------------------------------------------------------------
    def think(self, input: str, model: str | None, tags: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single LLM inference.

        MUST return:
        {
            "output": <str>,
            "usage": {
                "prompt_tokens": <int> | None,
                "completion_tokens": <int> | None,
                "total_tokens": <int> | None,
            },
            "model": <canonical_model_name>,
            "vendor": <vendor_name>,
        }

        MUST NOT raise exceptions.
        MUST return canonical error envelope on failure:
        {
            "error": {
                "type": <str>,
                "message": <str>
            }
        }
        """
        raise NotImplementedError

    # ------------------------------------------------------------
    # Optional helper: canonical model name
    # ------------------------------------------------------------
    @staticmethod
    def normalize_model_name(name: str | None) -> str | None:
        if name is None:
            return None
        return name.strip().lower()
