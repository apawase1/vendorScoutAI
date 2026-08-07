# PRD — VendorScoutAI

**Event:** Google AI Agent Builder Series 2026 · B2B Services track · Problem Statement #7: Vendor Evaluation

## Problem

Small business owners and artisans lose hours finding, vetting, and haggling with material suppliers. They lack procurement teams, and marketplace listings are noisy — inflated claims, ghost vendors, suspiciously cheap offers.

## Solution

An autonomous sourcing agent: give it an item, quantity, budget, and timeline; it discovers vendors, verifies trustworthiness, and negotiates over WhatsApp on the owner's behalf — while the owner keeps sole authority over the final commitment.

## Users

Primary: small business owners / artisans in India sourcing materials (textiles, packaging, raw goods). Secondary: micro-manufacturers scaling procurement.

## Core user journey

1. Owner enters requirement in the Streamlit dashboard and clicks Start Sourcing.
2. Sourcing Agent finds 3–6 candidate vendors via Google Search grounding.
3. Verification Agent scores trust (price sanity, contactability, footprint, reviews) and ranks the top 3.
4. Negotiation Agent opens WhatsApp with the top vendor, disclosing itself as an AI assistant, and negotiates up to 3 counter rounds toward the budget.
5. Agent records the best terms as a proposal and attempts finalization — the Deal-Lock Guardrail blocks it.
6. Owner reviews the proposal and transcript, then Locks (agent sends binding confirmation) or Rejects (agent declines politely).

## Requirements

**Functional:** structured vendor extraction from grounded search; deterministic + LLM trust scoring with explicit red flags; autonomous WhatsApp back-and-forth via Twilio Sandbox; live activity trace; human Lock/Reject approval gate; stub mode for offline demo.

**Safety (non-negotiable):** mandatory AI self-disclosure in the first vendor message; `before_tool_callback` blocklist rejecting payment/confirmation/commitment tools unless `human_approved=True`; guardrail is a distinct, auditable layer with logged blocked attempts.

**Non-functional:** in-process session state only (no external DB); single API-key setup; demo honesty — Twilio Sandbox test number, not Meta's Business API.

## Out of scope

Payments execution, multi-vendor parallel negotiation, Meta WhatsApp Business API, persistent vendor database, authentication.

## Success criteria

End-to-end run completes in under ~2 minutes in stub mode; guardrail visibly blocks ≥1 finalization attempt per run; zero binding messages sent without human approval; judges can trace every agent step in the UI.
