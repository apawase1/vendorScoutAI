"""VendorScoutAI — 3-agent ADK SequentialAgent pipeline + deal-lock guardrail.

Pipeline state flow (output_key):
    discovered_vendors -> verified_vendors -> negotiated_deal
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai import types

from tools.negotiation_tools import (
    finalize_deal,
    propose_deal_terms,
    send_whatsapp_message,
    set_active_vendor,
    try_next_vendor,
    wait_for_vendor_reply,
)
from tools.security import APPROVAL_FLAG, deal_lock_guardrail
from tools.sourcing_tools import STUB_VENDORS
from tools.verification_tools import assess_vendor

load_dotenv()

APP_NAME = "vendorscoutai"
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

EventCallback = Optional[Callable[[Event], None]]


def stub_mode() -> bool:
    return os.getenv("VENDORSCOUT_STUB", "1").lower() in {"1", "true", "yes"}


# --------------------------------------------------------------- Sourcing

_SOURCING_INSTRUCTION = """You are the Sourcing Agent of VendorScoutAI, an
autonomous sourcing assistant for small business owners and artisans.

The user message contains a material requirement (item, quantity, budget,
timeline, location). Use the google_search tool to find real candidate
suppliers (B2B marketplaces, manufacturer directories, local wholesalers).

Extract structured vendor data directly from the grounded search results.
Respond with ONLY a JSON array of 3-6 vendors, each object having exactly:
"name", "unit_price" (number), "currency", "moq" (number), "location",
"contact", "evidence_summary". Use null for unknown fields. No markdown,
no commentary."""


def _sourcing_stub_instruction() -> str:
    return (
        "You are the Sourcing Agent of VendorScoutAI running in STUB MODE.\n"
        "Respond with ONLY this JSON array, verbatim:\n"
        + json.dumps(STUB_VENDORS, indent=2)
    )


def _extract_json(raw: str) -> Any:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.removeprefix("json").strip()
    return json.loads(text)


def _inject_demo_vendor(callback_context: Any) -> None:
    """Real google_search grounding won't find a made-up demo vendor, so we
    inject it into the candidate pool after Sourcing runs (works in stub
    mode too, as a no-op since it's already present there). Verification
    then scores it normally, and _promote_demo_vendor forces it to #1
    regardless of that score, so negotiation always targets a real,
    consenting WhatsApp number. No-op if the env var isn't set."""
    target = os.getenv("DEMO_PRIORITY_VENDOR_CONTACT")
    if not target:
        return
    name = os.getenv("DEMO_PRIORITY_VENDOR_NAME", "Aditya Materials")
    raw = callback_context.state.get("discovered_vendors")
    try:
        vendors = _extract_json(raw) if raw else []
        if not isinstance(vendors, list):
            vendors = []
    except Exception:
        vendors = []

    if any(target in str(v.get("contact", "")) for v in vendors):
        return  # already present (e.g. stub mode)

    prices = [v.get("unit_price") for v in vendors if isinstance(v.get("unit_price"), (int, float))]
    price = round(sum(prices) / len(prices), 2) if prices else 175.0

    vendors.append({
        "name": name,
        "unit_price": price,
        "currency": "INR",
        "moq": 250,
        "location": "Bengaluru, Karnataka",
        "contact": target,
        "evidence_summary": (
            "GST registered, TrustSEAL verified, established supplier with "
            "strong reviews and export history."
        ),
    })
    callback_context.state["discovered_vendors"] = json.dumps(vendors)


def build_sourcing_agent(stub: bool) -> LlmAgent:
    return LlmAgent(
        name="sourcing_agent",
        model=MODEL,
        description="Finds candidate vendors via Google Search grounding.",
        instruction=_sourcing_stub_instruction() if stub else _SOURCING_INSTRUCTION,
        # google_search is the ONLY tool here — ADK built-in tools cannot be
        # mixed with custom function tools on the same agent.
        tools=[] if stub else [google_search],
        after_agent_callback=_inject_demo_vendor,
        output_key="discovered_vendors",
    )


# ----------------------------------------------------------- Verification

def _verification_instruction(ctx: Any) -> str:
    vendors = ctx.state.get("discovered_vendors", "[]")
    return f"""You are the Verification Agent of VendorScoutAI.

Candidate vendors (search-grounded JSON from the Sourcing Agent):
{vendors}

Steps:
1. Compute the median unit_price across all candidates.
2. Call assess_vendor once per vendor, passing that median as
   market_median_price.
3. Combine the tool's deterministic score with your own judgment of the
   evidence (suspiciously low prices, missing footprint, generic listings).

Respond with ONLY JSON:
{{"ranked_vendors": [top 3 vendors, best first, each with the original
fields plus "trust_score", "red_flags", "positives"]}}"""


def _promote_demo_vendor(callback_context: Any) -> None:
    """Deterministic safety net for the live demo: whatever the LLM ranks,
    force the vendor matching DEMO_PRIORITY_VENDOR_CONTACT to the top slot
    so the Negotiation Agent always targets the real, consenting WhatsApp
    number. No-op if the env var isn't set or the vendor isn't present."""
    target = os.getenv("DEMO_PRIORITY_VENDOR_CONTACT")
    if not target:
        return
    raw = callback_context.state.get("verified_vendors")
    if not raw:
        return
    try:
        data = _extract_json(raw)
        vendors = data["ranked_vendors"]
        vendors.sort(key=lambda v: 0 if target in str(v.get("contact", "")) else 1)
        callback_context.state["verified_vendors"] = json.dumps(data)
    except Exception:
        pass  # never let the safety net break the pipeline


def build_verification_agent() -> LlmAgent:
    return LlmAgent(
        name="verification_agent",
        model=MODEL,
        description="Scores vendor trustworthiness and ranks candidates.",
        instruction=_verification_instruction,
        tools=[assess_vendor],
        after_agent_callback=_promote_demo_vendor,
        output_key="verified_vendors",
    )


# ------------------------------------------------------------ Negotiation

def _negotiation_instruction(ctx: Any) -> str:
    verified = ctx.state.get("verified_vendors", "{}")
    chosen = ctx.state.get("chosen_vendor") or {}
    chosen_line = (
        f"\nThe OWNER HAS CHOSEN this vendor to contact — use exactly this "
        f"name and contact in set_active_vendor:\n"
        f"  name: {chosen.get('name')}\n  contact: {chosen.get('contact')}\n"
        if chosen.get("name")
        else ""
    )
    return f"""You are the Negotiation Agent of VendorScoutAI.

Verified, ranked vendors:
{verified}
{chosen_line}
The owner's original requirement — including business name, business
description, item, quantity, budget, and timeline — is in the conversation
above. Use that budget as your ceiling.

Procedure:
1. Call set_active_vendor with the owner's chosen vendor above (or the
   TOP-RANKED vendor if no explicit choice was given).
2. Your FIRST send_whatsapp_message to any vendor MUST (a) disclose that you
   are an AI assistant negotiating on behalf of the named business (e.g.
   "Hi, I'm an AI assistant reaching out on behalf of GAMLA, a decorative
   pots & plants business..."), using the actual business name and
   description from the requirement above, not a generic placeholder, and
   (b) ask which language they'd prefer to continue in: English, Hindi, or
   Kannada. Every message should read as coming from that business, signed
   off naturally (not from "the business owner" or "VendorScoutAI").
3. Once the vendor states a language preference, conduct the REST of the
   negotiation with that vendor entirely in that language (natural Hindi or
   Kannada text, not transliteration) — greetings, counter-offers,
   everything. If they don't state a preference, default to English.
4. Negotiate autonomously: send_whatsapp_message -> wait_for_vendor_reply,
   counter-offering toward the owner's budget. At most 3 counter rounds.
5. If, after a genuine attempt, this vendor's best offer still exceeds the
   budget or can't meet the timeline, call try_next_vendor with a clear
   reason, then repeat steps 2-4 with the new active vendor. Do this at
   most once (two vendors total) to keep the negotiation bounded.
6. If try_next_vendor returns "no_more_vendors", propose the best offer you
   have anyway, clearly noting in the proposal that it exceeds budget, so
   the owner can make the final call.
7. Once you have acceptable (or best-available) terms, call
   propose_deal_terms with the vendor that produced them. Regardless of what
   language the negotiation happened in, propose_deal_terms' fields and your
   final JSON summary below MUST be in English — the owner reads only
   English. Translate values, don't leave them in Hindi/Kannada.
8. Then attempt finalize_deal exactly ONCE. The deal-lock guardrail will
   block it unless the owner has approved — when blocked, stop immediately.
9. NEVER promise payment or confirm an order in message text yourself;
   only finalize_deal may do that, and only when permitted.

Finish by responding with ONLY JSON, in English:
{{"vendor_name": ..., "negotiation_language": "English" | "Hindi" | "Kannada",
"terms": {{"quantity", "unit_price", "currency", "delivery_timeline",
"payment_terms"}}, "rounds": <int>, "switched_vendor": true | false,
"status": "awaiting_human_approval" | "finalized"}}"""


def build_negotiation_agent(name: str = "negotiation_agent") -> LlmAgent:
    return LlmAgent(
        name=name,
        model=MODEL,
        description="Negotiates via WhatsApp; cannot finalize without human approval.",
        instruction=_negotiation_instruction,
        tools=[
            set_active_vendor,
            send_whatsapp_message,
            wait_for_vendor_reply,
            try_next_vendor,
            propose_deal_terms,
            finalize_deal,
        ],
        before_tool_callback=deal_lock_guardrail,  # deal-lock guardrail wiring
        output_key="negotiated_deal",
    )


# ------------------------------------------------------------ Orchestration

def build_pipeline(stub: Optional[bool] = None) -> SequentialAgent:
    """Full autonomous chain — kept for `adk run` / non-interactive use."""
    stub = stub_mode() if stub is None else stub
    return SequentialAgent(
        name="vendorscout_pipeline",
        description="Sourcing -> Verification -> Negotiation",
        sub_agents=[
            build_sourcing_agent(stub),
            build_verification_agent(),
            build_negotiation_agent(),
        ],
    )


def build_discovery_pipeline(stub: Optional[bool] = None) -> SequentialAgent:
    """Sourcing -> Verification only. The pipeline HALTS here so the owner
    can choose which of the ranked vendors to actually contact — the first
    of two human-in-the-loop checkpoints (the second is the deal lock)."""
    stub = stub_mode() if stub is None else stub
    return SequentialAgent(
        name="vendorscout_discovery",
        description="Sourcing -> Verification",
        sub_agents=[
            build_sourcing_agent(stub),
            build_verification_agent(),
        ],
    )


class VendorScout:
    """Owns the shared in-memory session plus two runners:
    the full pipeline, and a finalizer (negotiation-only) used after the
    owner's Lock/Reject decision — mirroring the architecture's
    'if locked: final-confirmation -> NEG' edge."""

    def __init__(self, stub: Optional[bool] = None,
                 user_id: str = "owner", session_id: str = "demo"):
        self.user_id = user_id
        self.session_id = session_id
        self.session_service = InMemorySessionService()
        self.requirement = ""
        self.discovery = Runner(
            app_name=APP_NAME,
            agent=build_discovery_pipeline(stub),
            session_service=self.session_service,
        )
        self.negotiator = Runner(
            app_name=APP_NAME,
            agent=build_negotiation_agent(),
            session_service=self.session_service,
        )
        self.finalizer = Runner(
            app_name=APP_NAME,
            agent=build_negotiation_agent("finalizer_agent"),
            session_service=self.session_service,
        )

    async def _session(self):
        session = await self.session_service.get_session(
            app_name=APP_NAME, user_id=self.user_id, session_id=self.session_id
        )
        if session is None:
            session = await self.session_service.create_session(
                app_name=APP_NAME, user_id=self.user_id, session_id=self.session_id
            )
        return session

    async def _drive(self, runner: Runner, text: str, on_event: EventCallback) -> dict:
        await self._session()
        message = types.Content(role="user", parts=[types.Part(text=text)])
        async for event in runner.run_async(
            user_id=self.user_id, session_id=self.session_id, new_message=message
        ):
            if on_event:
                on_event(event)
        return await self.state()

    async def run(self, requirement: str, on_event: EventCallback = None) -> dict:
        """Stage 1: source + verify, then HALT for the owner's vendor choice."""
        self.requirement = requirement
        return await self._drive(self.discovery, requirement, on_event)

    async def set_chosen_vendor(self, name: str, contact: str) -> None:
        session = await self._session()
        await self.session_service.append_event(
            session,
            Event(
                author="user",
                actions=EventActions(
                    state_delta={"chosen_vendor": {"name": name, "contact": contact}}
                ),
            ),
        )

    async def negotiate(self, name: str, contact: str,
                        on_event: EventCallback = None) -> dict:
        """Stage 2: negotiate with the owner-chosen vendor, falling back to
        the next-best ranked vendor if this one can't meet the terms."""
        await self.set_chosen_vendor(name, contact)
        return await self._drive(
            self.negotiator,
            f"{self.requirement}\n\nThe owner chose to contact {name} ({contact}) "
            "first. Begin negotiation with them.",
            on_event,
        )

    async def state(self) -> dict:
        session = await self.session_service.get_session(
            app_name=APP_NAME, user_id=self.user_id, session_id=self.session_id
        )
        return dict(session.state) if session else {}

    async def set_approval(self, approved: bool) -> None:
        session = await self._session()
        await self.session_service.append_event(
            session,
            Event(
                author="user",
                actions=EventActions(state_delta={APPROVAL_FLAG: approved}),
            ),
        )

    async def approve_and_finalize(self, on_event: EventCallback = None) -> dict:
        await self.set_approval(True)
        return await self._drive(
            self.finalizer,
            "The owner LOCKED the deal in the UI. Call finalize_deal now with "
            "a confirmation message for the agreed terms.",
            on_event,
        )

    async def reject(self, on_event: EventCallback = None) -> dict:
        await self.set_approval(False)
        return await self._drive(
            self.finalizer,
            "The owner REJECTED the proposed terms. Send one polite WhatsApp "
            "message declining for now. Do NOT call finalize_deal.",
            on_event,
        )


root_agent = build_pipeline()
