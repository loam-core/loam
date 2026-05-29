from pathlib import Path
from loam.identity.paths import stores_root


def list_all_stores() -> list[str]:
    """
    Return a list of all store IDs in ~/.loam/stores.
    """
    root = stores_root()
    if not root.exists():
        return []
    return [p.name for p in root.iterdir() if p.is_dir()]

