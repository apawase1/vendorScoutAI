"""Meta WhatsApp webhook receiver.

Meta delivers inbound messages by webhook only (no polling endpoint), so this
tiny server catches them and appends to the shared inbox file that
tools/whatsapp_provider.py polls.

Run alongside Streamlit:
    python webhook_server.py          # listens on :8000
    ngrok http 8000                   # public HTTPS URL for Meta

Then in the Meta app: WhatsApp -> Configuration -> Edit webhook
    Callback URL:  https://<ngrok-id>.ngrok-free.app/webhook
    Verify token:  same value as META_VERIFY_TOKEN in .env
and subscribe to the `messages` field.
"""
from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

from tools.whatsapp_provider import append_inbox

app = Flask(__name__)


@app.get("/webhook")
def verify():
    """Meta's one-time subscription handshake."""
    args = request.args
    if args.get("hub.verify_token") == os.getenv("META_VERIFY_TOKEN", "vendorscout"):
        return args.get("hub.challenge", ""), 200
    return "forbidden", 403


@app.post("/webhook")
def receive():
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
                print(f"[inbound] {msg.get('from')}: {body}", flush=True)
    return "ok", 200


@app.get("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    app.run(port=int(os.getenv("WEBHOOK_PORT", "8000")), host="0.0.0.0")
