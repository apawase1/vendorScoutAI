from types import SimpleNamespace

from tools.security import (
    APPROVAL_FLAG,
    BLOCKED_FINALIZATION_TOOLS,
    GUARDRAIL_LOG_KEY,
    deal_lock_guardrail,
)


def _tool(name):
    return SimpleNamespace(name=name)


def _ctx(state=None):
    return SimpleNamespace(state=state if state is not None else {})


def test_blocks_every_finalization_tool_without_approval():
    for name in BLOCKED_FINALIZATION_TOOLS:
        result = deal_lock_guardrail(_tool(name), {}, _ctx())
        assert result["status"] == "BLOCKED_BY_DEAL_LOCK"


def test_allows_finalization_with_explicit_approval():
    ctx = _ctx({APPROVAL_FLAG: True})
    assert deal_lock_guardrail(_tool("finalize_deal"), {}, ctx) is None


def test_truthy_but_not_true_is_still_blocked():
    ctx = _ctx({APPROVAL_FLAG: "yes"})
    assert deal_lock_guardrail(_tool("finalize_deal"), {}, ctx) is not None


def test_negotiation_messaging_is_never_blocked():
    for name in ("send_whatsapp_message", "wait_for_vendor_reply", "propose_deal_terms"):
        assert deal_lock_guardrail(_tool(name), {}, _ctx()) is None


def test_blocked_attempts_are_logged():
    ctx = _ctx()
    deal_lock_guardrail(_tool("confirm_order"), {"amount": 5}, ctx)
    deal_lock_guardrail(_tool("send_payment"), {}, ctx)
    log = ctx.state[GUARDRAIL_LOG_KEY]
    assert [e["tool"] for e in log] == ["confirm_order", "send_payment"]
