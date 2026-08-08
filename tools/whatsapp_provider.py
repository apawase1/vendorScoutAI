"""WhatsApp transport layer — Meta Cloud API.

Meta's Cloud API has no polling endpoint for inbound messages: replies arrive
by webhook only. `webhook_server.py` receives them and appends to the shared
inbox (see tools/inbox_store.py — Redis in production, a local file for
zero-setup local dev), which `read_inbox` polls — keeping the agent's
synchronous send -> wait_for_reply loop intact regardless of backend.

Free-text note: Meta only allows free-form (non-template) messages inside a
24h window opened by an inbound message from the recipient. For the demo the
vendor sends one message first, which opens that window.

The outbound call to Meta's Graph API is wrapped in a circuit breaker
(tools/circuit_breaker.py) — it's a third-party dependency we don't control,
and after Meta trips repeatedly there's no point hammering it (or making the
user wait through the full 30s timeout) on every subsequent message.
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

from tools.circuit_breaker import CircuitBreaker, CircuitOpenError
from tools.inbox_store import get_store

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v25.0")

_meta_breaker = CircuitBreaker(name="meta_whatsapp", fail_max=3, reset_timeout_s=30)


def _digits(number: str) -> str:
    return "".join(c for c in number if c.isdigit())


# ------------------------------------------------------------- inbox

def read_inbox() -> list[dict[str, Any]]:
    return get_store().read()


def append_inbox(entry: dict[str, Any]) -> None:
    get_store().append(entry)


def clear_inbox() -> None:
    get_store().clear()


# ---------------------------------------------------------------- sending

def _post_to_meta(body: str) -> dict[str, Any]:
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
        timeout=10,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Meta API {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    return {"status": "sent", "id": data.get("messages", [{}])[0].get("id", "")}


def send_message(body: str) -> dict[str, Any]:
    try:
        return _meta_breaker.call(_post_to_meta, body)
    except CircuitOpenError:
        return {
            "status": "failed",
            "error": "meta_whatsapp circuit open — too many recent failures, "
                     "skipping call to avoid piling up latency",
        }
    except Exception as exc:  # noqa: BLE001 — surface as a normal tool result
        return {"status": "failed", "error": str(exc)[:400]}


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
