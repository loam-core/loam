#cli/session.py

import json
import os
from pathlib import Path
from typing import Optional

SESSION_FILE = Path(os.path.expanduser("~/.loam/session.json"))


def _load_session() -> dict:
    if not SESSION_FILE.exists():
        return {}
    try:
        return json.loads(SESSION_FILE.read_text())
    except Exception:
        return {}


def _save_session(data: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data))


def get_cached_passphrase(store_id: str) -> Optional[str]:
    data = _load_session()
    entry = data.get(store_id)
    if not entry:
        return None
    return entry.get("passphrase")


def set_cached_passphrase(store_id: str, passphrase: str) -> None:
    data = _load_session()
    data[store_id] = {"passphrase": passphrase}
    _save_session(data)


def clear_cached_passphrase(store_id: str) -> None:
    data = _load_session()
    if store_id in data:
        del data[store_id]
        _save_session(data)


def clear_all_cached_passphrases() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()

