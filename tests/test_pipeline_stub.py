import asyncio
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"), reason="requires GOOGLE_API_KEY"
)


def test_stub_pipeline_end_to_end(monkeypatch):
    monkeypatch.setenv("VENDORSCOUT_STUB", "1")
    monkeypatch.setenv("VENDORSCOUT_WHATSAPP_STUB", "1")
    from agents import VendorScout

    scout = VendorScout(stub=True)

    # Stage 1: discovery halts after ranking vendors for the owner to choose from.
    state = asyncio.run(
        scout.run(
            "Requirement: 500 x plain cotton tote bags. Budget: 170 INR per unit. "
            "Delivery timeline: 3 weeks. Ship to: Pune, India."
        )
    )
    assert "discovered_vendors" in state
    assert "verified_vendors" in state
    assert "negotiated_deal" not in state, "negotiation must not run before the owner picks a vendor"

    # Stage 2: owner picks the top-ranked vendor; negotiation runs and halts
    # at the deal-lock guardrail without human approval.
    top_vendor = state["verified_vendors"]
    import json
    ranked = json.loads(top_vendor.strip().removeprefix("```json").removesuffix("```").strip())
    vendor = ranked["ranked_vendors"][0]

    state = asyncio.run(scout.negotiate(vendor["name"], vendor.get("contact", "")))

    assert "negotiated_deal" in state
    assert state.get("proposed_deal", {}).get("status") == "awaiting_human_approval"
    assert "final_deal" not in state, "guardrail must prevent autonomous finalization"
