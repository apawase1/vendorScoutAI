"""Verification Agent function tools — deterministic trust heuristics.

No web scraping: reasons only over the Sourcing Agent's search-grounded
output, with Gemini handling the qualitative judgment.
"""
from __future__ import annotations

from typing import Any, Optional

_EVIDENCE_SIGNALS = {
    "gst": "GST registered",
    "year": "established operating history",
    "review": "customer reviews present",
    "★": "rated by buyers",
    "export": "export history",
    "verified": "marketplace-verified",
    "trustseal": "TrustSEAL certification",
}


def assess_vendor(
    name: str,
    unit_price: float,
    market_median_price: float,
    moq: int,
    location: Optional[str],
    contact: Optional[str],
    evidence_summary: Optional[str],
) -> dict[str, Any]:
    """Score a vendor's trustworthiness (0-100) and flag red flags.

    Args:
        name: Vendor business name.
        unit_price: Quoted price per unit.
        market_median_price: Median unit price across all discovered vendors.
        moq: Minimum order quantity.
        location: Physical location, or None if not listed.
        contact: Phone/email, or None if not listed.
        evidence_summary: Trust evidence extracted from search results.
    """
    score = 50
    red_flags: list[str] = []
    positives: list[str] = []

    if market_median_price > 0 and unit_price < 0.5 * market_median_price:
        score -= 25
        red_flags.append("price suspiciously far below market median")

    if contact:
        score += 10
        positives.append("direct contact available")
    else:
        score -= 15
        red_flags.append("no direct contact information")

    if location:
        score += 5
        positives.append("physical location disclosed")
    else:
        score -= 10
        red_flags.append("no physical location listed")

    evidence = (evidence_summary or "").lower()
    if not evidence or "generic" in evidence or "no reviews" in evidence:
        score -= 10
        red_flags.append("weak or generic online footprint")
    for keyword, label in _EVIDENCE_SIGNALS.items():
        if keyword in evidence:
            score += 7
            positives.append(label)

    if moq > 0 and moq >= 1000:
        red_flags.append("high minimum order quantity")

    return {
        "name": name,
        "trust_score": max(0, min(100, score)),
        "red_flags": red_flags,
        "positives": positives,
    }
