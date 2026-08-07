"""Deal-Lock Guardrail — the trust/safety core of VendorScoutAI.

Autonomous negotiation messaging is ALLOWED.
Autonomous deal FINALIZATION is BLOCKED until a human explicitly approves
via the Streamlit UI (Lock Deal), which sets `human_approved=True` in
session state.

Kept free of ADK imports so it is trivially unit-testable: any object with
`.name` (tool) and `.state` (context) works.
"""
from __future__ import annotations

from typing import Any, Optional

APPROVAL_FLAG = "human_approved"
GUARDRAIL_LOG_KEY = "guardrail_blocked_attempts"

BLOCKED_FINALIZATION_TOOLS = frozenset({
    "finalize_deal",
    "confirm_order",
    "send_payment",
    "sign_contract",
})


def deal_lock_guardrail(
    tool: Any, args: dict[str, Any], tool_context: Any
) -> Optional[dict[str, Any]]:
    """ADK `before_tool_callback`. Returning a dict cancels the tool call
    and feeds the dict back to the agent as the tool result."""
    if tool.name not in BLOCKED_FINALIZATION_TOOLS:
        return None
    if tool_context.state.get(APPROVAL_FLAG) is True:
        return None

    attempts = list(tool_context.state.get(GUARDRAIL_LOG_KEY, []))
    attempts.append({"tool": tool.name, "args": args})
    tool_context.state[GUARDRAIL_LOG_KEY] = attempts

    return {
        "status": "BLOCKED_BY_DEAL_LOCK",
        "reason": (
            f"'{tool.name}' is a binding financial commitment and requires "
            "explicit human approval (Lock Deal) in the Streamlit UI. "
            "Present the proposed terms to the owner and stop negotiating."
        ),
    }
