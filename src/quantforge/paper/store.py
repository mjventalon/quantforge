"""Persistent storage for paper-trading accounts (JSON files, atomic writes).

Accounts live in ``$QUANTFORGE_DATA_DIR/paper`` (default ``~/.quantforge/paper``). Each
*wallet* is one file holding one or more accounts; its random id is the key a browser keeps
in a cookie, and the **account code** a user can type on another device to reopen it.

On cloud hosts, mount a persistent disk/volume and point ``QUANTFORGE_DATA_DIR`` at it,
otherwise files disappear when the container restarts.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from pathlib import Path

from .engine import Account

__all__ = ["data_dir", "new_wallet_id", "load_wallet", "save_wallet", "valid_wallet_id",
           "delete_wallet"]

_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def data_dir() -> Path:
    base = Path(os.environ.get("QUANTFORGE_DATA_DIR") or Path.home() / ".quantforge")
    d = base / "paper"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_wallet_id() -> str:
    return secrets.token_urlsafe(18)


def valid_wallet_id(wid: str) -> bool:
    return bool(wid) and bool(_ID.match(wid))


def _path(wid: str) -> Path:
    if not valid_wallet_id(wid):
        raise ValueError("invalid account code")
    return data_dir() / f"{wid}.json"


def load_wallet(wid: str) -> list[Account]:
    """Accounts of a wallet; an empty list if the code is unknown."""
    p = _path(wid)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [Account.from_dict(a) for a in data.get("accounts", [])]


def save_wallet(wid: str, accounts: list[Account]) -> None:
    p = _path(wid)
    payload = json.dumps({"version": 1, "accounts": [a.to_dict() for a in accounts]},
                         separators=(",", ":"))
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".tmp_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(payload)
    os.replace(tmp, p)


def delete_wallet(wid: str) -> None:
    p = _path(wid)
    if p.exists():
        p.unlink()
