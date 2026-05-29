# substrate/config.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

@dataclass
class FilesystemConfig:
    allowed_paths: List[str] = field(default_factory=list)
    mounts: Dict[str, str] = field(default_factory=dict)

@dataclass
class Config:
    store_path: Path
    filesystem: FilesystemConfig = field(default_factory=FilesystemConfig)
