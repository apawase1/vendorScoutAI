# VendorScoutAI 🧭

**Autonomous sourcing agent for small business owners and artisans.**
Google AI Agent Builder Series 2026 — B2B Services track, Problem Statement #7 (Vendor Evaluation).

Give it a material requirement — item, quantity, budget, timeline — and VendorScoutAI finds vendors, verifies their trustworthiness, and negotiates over real WhatsApp on your behalf, in the vendor's own language. It will haggle autonomously. It will **never** commit your money without your explicit approval.

> **Autonomous negotiation is allowed. Autonomous financial commitment is not.**
> That single line is the design thesis, and it's enforced in code, not in a prompt.

**[Live static demo →](https://apawase1.github.io/vendorScoutAI/)** (no backend, no API keys — a scripted replay of a real run, honestly labeled as such)

---

## The problem

Small business owners and artisans have no procurement team. Finding material suppliers means hours across noisy B2B marketplaces full of inflated claims, ghost vendors, and suspiciously cheap listings — then haggling with each one individually, often in a language the business owner doesn't speak. Meanwhile, handing that job to an AI raises the obvious question: *what stops it from spending my money?*

VendorScoutAI answers both halves.

---

## Architecture

A 3-agent ADK pipeline, split into two human-gated stages so the owner stays in control at two separate checkpoints:

`discovered_vendors → verified_vendors → [owner picks a vendor] → negotiated_deal → [owner locks the deal]`

| Agent | Tools | Role |
|---|---|---|
| **Sourcing** | ADK built-in `google_search` *only* | Finds candidate vendors, extracts structured data from grounded search results |
| **Verification** | Custom function tools + Gemini reasoning | Scores trustworthiness, flags red flags, ranks the top 3 candidates |
| **Negotiation** | Custom tools + WhatsApp (Meta Cloud API) | Discloses itself as AI, asks the vendor's preferred language (English / Hindi / Kannada), negotiates entirely in that language, reports back to the owner in English, halts at finalization |

Discovery (Sourcing → Verification) runs automatically and stops. The owner picks which ranked vendor to contact first from the UI. Negotiation then runs against that vendor — if it can't meet the budget or timeline, the agent automatically tries the next best-ranked vendor on its own, and reports every switch in the transcript.

### 🔒 The Deal-Lock Guardrail

`tools/security.py` — a standalone ADK `before_tool_callback`, deliberately built as a **visible, separate layer** rather than logic buried inside the Negotiation Agent.

It rejects any tool representing a binding commitment — `finalize_deal`, `confirm_order`, `send_payment`, `sign_contract` — unless `human_approved is True`, set only by the owner clicking **Accept & Lock Deal** in the UI.

Design details that matter:

- **Enforced by the runtime, not the prompt.** The model cannot talk its way past it; ADK invokes the callback before any tool executes.
- **Strict identity check.** `is True`, not truthiness — a stray `"yes"` string won't unlock it.
- **Messaging stays free.** Negotiation messages are never blocked. Only commitment is.
- **Every blocked attempt is logged** to session state and surfaced in the UI.

Covered by unit tests in `tests/test_security.py` that need no API key.

---

## Quickstart

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your GOOGLE_API_KEY
streamlit run app.py
```

Requires **Python 3.11+** (google-adk 2.4.0 needs ≥3.10).

Click **Load demo** in the sidebar for a complete, pre-recorded run — three vendors, a failed English negotiation, a failed Kannada negotiation, a successful Hindi negotiation, a guardrail block, and a finalized deal — with no API key or network access required.

### Going live

| Capability | Flag | Extra setup |
|---|---|---|
| Real Google Search grounding | `VENDORSCOUT_STUB=0` | none — a priority vendor is still injected into results so live demos have a guaranteed, reachable outcome |
| Real WhatsApp messaging | `VENDORSCOUT_WHATSAPP_STUB=0` | Meta WhatsApp Cloud API (below) |

**Meta WhatsApp Cloud API:** create a Meta app with the WhatsApp product, grab a temporary or permanent access token and phone number ID from *API Setup*, and set `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, and `VENDOR_WHATSAPP_TO` in `.env`. Inbound replies arrive only via webhook (Meta has no polling endpoint) — run `python webhook_server.py` behind a tunnel (e.g. `ngrok http 8000`) and register `https://<tunnel>/webhook` with your chosen `META_VERIFY_TOKEN` under *Configuration → Webhooks*, subscribed to the `messages` field.

---

## Multilingual negotiation

The Negotiation Agent's first message to any vendor always discloses that it's an AI and asks whether the vendor prefers English, Hindi, or Kannada. Once the vendor answers, the rest of that conversation continues entirely in the chosen language — price counters, delivery terms, everything. The final deal summary shown to the business owner is always translated back to English, since the owner only reads English.

---

## Demo scoping — stated honestly

Vendor-side WhatsApp runs through the **Meta WhatsApp Cloud API with a consenting test number**, not real unknown vendors — production use requires Meta business verification that wasn't feasible before the finale.

The hosted [static demo](https://apawase1.github.io/vendorScoutAI/) (`docs/index.html`) is a dependency-free, scripted replay of a real run, built so judges can see the full experience — including the guardrail block — without any backend, API key, or WhatsApp account. It's labeled as a static build in the UI itself.

We'd rather say this plainly than imply production scale.

---

## Tests

```bash
pytest tests/test_security.py       # guardrail unit tests — no API key needed
pytest tests/test_pipeline_stub.py  # full pipeline end-to-end — needs GOOGLE_API_KEY
```

---

## Project structure

```
agents.py                 # 3 agents + pipeline + guardrail wiring + VendorScout orchestrator
app.py                    # Streamlit dashboard: requirement form, live trace, vendor choice,
                           # chat timeline, Lock/Reject UI, receipt card
webhook_server.py         # Flask webhook receiver for inbound Meta WhatsApp messages
tools/
  sourcing_tools.py       # stub vendor data + demo priority-vendor constants
  verification_tools.py   # deterministic trust heuristics
  negotiation_tools.py    # WhatsApp send/receive, vendor targeting + fallback, deal proposal
  whatsapp_provider.py    # Meta WhatsApp Cloud API transport, circuit-breaker wrapped
  inbox_store.py          # shared WhatsApp inbox — Redis in prod, local file for dev
  circuit_breaker.py      # small breaker used around Meta + Gemini/ADK calls
  security.py             # ⭐ deal-lock guardrail callback
  demo_data.py            # frozen full-pipeline state for the "Load demo" button
docs/
  index.html              # static, dependency-free replica for GitHub Pages hosting
ops/alerts/                # Cloud Monitoring alert policies (error rate, latency, saturation, circuit breaker)
.github/workflows/         # ci.yml (test+build) and deploy.yml (Cloud Run deploy)
Dockerfile, docker-compose.yml, gunicorn.conf.py, entrypoint.sh
tests/
architecture-diagram.md   # full Mermaid diagram + design iteration history
PRD.md
DEMO_SCRIPT.md            # demo runbook + judge Q&A
DEPLOY.md                 # production deployment runbook — Docker, CI/CD, Cloud Run, alerting
```

## Production deployment

See **[DEPLOY.md](DEPLOY.md)** for the full runbook: Docker image, GitHub
Actions CI/CD to Cloud Run, externalized config via Secret Manager, graceful
shutdown, circuit breakers on Gemini/ADK and Meta's API, and symptom-based
alerting (error rate, latency, saturation, circuit-breaker trips).

---

## Tech stack

Python 3.11 · Google ADK 2.4.0 (`SequentialAgent`) · Gemini · Meta WhatsApp Cloud API · Flask (webhook) · Streamlit · ADK `InMemorySessionService` (no external DB)
