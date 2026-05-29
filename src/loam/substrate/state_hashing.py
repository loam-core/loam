#substrate/state_hashing

from pathlib import Path
import hashlib

class StateHashingError(Exception):
    pass

def compute_state_hash(root: Path) -> str:
    """
    Compute State Hashing v1 over the given state root directory.
    """
    if not root.exists():
        raise StateHashingError(f"State root does not exist: {root}")

    if not root.is_dir():
        raise StateHashingError(f"State root is not a directory: {root}")

    # 1. Collect all files under root
    files = []
    for path in root.rglob("*"):
        if path.is_file():
            # store relative path (canonical)
            rel = path.relative_to(root)
            files.append(rel)

    # 2. Sort lexicographically
    files.sort(key=lambda p: str(p))

    # 3. Build canonical bytes
    chunks = []
    for rel in files:
        abs_path = root / rel

        # File path (UTF‑8) + newline
        chunks.append(str(rel).encode("utf-8"))
        chunks.append(b"\n")

        # file contents (raw bytes) + newline
        try:
            data = abs_path.read_bytes()
        except Exception as e:
            raise StateHashingError(f"Failed to read state file {abs_path}: {e}")

        chunks.append(data)
        chunks.append(b"\n")

    # 4. Remove final newline if present
    if chunks:
        last = chunks[-1]
        if last == b"\n":
            chunks = chunks[:-1]

    canonical_bytes = b"".join(chunks)

    # 5. Hash
    h = hashlib.sha256()
    h.update(canonical_bytes)
    return h.hexdigest()
