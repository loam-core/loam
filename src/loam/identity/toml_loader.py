#identity/toml_loader

from dataclasses import dataclass
from pathlib import Path
import tomllib

@dataclass
class StateConfig:
    path: Path | None
    hashing_enabled: bool

def load_identity_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_state_config(toml_data: dict) -> StateConfig:
    state = toml_data.get("state", {}) or {}

    raw_path = state.get("path")
    hashing_enabled = bool(state.get("hashing_enabled", False))

    # If hashing is enabled, path must be present and absolute
    if hashing_enabled:
        if not raw_path:
            raise ValueError("State hashing is enabled but no 'state.path' is configured in identity.toml")

        p = Path(raw_path)
        if not p.is_absolute():
            raise ValueError(f"State path must be absolute when hashing is enabled, got: {raw_path}")

        path = p
    else:
        # Hashing disabled → path may be None or anything; we don't care
        path = Path(raw_path) if raw_path else None

    return StateConfig(
        path=path,
        hashing_enabled=hashing_enabled,
    )

@dataclass
class ArtifactsConfig:
    path: Path

def load_artifacts_config(toml_data: dict) -> ArtifactsConfig:
    artifacts = toml_data.get("artifacts", {}) or {}
    raw_path = artifacts.get("path")

    if not raw_path:
        raise ValueError("identity.toml missing [artifacts].path")

    p = Path(raw_path)
    if not p.is_absolute():
        raise ValueError(f"Artifacts path must be absolute, got: {raw_path}")

    return ArtifactsConfig(path=p)
