#backends/tools/fs.py

import json
from loam.continuity.hash import compute_file_hash


def read(context, args):
    path = args["path"]

    # Resolve sandbox path
    p = context._sandbox_path(path)

    # Read file
    content = p.read_text(encoding="utf-8")

    # Return result + metadata for Chronicle
    return {
        "result": {"content": content},
        "meta": {
            "virtual_path": path,
            "bytes": len(content.encode("utf-8")),
            "full_path": str(p),
        }
    }


def write(context, args):
    path = args["path"]
    content = args.get("content", "")

    # Normalize dict → JSON string
    if isinstance(content, dict):
        content = json.dumps(content)

    # Ensure content is a string
    if not isinstance(content, str):
        content = str(content)

    content_bytes = content.encode("utf-8")

    # Resolve sandbox path
    p = context._sandbox_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    p.write_text(content, encoding="utf-8")

    # Return result + metadata for Chronicle
    return {
        "result": {"ok": True},
        "meta": {
            "virtual_path": path,
            "bytes": len(content_bytes),
            "full_path": str(p),
        }
    }

def list_dir(context, args):
    path = args["path"]

    p = context._sandbox_path(path)
    entries = []

    for child in p.iterdir():
        entries.append({
            "name": child.name,
            "is_dir": child.is_dir(),
            "bytes": child.stat().st_size if child.is_file() else None,
        })

    return {
        "result": {"entries": entries},
        "meta": {
            "virtual_path": path,
            "entries": len(entries),
            # no PII, no payloads — entries list stays in result, not meta
        }
    }


def delete(context, args):
    path = args["path"]

    p = context._sandbox_path(path)

    # Hash before deletion (safe — file contents are not logged)
    try:
        file_hash_before = compute_file_hash(p)
    except Exception:
        file_hash_before = None

    size = p.stat().st_size if p.exists() and p.is_file() else 0

    # Perform deletion
    if p.exists():
        p.unlink()

    return {
        "result": {"ok": True},
        "meta": {
            "virtual_path": path,
            "bytes_deleted": size,
            "full_path": str(p),
            "file_hash_before": file_hash_before,
        }
    }
