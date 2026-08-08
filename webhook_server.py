"""Meta WhatsApp webhook receiver.

Meta delivers inbound messages by webhook only (no polling endpoint), so this
tiny server catches them and appends to the shared inbox (tools/inbox_store.py
— Redis in production) that tools/whatsapp_provider.py polls.

Local dev:
    python webhook_server.py          # dev server on :8000
    ngrok http 8000                   # public HTTPS URL for Meta

Production: run under gunicorn (see gunicorn.conf.py / Dockerfile), not the
Flask dev server used by the __main__ block below.

Then in the Meta app: WhatsApp -> Configuration -> Edit webhook
    Callback URL:  https://<your-domain>/webhook
    Verify token:  same value as META_VERIFY_TOKEN
and subscribe to the `messages` field.

Security: every POST is a request from the public internet — anyone who
learns this URL could otherwise inject fake "vendor replies" into a live
negotiation. If META_APP_SECRET is set (Meta app -> Settings -> Basic),
every POST's HMAC-SHA256 signature is verified before it's trusted.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

from tools.whatsapp_provider import append_inbox

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("vendorscoutai.webhook")

app = Flask(__name__)

_APP_SECRET = os.getenv("META_APP_SECRET", "")
if not _APP_SECRET:
    logger.warning(
        "META_APP_SECRET not set — inbound webhook signatures are NOT being "
        "verified. Fine for local dev with a private tunnel; set this before "
        "exposing the webhook publicly."
    )


def _signature_valid(raw_body: bytes) -> bool:
    if not _APP_SECRET:
        return True  # nothing to check against — see startup warning above
    header = request.headers.get("X-Hub-Signature-256", "")
    if not header.startswith("sha256="):
        return False
    expected = hmac.new(_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header.removeprefix("sha256="), expected)


@app.get("/webhook")
def verify():
    """Meta's one-time subscription handshake."""
    args = request.args
    if args.get("hub.verify_token") == os.getenv("META_VERIFY_TOKEN", ""):
        return args.get("hub.challenge", ""), 200
    return "forbidden", 403


@app.post("/webhook")
def receive():
    if not _signature_valid(request.get_data()):
        logger.warning("rejected webhook POST with invalid/missing signature")
        return "forbidden", 403

    payload = request.get_json(silent=True) or {}
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if msg.get("type") != "text":
                    continue
                body = msg.get("text", {}).get("body", "")
                append_inbox({
                    "from": msg.get("from", ""),
                    "body": body,
                    "ts": float(msg.get("timestamp", time.time())),
                })
                logger.info("inbound message from=%s len=%d", msg.get("from"), len(body))
    return "ok", 200


@app.get("/health")
def health():
    """Liveness probe — process is up and can serve requests."""
    return "ok", 200


if __name__ == "__main__":
    # Dev-only. Production uses gunicorn (see Dockerfile / gunicorn.conf.py),
    # which gives real graceful shutdown, worker recycling, and concurrency.
    port = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8000")))
    app.run(port=port, host="0.0.0.0")
