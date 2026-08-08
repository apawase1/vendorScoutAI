"""Shared inbox for inbound WhatsApp messages — pluggable backend.

The webhook process (receives Meta's POST) and the agent process (polls for
replies in `wait_for_vendor_reply`) must see the same inbox. On a laptop
that's trivially true — same filesystem, same process even. On a real
deployment they're very likely *different containers* (the UI and the
webhook run as separate Cloud Run services so the webhook has its own public
URL), so a local JSON file would silently never be seen by the UI process.

Backend selection is automatic:
    REDIS_URL set      -> RedisInboxStore (shared across every instance)
    REDIS_URL unset     -> FileInboxStore (zero-setup local dev fallback)

Both implement the same three-method interface, so nothing above this layer
needs to know which one is active.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol


class InboxStore(Protocol):
    def read(self) -> list[dict[str, Any]]: ...
    def append(self, entry: dict[str, Any]) -> None: ...
    def clear(self) -> None: ...


class FileInboxStore:
    """Local JSON file. Fine for a single process/instance; not safe to
    share across multiple containers — use RedisInboxStore in production."""

    def __init__(self, path: str = "whatsapp_inbox.json") -> None:
        self._path = Path(path)

    def read(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text() or "[]")
        except json.JSONDecodeError:
            return []

    def append(self, entry: dict[str, Any]) -> None:
        messages = self.read()
        messages.append(entry)
        self._path.write_text(json.dumps(messages, indent=2))

    def clear(self) -> None:
        self._path.write_text("[]")


class RedisInboxStore:
    """Redis list — safe to share across any number of instances/services.
    Each message is one list element, so append is a single atomic RPUSH."""

    def __init__(self, url: str, key: str = "vendorscoutai:whatsapp_inbox") -> None:
        import redis  # imported lazily so redis is only required when used

        self._r = redis.from_url(url, decode_responses=True, socket_timeout=5)
        self._key = key

    def read(self) -> list[dict[str, Any]]:
        return [json.loads(raw) for raw in self._r.lrange(self._key, 0, -1)]

    def append(self, entry: dict[str, Any]) -> None:
        self._r.rpush(self._key, json.dumps(entry))
        # Keep the list bounded — this is a short-lived negotiation
        # transcript, not a long-term store.
        self._r.ltrim(self._key, -500, -1)

    def clear(self) -> None:
        self._r.delete(self._key)


_store: InboxStore | None = None


def get_store() -> InboxStore:
    global _store
    if _store is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            _store = RedisInboxStore(redis_url)
        else:
            _store = FileInboxStore(os.getenv("WHATSAPP_INBOX", "whatsapp_inbox.json"))
    return _store
