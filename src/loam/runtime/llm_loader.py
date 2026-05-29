#runtime/llm_loader.py

import importlib
from typing import Protocol, Any, Dict


class LLMBackend(Protocol):
    vendor_name: str

    def think(self, input: str, model: str | None = None, tags: Dict[str, Any] | None = None) -> Dict[str, Any]:
        ...



def load_llm_backend(name: str, rt) -> LLMBackend:
    module_path = f"loam.backends.llm.{name}"

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ValueError(f"Unknown LLM provider: {name}") from e

    if not hasattr(module, "Backend"):
        raise ValueError(f"LLM provider {name} has no Backend class")

    backend_cls = module.Backend
    backend = backend_cls(rt)  # ← pass runtime, not store_id

    # ------------------------------------------------------------
    # Protocol enforcement
    # ------------------------------------------------------------

    # vendor_name
    if not isinstance(getattr(backend, "vendor_name", None), str):
        raise TypeError(f"Backend {name} missing valid vendor_name")

    # capability flags
    for flag in ["supports_streaming", "supports_embeddings", "supports_tools"]:
        if not hasattr(backend, flag):
            setattr(backend, flag, False)
        elif not isinstance(getattr(backend, flag), bool):
            raise TypeError(f"Backend {name} has non-boolean {flag}")

    # think() method
    think = getattr(backend, "think", None)
    if not callable(think):
        raise TypeError(f"Backend {name} missing think() method")

    # model normalization helper
    if not hasattr(backend, "normalize_model_name"):
        raise TypeError(f"Backend {name} missing normalize_model_name()")

    return backend
