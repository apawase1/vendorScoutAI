"""VendorScoutAI — Streamlit dashboard: live trace + deal approval UI.

Visual theme: strict two-tone — espresso-brown (#3D2314) and cream
(#FDFBF7) only, no other hues. Contrast is enforced explicitly on every
component, including Streamlit/BaseWeb internals (dropdown popovers,
expanders, alerts) that don't inherit page-level styles by default.
"""
from __future__ import annotations

import asyncio
import json

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agents import VendorScout, stub_mode
from tools.demo_data import demo_state
from tools.negotiation_tools import (
    ACTIVE_VENDOR_KEY,
    SWITCH_LOG_KEY,
    TRANSCRIPT_KEY,
    whatsapp_stub_mode,
)
from tools.security import GUARDRAIL_LOG_KEY

st.set_page_config(page_title="VendorScoutAI", page_icon="🧭", layout="wide")

# --------------------------------------------------------------- Theme
# Pure light theme (forced via .streamlit/config.toml, never follows OS
# dark mode). Espresso is used ONLY as an accent on light surfaces — never
# large brown fills with brown text, which caused the blending issues.

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&display=swap');

:root {
    --espresso: #3D2314;
    --ink: #2A1A0E;          /* primary text */
    --ink-soft: #6E5B4C;     /* secondary text */
    --cream: #FDFBF7;        /* page background */
    --card: #FFFFFF;         /* card surfaces */
    --line: #E7DFD2;         /* hairline borders */
    --wash: #F4EEE3;         /* subtle fills */
}

html, body, [class*="css"] { font-family: 'Nunito', sans-serif; }
.stApp { background: var(--cream); }
.block-container { padding-top: 1rem; max-width: 1180px; }
h1, h2, h3 { color: var(--espresso) !important; }
[data-testid="stMarkdownContainer"] p { color: var(--ink); }

/* ---- Header ---- */
.vs-header {
    background: var(--card);
    border: 1px solid var(--line);
    border-top: 4px solid var(--espresso);
    border-radius: 14px;
    padding: 1.5rem 2rem 1.3rem 2rem;
    margin-bottom: 1.2rem;
    text-align: center;
    box-shadow: 0 2px 12px rgba(61, 35, 20, 0.06);
}
.vs-header h1 { color: var(--espresso); font-size: 2.1rem; font-weight: 800; margin: 0; }
.vs-header p { color: var(--ink-soft); margin: 0.45rem 0 0 0; font-size: 0.95rem; }
.vs-header b { color: var(--espresso); }

/* ---- Sidebar: light, clean, clearly separated ---- */
[data-testid="stSidebar"] {
    background: var(--card);
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] h2 {
    font-weight: 800;
    font-size: 1.15rem;
    color: var(--espresso) !important;
    border-bottom: 2px solid var(--espresso);
    padding-bottom: 0.5rem;
}
[data-testid="stSidebar"] label { color: var(--ink) !important; font-weight: 600; }
[data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] small { color: var(--ink-soft) !important; }

/* ---- Buttons ----
   Streamlit 1.61 renders data-testid="stBaseButton-primary/secondary"
   instead of a kind="" attribute — both selectors kept for safety across
   versions. */
.stButton > button,
button[data-testid^="stBaseButton"] {
    border-radius: 10px !important;
    font-weight: 700 !important;
    padding: 0.55rem 1.5rem !important;
    transition: transform 0.08s ease-in-out, box-shadow 0.08s ease-in-out;
}
.stButton > button:hover,
button[data-testid^="stBaseButton"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 3px 10px rgba(61,35,20,0.15);
}
.stButton > button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: var(--espresso) !important;
    color: #FFFFFF !important;
    border: none !important;
}
.stButton > button[kind="primary"] p,
button[data-testid="stBaseButton-primary"] p,
button[data-testid="stBaseButton-primary"] div {
    color: #FFFFFF !important;
}
.stButton > button[kind="secondary"],
button[data-testid="stBaseButton-secondary"] {
    background: var(--card) !important;
    color: var(--espresso) !important;
    border: 1.5px solid var(--espresso) !important;
}
.stButton > button[kind="secondary"] p,
button[data-testid="stBaseButton-secondary"] p,
button[data-testid="stBaseButton-secondary"] div {
    color: var(--espresso) !important;
}

/* ---- Section headers ---- */
.vs-section {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--espresso);
    margin: 0.4rem 0 0.7rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 2px solid var(--line);
}

/* ---- Vendor cards ---- */
.vs-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-left: 4px solid var(--espresso);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 1px 6px rgba(61, 35, 20, 0.05);
    color: var(--ink);
}
.vs-card b { color: var(--espresso); font-size: 1rem; }
.vs-card .vs-meta { margin-top: 0.5rem; font-size: 0.87rem; color: var(--ink-soft); }
.vs-badge {
    display: inline-block;
    padding: 0.16rem 0.6rem;
    border-radius: 999px;
    font-size: 0.73rem;
    font-weight: 700;
    margin: 0.15rem 0.25rem 0.15rem 0;
}
.vs-badge-outline { background: var(--wash); color: var(--espresso); border: 1px solid var(--line); }
.vs-badge-filled { background: var(--espresso); color: #FFFFFF; }
.vs-scorebar-track { background: var(--wash); border-radius: 999px; height: 7px; width: 100%; margin-top: 0.4rem; }
.vs-scorebar-fill { background: var(--espresso); height: 7px; border-radius: 999px; }

/* ---- Chat ----
   Tinted canvas so BOTH bubble styles read as raised surfaces against it:
   outgoing = solid espresso, incoming = pure white w/ border + shadow. */
.vs-chatwrap {
    background: #EFE7DA;
    border-radius: 12px;
    padding: 1rem;
    border: 1px solid var(--line);
    max-height: 480px;
    overflow-y: auto;
    box-shadow: inset 0 1px 4px rgba(61, 35, 20, 0.07);
}
.vs-bubble-row { display: flex; margin-bottom: 0.6rem; }
.vs-bubble-row.out { justify-content: flex-end; }
.vs-bubble-row.in { justify-content: flex-start; }
.vs-bubble {
    max-width: 74%;
    padding: 0.6rem 0.9rem;
    border-radius: 14px;
    font-size: 0.92rem;
    line-height: 1.45;
    box-shadow: 0 1px 3px rgba(61, 35, 20, 0.14);
}
.vs-bubble.out {
    background: var(--espresso);
    color: #FFFFFF;
    border-bottom-right-radius: 3px;
}
.vs-bubble.out .vs-bubble-label { color: #D9C3AE; }
.vs-bubble.in {
    background: #FFFFFF;
    color: var(--ink);
    border: 1px solid #D9CDBB;
    border-bottom-left-radius: 3px;
}
.vs-bubble.in .vs-bubble-label { color: var(--espresso); }
.vs-bubble-label { font-size: 0.67rem; margin-bottom: 0.2rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.4px; }
.vs-switch-banner {
    text-align: center;
    font-size: 0.82rem;
    color: var(--espresso);
    background: var(--wash);
    border: 1px dashed var(--espresso);
    border-radius: 10px;
    padding: 0.45rem 0.7rem;
    margin: 0.6rem 0;
    font-weight: 600;
}

/* ---- Deal proposal card ---- */
.vs-invite {
    background: var(--card);
    border: 1px solid var(--line);
    border-top: 4px solid var(--espresso);
    border-radius: 14px;
    padding: 1.3rem 1.6rem;
    box-shadow: 0 2px 12px rgba(61, 35, 20, 0.08);
    color: var(--ink);
}
.vs-invite h3 { color: var(--espresso); margin: 0 0 0.6rem 0; font-weight: 800; }
.vs-invite .vs-terms { display: flex; flex-wrap: wrap; gap: 0.5rem 1.6rem; margin-top: 0.4rem; }
.vs-invite .vs-term { font-size: 0.92rem; }
.vs-invite .vs-term small { display: block; color: var(--ink-soft); font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }

/* ---- Confirmed deal receipt ---- */
.vs-receipt {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 16px;
    margin-top: 0.8rem;
    overflow: hidden;
    box-shadow: 0 4px 18px rgba(61, 35, 20, 0.10);
    color: var(--ink);
}
.vs-receipt-head {
    background: var(--espresso);
    padding: 1.1rem 1.6rem;
    text-align: center;
}
.vs-receipt-title {
    color: #FFFFFF;
    font-size: 1.25rem;
    font-weight: 800;
    letter-spacing: 0.3px;
}
.vs-receipt-sub { color: #D9C3AE; font-size: 0.85rem; margin-top: 0.15rem; }
.vs-receipt-sub b { color: #FFFFFF; }

.vs-receipt-hero {
    text-align: center;
    padding: 1.5rem 1.6rem 1.2rem 1.6rem;
    border-bottom: 1px dashed var(--line);
}
.vs-hero-item {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--ink-soft);
}
.vs-hero-total {
    font-size: 2.6rem;
    font-weight: 800;
    color: var(--espresso);
    line-height: 1.15;
    margin: 0.25rem 0 0.1rem 0;
}
.vs-hero-calc { font-size: 0.88rem; color: var(--ink-soft); }

.vs-receipt-rows { padding: 0.4rem 1.6rem; }
.vs-rrow {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1.5rem;
    padding: 0.7rem 0;
    border-bottom: 1px solid var(--line);
    font-size: 0.92rem;
}
.vs-rrow:last-child { border-bottom: none; }
.vs-rrow span { color: var(--ink-soft); font-weight: 600; white-space: nowrap; }
.vs-rrow b { color: var(--espresso); text-align: right; }

.vs-receipt-foot {
    background: var(--wash);
    padding: 1rem 1.6rem 1.2rem 1.6rem;
    text-align: center;
}
.vs-receipt-foot a {
    display: inline-block;
    background: var(--espresso);
    color: #FFFFFF !important;
    text-decoration: none;
    font-weight: 700;
    font-size: 0.9rem;
    padding: 0.5rem 1.3rem;
    border-radius: 10px;
}
.vs-receipt-note {
    margin-top: 0.8rem;
    font-size: 0.8rem;
    color: var(--ink-soft);
    line-height: 1.5;
}
.vs-receipt a { color: var(--espresso); font-weight: 700; }

/* ---- Raw JSON / agent output blocks ---- */
.vs-pre {
    background: var(--wash);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.8rem 1rem;
    font-family: ui-monospace, 'SF Mono', 'Courier New', monospace;
    font-size: 0.8rem;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 380px;
    overflow-y: auto;
}

/* ---- Live trace (st.status) readability ---- */
[data-testid="stExpander"] details, div[data-testid="stStatusWidget"] { background: var(--card); }
[data-testid="stExpander"] {
    border: 1px solid var(--line) !important;
    border-radius: 12px !important;
    background: var(--card) !important;
}
[data-testid="stExpander"] code {
    background: var(--wash) !important;
    color: var(--espresso) !important;
    border-radius: 6px;
    padding: 0.1rem 0.35rem;
    font-size: 0.8rem;
}
</style>
""",
    unsafe_allow_html=True,
)


def scout() -> VendorScout:
    if "scout" not in st.session_state:
        st.session_state.scout = VendorScout()
    return st.session_state.scout


def run(coro):
    return asyncio.run(coro)


def describe_event(event) -> str | None:
    parts = getattr(getattr(event, "content", None), "parts", None) or []
    lines = []
    for part in parts:
        if getattr(part, "text", None):
            text = part.text.strip()
            if len(text) > 220:
                text = text[:220] + "…"
            lines.append(text)
        call = getattr(part, "function_call", None)
        if call:
            args = dict(call.args or {})
            brief = ", ".join(f"{k}={str(v)[:40]}" for k, v in list(args.items())[:3])
            lines.append(f"→ calling `{call.name}` ({brief})" if brief else f"→ calling `{call.name}`")
        resp = getattr(part, "function_response", None)
        if resp:
            r = resp.response if isinstance(resp.response, dict) else {}
            if r.get("status") == "BLOCKED_BY_DEAL_LOCK":
                lines.append(f"⛔ **GUARDRAIL BLOCKED** `{resp.name}` — human approval required")
            else:
                status = r.get("status") or r.get("reply") or "done"
                lines.append(f"✓ `{resp.name}` → {str(status)[:120]}")
    return "\n\n".join(lines) or None


_AGENT_LABELS = {
    "sourcing_agent": "🔎 Sourcing Agent",
    "verification_agent": "🛡️ Verification Agent",
    "negotiation_agent": "🤝 Negotiation Agent",
    "finalizer_agent": "🤝 Negotiation Agent",
}


def trace_run(coro_factory, label: str):
    box = st.status(label, expanded=True)

    def on_event(event):
        text = describe_event(event)
        if text:
            author = _AGENT_LABELS.get(event.author, event.author)
            box.markdown(f"**{author}**\n\n{text}")

    state = run(coro_factory(on_event))
    box.update(state="complete", expanded=False)
    st.session_state.pipeline_state = state


def parse_json(raw):
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
    except (json.JSONDecodeError, AttributeError):
        return raw


def render_json(data) -> None:
    """Render JSON as a monochrome pre block instead of st.json, which
    ships its own syntax-highlight theme that ignores our CSS overrides."""
    st.markdown(f'<div class="vs-pre">{json.dumps(data, indent=2, default=str)}</div>', unsafe_allow_html=True)


def vendor_cards(verified: dict, selectable: bool = False):
    """Render ranked vendors. When `selectable`, each of the top 3 gets a
    'Contact <number>' button — the owner picks who to approach first."""
    vendors = (verified or {}).get("ranked_vendors", [])
    for i, v in enumerate(vendors):
        score = int(v.get("trust_score", 0))
        badges = "".join(f'<span class="vs-badge vs-badge-outline">{p}</span>' for p in v.get("positives", [])[:3])
        flags = "".join(f'<span class="vs-badge vs-badge-filled">{f}</span>' for f in v.get("red_flags", []))
        contact = v.get("contact") or "—"
        st.markdown(
            f"""
<div class="vs-card">
  <b>#{i+1} {v.get('name','?')}</b>
  <span class="vs-badge vs-badge-filled">Trust {score}/100</span>
  <div class="vs-scorebar-track"><div class="vs-scorebar-fill" style="width:{max(score,4)}%"></div></div>
  <div class="vs-meta">
    {v.get('location','—')} · ₹{v.get('unit_price','?')} /unit · MOQ {v.get('moq','?')} · {contact}
  </div>
  <div style="margin-top:0.4rem;">{badges}{flags}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if selectable and i < 3 and v.get("contact"):
            if st.button(
                f"Contact {contact}",
                key=f"contact_{i}",
                type="primary" if i == 0 else "secondary",
                use_container_width=True,
            ):
                st.session_state.negotiating_with = {
                    "name": v.get("name", ""), "contact": v.get("contact", "")
                }
                st.rerun()


def chat_timeline(state: dict):
    events = []
    for m in state.get(TRANSCRIPT_KEY, []):
        events.append((m.get("ts", 0), "message", m))
    for s in state.get(SWITCH_LOG_KEY, []):
        events.append((s.get("ts", 0), "switch", s))
    events.sort(key=lambda e: e[0])

    html = ['<div class="vs-chatwrap">']
    for _, kind, payload in events:
        if kind == "switch":
            html.append(
                f'<div class="vs-switch-banner">🔄 Switched vendor: '
                f'<b>{payload["from"]}</b> → <b>{payload["to"]}</b> — {payload["reason"]}</div>'
            )
        else:
            side = "out" if payload["direction"] == "outbound" else "in"
            label = "VendorScoutAI (AI)" if side == "out" else payload.get("vendor", "Vendor")
            html.append(
                f'<div class="vs-bubble-row {side}"><div class="vs-bubble {side}">'
                f'<div class="vs-bubble-label">{label}</div>{payload["body"]}</div></div>'
            )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


# --------------------------------------------------------------- Layout

TIMELINE_OPTIONS = ["1 week", "2 weeks", "3 weeks", "4 weeks", "6 weeks"]
FILTER_DEFAULTS = {
    "f_business_name": "GAMLA",
    "f_business_desc": "decorative pots & plants",
    "f_item": "Decorative clay pots",
    "f_quantity": 500,
    "f_budget": 170.0,
    "f_timeline": "3 weeks",
    "f_location": "Pune, India",
}
# Values the form is emptied to when the canned demo is loaded.
FILTER_EMPTY = {
    "f_business_name": "", "f_business_desc": "", "f_item": "",
    "f_quantity": 1, "f_budget": 1.0, "f_timeline": "3 weeks", "f_location": "",
}

# Widget state can't be mutated after a widget renders, so honour pending
# requests here — before any input is instantiated.
if st.session_state.pop("_clear_requirements", False):
    for k, v in FILTER_EMPTY.items():
        st.session_state[k] = v

if st.session_state.pop("_load_demo", False):
    st.session_state.pipeline_state = demo_state(finalized=True)
    st.session_state.demo_mode = True

st.markdown(
    """
<div class="vs-header">
  <h1>🧭 VendorScoutAI</h1>
  <p>Autonomous sourcing • verified vendors • AI-negotiated deals on WhatsApp — <b>finalized only by you.</b></p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Material Requirement")
    business_name = st.text_input("Your business name", FILTER_DEFAULTS["f_business_name"], key="f_business_name")
    business_desc = st.text_input("Business description", FILTER_DEFAULTS["f_business_desc"], key="f_business_desc")
    item = st.text_input("Item", FILTER_DEFAULTS["f_item"], key="f_item")
    quantity = st.number_input("Quantity", 1, 100000, FILTER_DEFAULTS["f_quantity"], key="f_quantity")
    budget = st.number_input("Budget per unit (INR)", 1.0, 1e6, FILTER_DEFAULTS["f_budget"], key="f_budget")
    timeline = st.selectbox("Timeline", TIMELINE_OPTIONS,
                            index=TIMELINE_OPTIONS.index(FILTER_DEFAULTS["f_timeline"]), key="f_timeline")
    location = st.text_input("Ship to", FILTER_DEFAULTS["f_location"], key="f_location")

    if st.button("Clear", use_container_width=True, help="Empty the form"):
        st.session_state["_clear_requirements"] = True
        st.rerun()
    if st.button("Load demo", use_container_width=True,
                 help="Show a complete pre-recorded run"):
        st.session_state["_load_demo"] = True
        st.rerun()

    st.divider()
    st.caption(f"Search: {'stub' if stub_mode() else 'live'}  ·  WhatsApp: {'stub' if whatsapp_stub_mode() else 'live'}")

_, cta_col, _ = st.columns([1, 2, 1])
with cta_col:
    start_clicked = st.button("Start Sourcing", type="primary", use_container_width=True)

if start_clicked:
    for k in ("pipeline_state", "negotiating_with", "demo_mode"):
        st.session_state.pop(k, None)
    requirement = (
        f"Business: {business_name} ({business_desc}). "
        f"Requirement: {quantity} x {item}. Budget: {budget} INR per unit. "
        f"Delivery timeline: {timeline}. Ship to: {location}."
    )
    trace_run(lambda cb: scout().run(requirement, on_event=cb),
              "Finding and verifying vendors…")

# Owner picked a vendor -> run the negotiation stage.
pending = st.session_state.pop("negotiating_with", None)
if pending:
    trace_run(
        lambda cb: scout().negotiate(pending["name"], pending["contact"], on_event=cb),
        f"Negotiating with {pending['name']}…",
    )

state = st.session_state.get("pipeline_state")
if state and state.get("_service_unavailable"):
    st.error(
        "🔌 The AI service is temporarily unavailable after repeated failures "
        "(circuit breaker open) — this protects you from a long hang on every "
        "click while it's down. It will retry automatically in under a "
        "minute; try again shortly."
    )

if state:
    if st.session_state.get("demo_mode"):
        st.caption("Showing a pre-recorded demo run — no live agents or WhatsApp calls.")
    st.markdown("")
    active_vendor = state.get(ACTIVE_VENDOR_KEY, {})
    has_negotiated = bool(state.get(TRANSCRIPT_KEY))

    if active_vendor.get("name"):
        st.markdown(
            f'<div style="text-align:center; margin-bottom:0.8rem;">'
            f'<span class="vs-badge vs-badge-filled">🤝 Negotiating with '
            f'{active_vendor["name"]} · {active_vendor.get("contact","")}</span></div>',
            unsafe_allow_html=True,
        )
    elif not has_negotiated:
        st.info(
            "Vendors verified and ranked. **Choose who to contact first** — "
            "if they can't meet your terms, the agent will move to the next best on its own."
        )

    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        st.markdown('<div class="vs-section">🛡️ Verified Vendors</div>', unsafe_allow_html=True)
        vendor_cards(parse_json(state.get("verified_vendors", "{}")),
                     selectable=not has_negotiated)
        with st.expander("Raw sourcing results"):
            render_json(parse_json(state.get("discovered_vendors", "[]")))

    with col_right:
        st.markdown('<div class="vs-section">💬 WhatsApp Negotiation</div>', unsafe_allow_html=True)
        if has_negotiated:
            chat_timeline(state)
        else:
            st.markdown(
                '<div class="vs-chatwrap" style="display:flex; align-items:center; '
                'justify-content:center; min-height:180px; text-align:center;">'
                '<div style="color:var(--ink-soft); font-size:0.9rem; max-width:260px;">'
                'No conversation yet.<br/>Pick a vendor to contact and the agent '
                'will open WhatsApp on your behalf.</div></div>',
                unsafe_allow_html=True,
            )

    blocked = state.get(GUARDRAIL_LOG_KEY, [])
    if blocked and not state.get("final_deal"):
        st.error(
            f"⛔ **Deal-Lock Guardrail** blocked {len(blocked)} autonomous "
            "finalization attempt(s). Nothing is binding until you decide below."
        )

    proposal = state.get("proposed_deal")
    if proposal and not state.get("final_deal"):
        st.markdown("")
        st.markdown(
            f"""
<div class="vs-invite">
  <h3>📋 Proposed Deal — your decision</h3>
  <b style="color:var(--espresso); font-size:1.05rem;">{proposal.get('vendor_name','?')}</b>
  &nbsp;—&nbsp; {proposal.get('item','?')}
  <div class="vs-terms">
    <div class="vs-term"><small>Quantity</small>{proposal.get('quantity','?')}</div>
    <div class="vs-term"><small>Unit price</small>₹{proposal.get('unit_price','?')}</div>
    <div class="vs-term"><small>Total</small>₹{proposal.get('total','?')}</div>
    <div class="vs-term"><small>Delivery</small>{proposal.get('delivery_timeline','?')}</div>
    <div class="vs-term"><small>Payment</small>{proposal.get('payment_terms','?')}</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown("")
        lock, reject = st.columns(2)
        if lock.button("🔒 Accept & Lock Deal", type="primary", use_container_width=True):
            trace_run(lambda cb: scout().approve_and_finalize(on_event=cb),
                      "Finalizing with vendor…")
            st.rerun()
        if reject.button("Reject", use_container_width=True):
            trace_run(lambda cb: scout().reject(on_event=cb), "Declining politely…")
            st.rerun()

    final = state.get("final_deal")
    if final:
        st.success("✅ Deal finalized with human approval.")

        vendor_name = final.get("vendor_name") or active_vendor.get("name", "—")
        contact = active_vendor.get("contact", "")
        if not contact:
            # fall back to whichever verified vendor matches the finalized name
            for v in (parse_json(state.get("verified_vendors", "{}")) or {}).get("ranked_vendors", []):
                if v.get("name") == vendor_name:
                    contact = v.get("contact", "") or ""
                    break

        wa_digits = "".join(c for c in str(contact) if c.isdigit())
        wa_link = (
            f'<a href="https://wa.me/{wa_digits}" target="_blank">Open WhatsApp chat →</a>'
            if wa_digits else ""
        )
        tel_link = f'<a href="tel:+{wa_digits}">+{wa_digits}</a>' if wa_digits else "—"

        def _money(v):
            try:
                return f"{float(v):,.0f}"
            except (TypeError, ValueError):
                return str(v)

        st.markdown(
            f"""
<div class="vs-receipt">
  <div class="vs-receipt-head">
    <div class="vs-receipt-title">Deal Confirmed</div>
    <div class="vs-receipt-sub">Agreed with <b>{vendor_name}</b> · approved by you</div>
  </div>

  <div class="vs-receipt-hero">
    <div class="vs-hero-item">{final.get('item','—')}</div>
    <div class="vs-hero-total">₹{_money(final.get('total','?'))}</div>
    <div class="vs-hero-calc">
      {final.get('quantity','?')} units × ₹{_money(final.get('unit_price','?'))} per unit
    </div>
  </div>

  <div class="vs-receipt-rows">
    <div class="vs-rrow"><span>Delivery</span><b>{final.get('delivery_timeline','—')}</b></div>
    <div class="vs-rrow"><span>Payment terms</span><b>{final.get('payment_terms','—')}</b></div>
    <div class="vs-rrow"><span>Vendor contact</span><b>{tel_link}</b></div>
  </div>

  <div class="vs-receipt-foot">
    {wa_link}
    <div class="vs-receipt-note">
      The agent sent the confirmation and stopped here. Payment and dispatch are
      arranged directly between you and the vendor.
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        with st.expander("Full deal record (raw)"):
            render_json(final)
