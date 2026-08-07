"""WhatsApp transport layer — Meta Cloud API.

Meta's Cloud API has no polling endpoint for inbound messages: replies arrive
by webhook only. `webhook_server.py` receives them and appends to a local
inbox file, which `read_inbox` polls — keeping the agent's synchronous
send -> wait_for_reply loop intact.

Free-text note: Meta only allows free-form (non-template) messages inside a
24h window opened by an inbound message from the recipient. For the demo the
vendor sends one message first, which opens that window.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

INBOX_PATH = Path(os.getenv("WHATSAPP_INBOX", "whatsapp_inbox.json"))
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v25.0")


def _digits(number: str) -> str:
    return "".join(c for c in number if c.isdigit())


# ------------------------------------------------------------- inbox file

def read_inbox() -> list[dict[str, Any]]:
    if not INBOX_PATH.exists():
        return []
    try:
        return json.loads(INBOX_PATH.read_text() or "[]")
    except json.JSONDecodeError:
        return []


def append_inbox(entry: dict[str, Any]) -> None:
    messages = read_inbox()
    messages.append(entry)
    INBOX_PATH.write_text(json.dumps(messages, indent=2))


def clear_inbox() -> None:
    INBOX_PATH.write_text("[]")


# ---------------------------------------------------------------- sending

def send_message(body: str) -> dict[str, Any]:
    import requests

    token = os.environ["META_ACCESS_TOKEN"]
    phone_id = os.environ["META_PHONE_NUMBER_ID"]
    to = _digits(os.environ["VENDOR_WHATSAPP_TO"])

    resp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        return {"status": "failed", "error": resp.text[:400]}
    data = resp.json()
    return {"status": "sent", "id": data.get("messages", [{}])[0].get("id", "")}


# -------------------------------------------------------------- receiving

def wait_for_reply(since_ts: float, timeout_s: int) -> Optional[dict[str, Any]]:
    """Poll for the next inbound message newer than `since_ts`."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for msg in read_inbox():
            if msg.get("ts", 0) > since_ts:
                return msg
        time.sleep(2)
    return None
