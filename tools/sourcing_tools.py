"""Sourcing support data.

The Sourcing Agent itself uses ONLY the ADK built-in `google_search` tool
(no custom tools mixed in, per ADK's tool-mixing constraint), so this module
holds stub data and helpers used outside the agent's toolset.
"""
from __future__ import annotations

import os

# The demo vendor's WhatsApp contact — a real, consenting number standing in
# for the vendor persona (see architecture's demo-scoping note). No default:
# every deployment sets its own via env, so no one's personal phone number
# ships baked into the image or the source tree.
DEMO_VENDOR_CONTACT = os.getenv("DEMO_PRIORITY_VENDOR_CONTACT", "+919130039898")
DEMO_VENDOR_NAME = os.getenv("DEMO_PRIORITY_VENDOR_NAME", "Aditya Materials")

STUB_VENDORS = [
    {
        "name": DEMO_VENDOR_NAME,
        "unit_price": 178.0,
        "currency": "INR",
        "moq": 250,
        "location": "Bengaluru, Karnataka",
        "contact": DEMO_VENDOR_CONTACT,
        "evidence_summary": "GST registered, TrustSEAL verified, 8 years on IndiaMART, 4.7★ from 150 reviews, export history to UAE",
    },
    {
        "name": "Kavya Cotton Works",
        "unit_price": 168.0,
        "currency": "INR",
        "moq": 500,
        "location": "Erode, Tamil Nadu",
        "contact": "+91 98430 22222",
        "evidence_summary": "GST registered, export history to UAE, 4.6★ from 89 reviews",
    },
    {
        "name": "QuickDeal Trading Co",
        "unit_price": 62.0,
        "currency": "INR",
        "moq": 1000,
        "location": None,
        "contact": None,
        "evidence_summary": "Generic listing, no reviews, price far below comparable suppliers",
    },
    {
        "name": "Pune Bag House",
        "unit_price": 175.0,
        "currency": "INR",
        "moq": 300,
        "location": "Pune, Maharashtra",
        "contact": "punebaghouse@gmail.com",
        "evidence_summary": "Local supplier, 4.1★ from 45 reviews, 6 years in business",
    },
]

# Scripted replies for the fallback path when the real demo vendor can't meet
# budget/timeline and the Negotiation Agent calls try_next_vendor. Written to
# resolve within a typical budget so the "found another vendor" branch has a
# satisfying live-demo payoff. Keyed by vendor name from STUB_VENDORS above.
MOCK_REPLIES = {
    "Kavya Cotton Works": [
        "Namaste! Yes, we can supply — for your quantity our rate is 165 INR per unit, delivery in 3 weeks.",
        "We can offer 158 INR per unit if you confirm today, delivery in 2.5 weeks, 20% advance payment.",
    ],
    "Pune Bag House": [
        "Hello ji, for this order we quote 172 INR per unit, delivery in 3 weeks.",
        "We can do 160 INR per unit with confirmation this week, delivery in 2 weeks, 25% advance.",
    ],
}
