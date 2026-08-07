"""Negotiation Agent function tools — WhatsApp messaging + deal proposal.

Transport (Meta Cloud API or Twilio) lives in tools/whatsapp_provider.py.
This module handles negotiation logic: who we're talking to, transcript
logging, vendor switching, and the proposal/finalize split the deal-lock
guardrail gates.

Negotiates with a REAL vendor over live WhatsApp (the demo vendor, identified
by DEMO_PRIORITY_VENDOR_CONTACT), falling back to the next ranked vendor from
Verification's output if that vendor can't meet the owner's budget/timeline.
Only one real WhatsApp number exists for the demo, so fallback vendors use
scripted replies (`MOCK_REPLIES` in sourcing_tools.py).
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

from google.adk.tools import ToolContext

from tools import whatsapp_provider
from tools.sourcing_tools import MOCK_REPLIES

TRANSCRIPT_KEY = "whatsapp_transcript"
ACTIVE_VENDOR_KEY = "active_vendor"
TRIED_VENDORS_KEY = "tried_vendor_names"
SWITCH_LOG_KEY = "vendor_switch_log"

_FALLBACK_REPLIES = [
    "Hello! Yes, we supply these. For that quantity the rate is 190 INR per unit, delivery in 4 weeks.",
    "We can come down to 172 INR per unit if you confirm this week. Delivery in 3 weeks.",
    "Final offer: 165 INR per unit, 2.5 weeks delivery, 30% advance payment.",
]


def _whatsapp_stub_mode() -> bool:
    flag = os.getenv("VENDORSCOUT_WHATSAPP_STUB", os.getenv("VENDORSCOUT_STUB", "1"))
    return flag.lower() in {"1", "true", "yes"}


def whatsapp_stub_mode() -> bool:
    """Public accessor for the UI layer."""
    return _whatsapp_stub_mode()


def _extract_json(raw: str) -> Any:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    return json.loads(text)


def _log(tool_context: ToolContext, direction: str, body: str, vendor: str = "") -> None:
    transcript = list(tool_context.state.get(TRANSCRIPT_KEY, []))
    transcript.append({"direction": direction, "body": body, "vendor": vendor, "ts": time.time()})
    tool_context.state[TRANSCRIPT_KEY] = transcript


def _active_vendor(tool_context: ToolContext) -> dict[str, str]:
    return tool_context.state.get(ACTIVE_VENDOR_KEY) or {"name": "", "contact": ""}


def _is_real_vendor(tool_context: ToolContext) -> bool:
    real = os.getenv("DEMO_PRIORITY_VENDOR_CONTACT", "").replace(" ", "")
    contact = _active_vendor(tool_context).get("contact", "").replace(" ", "")
    return bool(real) and real in contact


def set_active_vendor(vendor_name: str, contact: str, tool_context: ToolContext) -> dict[str, Any]:
    """Set which vendor the negotiation is currently targeting.

    Call this once before the first message to a vendor, and again whenever
    switching to a fallback vendor.
    """
    tool_context.state[ACTIVE_VENDOR_KEY] = {"name": vendor_name, "contact": contact}
    tried = list(tool_context.state.get(TRIED_VENDORS_KEY, []))
    if vendor_name not in tried:
        tried.append(vendor_name)
        tool_context.state[TRIED_VENDORS_KEY] = tried
    return {"status": "active_vendor_set", "vendor_name": vendor_name}


def try_next_vendor(current_vendor_name: str, reason: str, tool_context: ToolContext) -> dict[str, Any]:
    """Switch to the next-ranked vendor when the current one can't meet the
    owner's budget or timeline after a genuine negotiation attempt.

    Args:
        current_vendor_name: The vendor being dropped.
        reason: Why negotiation with this vendor failed (e.g. "quoted price
            35 INR above budget after 3 rounds").
    """
    try:
        vendors = _extract_json(tool_context.state.get("verified_vendors", "{}")).get(
            "ranked_vendors", []
        )
    except Exception:
        vendors = []

    tried = set(tool_context.state.get(TRIED_VENDORS_KEY, []))
    candidate = next((v for v in vendors if v.get("name") not in tried), None)
    if not candidate:
        return {"status": "no_more_vendors"}

    switch_log = list(tool_context.state.get(SWITCH_LOG_KEY, []))
    switch_log.append({
        "from": current_vendor_name,
        "to": candidate["name"],
        "reason": reason,
        "ts": time.time(),
    })
    tool_context.state[SWITCH_LOG_KEY] = switch_log

    set_active_vendor(candidate["name"], candidate.get("contact", ""), tool_context)
    return {"status": "switched", "new_vendor": candidate}


def send_whatsapp_message(body: str, tool_context: ToolContext) -> dict[str, Any]:
    """Send a WhatsApp message to the currently active vendor.

    Args:
        body: Message text. The FIRST message to any vendor MUST disclose
            that the sender is an AI assistant acting on the owner's behalf.
    """
    vendor = _active_vendor(tool_context)
    vendor_name = vendor.get("name", "")
    _log(tool_context, "outbound", body, vendor_name)

    if not (_is_real_vendor(tool_context) and not _whatsapp_stub_mode()):
        return {"status": "sent", "mode": "mock" if vendor_name else "stub"}

    # Mark the send time so wait_for_vendor_reply only accepts newer inbound
    # messages, not the vendor's earlier window-opening message.
    tool_context.state["last_outbound_ts"] = time.time()
    return whatsapp_provider.send_message(body)


def wait_for_vendor_reply(tool_context: ToolContext) -> dict[str, Any]:
    """Wait for the active vendor's next inbound WhatsApp reply."""
    vendor = _active_vendor(tool_context)
    vendor_name = vendor.get("name", "")

    if not (_is_real_vendor(tool_context) and not _whatsapp_stub_mode()):
        replies = MOCK_REPLIES.get(vendor_name, _FALLBACK_REPLIES)
        idx_key = f"reply_index::{vendor_name or 'default'}"
        idx = tool_context.state.get(idx_key, 0)
        reply = replies[min(idx, len(replies) - 1)]
        tool_context.state[idx_key] = idx + 1
        _log(tool_context, "inbound", reply, vendor_name)
        return {"reply": reply}

    since = tool_context.state.get("last_inbound_ts") or tool_context.state.get(
        "last_outbound_ts", time.time()
    )
    msg = whatsapp_provider.wait_for_reply(
        since_ts=since, timeout_s=int(os.getenv("REPLY_TIMEOUT_SECONDS", "180"))
    )
    if not msg:
        return {"reply": None, "error": "timeout waiting for vendor reply"}

    tool_context.state["last_inbound_ts"] = msg["ts"]
    _log(tool_context, "inbound", msg["body"], vendor_name)
    return {"reply": msg["body"]}


def propose_deal_terms(
    vendor_name: str,
    item: str,
    quantity: int,
    unit_price: float,
    currency: str,
    delivery_timeline: str,
    payment_terms: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Record the best negotiated terms as a PROPOSAL for human review.

    This is NOT binding — it queues the deal for the owner's Lock/Reject
    decision in the Streamlit UI.
    """
    proposal = {
        "vendor_name": vendor_name,
        "item": item,
        "quantity": quantity,
        "unit_price": unit_price,
        "currency": currency,
        "total": round(quantity * unit_price, 2),
        "delivery_timeline": delivery_timeline,
        "payment_terms": payment_terms,
        "status": "awaiting_human_approval",
    }
    tool_context.state["proposed_deal"] = proposal
    return {"status": "proposal_recorded_awaiting_human_approval", "proposal": proposal}


def finalize_deal(confirmation_message: str, tool_context: ToolContext) -> dict[str, Any]:
    """BINDING ACTION: confirm the order with the vendor over WhatsApp.

    Intercepted by the deal-lock guardrail unless the owner has explicitly
    approved via the Streamlit UI.
    """
    vendor_name = _active_vendor(tool_context).get("name", "")
    _log(tool_context, "outbound", confirmation_message, vendor_name)
    if _is_real_vendor(tool_context) and not _whatsapp_stub_mode():
        whatsapp_provider.send_message(confirmation_message)
    deal = dict(tool_context.state.get("proposed_deal", {}))
    deal["status"] = "finalized"
    tool_context.state["final_deal"] = deal
    return {"status": "finalized", "deal": deal}
