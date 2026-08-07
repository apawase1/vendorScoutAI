import asyncio
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"), reason="requires GOOGLE_API_KEY"
)


def test_stub_pipeline_end_to_end(monkeypatch):
    monkeypatch.setenv("VENDORSCOUT_STUB", "1")
    from agents import VendorScout

    scout = VendorScout(stub=True)
    state = asyncio.run(
        scout.run(
            "Requirement: 500 x plain cotton tote bags. Budget: 170 INR per unit. "
            "Delivery timeline: 3 weeks. Ship to: Pune, India."
        )
    )

    assert "discovered_vendors" in state
    assert "verified_vendors" in state
    assert "negotiated_deal" in state
    assert state.get("proposed_deal", {}).get("status") == "awaiting_human_approval"
    assert "final_deal" not in state, "guardrail must prevent autonomous finalization"
