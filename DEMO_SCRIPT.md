# VendorScoutAI — Demo Runbook & Video Script

## Pre-flight (do this 15 min before recording)

```bash
cd ~/Documents/Projects/vendorscoutAI
source .venv/bin/activate
pytest tests/test_security.py -q          # must be 5 passed
pytest tests/test_pipeline_stub.py -q     # must pass before anything else
```

**Twilio Sandbox opt-in expires after 24h of inactivity.** Re-send the join
phrase from the vendor phone to `+14155238886` right before recording, every
time. This is the #1 cause of a dead demo.

### Two run modes — know which you're in

| Mode | `.env` setting | Use when |
|---|---|---|
| **Live WhatsApp** | `VENDORSCOUT_WHATSAPP_STUB=0` | Main demo — real messages to your phone |
| **Offline safe** | `VENDORSCOUT_WHATSAPP_STUB=1` | Backup if Twilio/wifi fails on the day |

The offline mode runs the identical agent chain and guardrail with scripted
vendor replies. **Record a backup video in this mode first** — it costs 3
minutes and guarantees you have something to submit.

---

## Video script (target: 3-4 minutes)

### 0:00 — Problem (20s)
> "Small business owners and artisans lose hours sourcing materials — finding
> suppliers, checking if they're trustworthy, and haggling over price.
> VendorScoutAI does all three autonomously, but never commits their money
> without permission."

Show the dashboard landing screen.

### 0:20 — Enter the requirement (20s)
Sidebar: business name **GAMLA**, decorative pots & plants. Item, quantity
500, budget ₹170/unit, timeline 3 weeks, ship to Pune. Click **Start Sourcing**.

> "Three agents run in sequence on Google's ADK."

### 0:40 — Agent 1 & 2, live trace (40s)
Let the live trace expand. Point at it as it streams.

> "The Sourcing Agent uses ADK's built-in Google Search tool to find candidate
> vendors and pull out structured data. The Verification Agent then scores each
> one for trustworthiness — it flags this vendor" *(point at the red-flagged
> one)* "because the price is far below market and there's no online footprint.
> Classic scam signature. It gets ranked last."

### 1:20 — Live WhatsApp negotiation (60s) ← **the money shot**
Show the Streamlit chat panel and your phone side by side.

> "Now the Negotiation Agent opens a real WhatsApp conversation with the
> top-ranked vendor."

**Show the phone.** First message must visibly say it's an AI acting for GAMLA.

> "Notice it discloses itself as an AI up front — that's non-negotiable in our
> design."

Reply from your phone with a price **above** budget, e.g.
*"We can do 195 INR per unit, delivery in 4 weeks."*

Let the agent counter. Reply once more, then either settle near budget or hold
firm to trigger the vendor-switch path.

### 2:20 — The guardrail (45s) ← **the point of the whole project**
Scroll to the blocked-attempt banner.

> "Here's the core of the design. The agent tried to finalize the deal — and
> our Deal-Lock Guardrail blocked it. Autonomous *negotiation* is allowed.
> Autonomous *financial commitment* is not. This is an ADK before-tool
> callback sitting outside the agent, so the agent cannot route around it,
> and every blocked attempt is logged."

Show `tools/security.py` on screen for 3 seconds — it's short and readable.

### 3:05 — Human approval (30s)
> "The owner reviews the proposed terms and decides."

Click **Accept & Lock Deal**. Show the confirmation arriving on the phone.

> "Only now — after an explicit human decision — does the binding message go out."

### 3:35 — Close (15s)
> "Autonomous where it saves time. Human-controlled where it costs money."

---

## Judge Q&A — have these ready

**"Is this real WhatsApp?"**
Yes, via Twilio's WhatsApp Sandbox to a consenting test number, not real
unknown vendors. Meta's production API needs multi-week business verification.
We state this openly rather than implying production scale.

**"Why is search stubbed?"**
Live `google_search` grounding is implemented and switchable with one env flag
(`VENDORSCOUT_STUB=0`). We pin stubbed vendor data for demo reproducibility so
the guardrail moment lands identically every run. Offer to flip it live.

**"Could the agent bypass the guardrail?"**
No. It's a `before_tool_callback` registered on the agent, enforced by the ADK
runtime before any tool executes — not a prompt instruction the model could
ignore. The blocklist covers payment, order confirmation, and contract signing.
It requires `human_approved is True` exactly, so a truthy value can't sneak past.

**"What if the top vendor won't meet budget?"**
The agent calls `try_next_vendor` and negotiates with the next-ranked
candidate. Shown in the UI as an inline switch banner.

**"Where's the state stored?"**
ADK in-process session state only — no external DB. Data flows via `output_key`:
`discovered_vendors → verified_vendors → negotiated_deal`.

---

## If something breaks mid-demo

| Symptom | Fix |
|---|---|
| No WhatsApp arrives | Sandbox opt-in expired — re-send join phrase |
| Agent hangs on reply | `REPLY_TIMEOUT_SECONDS=120`; just reply faster, or narrate the wait |
| Model error | Swap `GEMINI_MODEL` in `.env`, restart Streamlit |
| Anything else | Switch to `VENDORSCOUT_WHATSAPP_STUB=1` and continue — same flow, scripted replies |

**Always fully restart Streamlit (Ctrl+C) after editing `.env` or any `tools/` file.**
Streamlit does not reload already-imported modules.
