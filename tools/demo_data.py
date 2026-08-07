"""Static end-to-end demo state.

A complete, frozen snapshot of a finished run — discovery, verification, a
live WhatsApp negotiation (including two language switches and two vendor
fallbacks), the guardrail block, and the approved deal. Loaded by the
"Clear filters & load demo" button so the full story can be shown without
depending on Gemini, Google Search, or WhatsApp being reachable.
"""
from __future__ import annotations

_T = 1_754_600_000.0  # fixed base timestamp so ordering is deterministic

DEMO_REQUIREMENT = (
    "Business: GAMLA (decorative pots & plants). "
    "Requirement: 400 x Glass and Steel Water Bottle. Budget: 150.0 INR per unit. "
    "Delivery timeline: 3 weeks. Ship to: Pune, India."
)

_DISCOVERED = [
    {
        "name": "Aditya Materials",
        "unit_price": 155.0, "currency": "INR", "moq": 250,
        "location": "Bengaluru, Karnataka", "contact": "919130039898",
        "evidence_summary": "GST registered, TrustSEAL verified, 8 years on IndiaMART, 4.7★ from 150 reviews, export history to UAE",
    },
    {
        "name": "Karnataka Craft Traders",
        "unit_price": 170.0, "currency": "INR", "moq": 400,
        "location": "Mysuru, Karnataka", "contact": "+91 99456 78123",
        "evidence_summary": "GST registered, 4.5★ from 112 reviews, 6 years in business",
    },
    {
        "name": "Deccan Steel & Glass",
        "unit_price": 149.0, "currency": "INR", "moq": 300,
        "location": "Hyderabad, Telangana", "contact": "+91 90000 77321",
        "evidence_summary": "GST registered, 4.2★ from 61 reviews, 5 years in business",
    },
    {
        "name": "ValueMart Exports",
        "unit_price": 58.0, "currency": "INR", "moq": 2000,
        "location": None, "contact": None,
        "evidence_summary": "Generic listing, no reviews, no verifiable address, price far below comparable suppliers",
    },
]

_VERIFIED = {
    "ranked_vendors": [
        {
            **_DISCOVERED[0], "trust_score": 92,
            "positives": ["GST registered", "TrustSEAL certification", "export history"],
            "red_flags": [],
        },
        {
            **_DISCOVERED[1], "trust_score": 78,
            "positives": ["GST registered", "strong customer reviews"],
            "red_flags": [],
        },
        {
            **_DISCOVERED[2], "trust_score": 74,
            "positives": ["GST registered", "customer reviews present"],
            "red_flags": [],
        },
    ]
}

_V1 = "Deccan Steel & Glass"
_V2 = "Karnataka Craft Traders"
_V3 = "Aditya Materials"

_TRANSCRIPT = [
    # --- Vendor 1: Deccan Steel & Glass (English) — fails on price + timeline
    {"direction": "outbound", "vendor": _V1, "ts": _T + 10, "body":
     "Hello! I'm an AI assistant reaching out on behalf of GAMLA, a decorative pots "
     "and plants business in Pune. We're sourcing 400 glass-and-steel water bottles "
     "for delivery within 3 weeks. Before we continue — would you prefer English, "
     "हिंदी, or ಕನ್ನಡ?"},
    {"direction": "inbound", "vendor": _V1, "ts": _T + 95, "body":
     "English is fine. For 400 pieces our rate is 168 INR per unit, delivery in 4 weeks."},
    {"direction": "outbound", "vendor": _V1, "ts": _T + 130, "body":
     "Thanks for the quick quote. Our budget is 150 INR per unit and we need delivery "
     "within 3 weeks. Could you work to 150 at this volume?"},
    {"direction": "inbound", "vendor": _V1, "ts": _T + 240, "body":
     "Sorry, 162 is our best for this quantity and 4 weeks is the earliest we can dispatch."},
    {"direction": "outbound", "vendor": _V1, "ts": _T + 265, "body":
     "Understood — that's outside what we can commit to right now. Thank you for your "
     "time, and we'll keep you in mind for future orders."},

    # --- Vendor 2: Karnataka Craft Traders (Kannada) — also fails
    {"direction": "outbound", "vendor": _V2, "ts": _T + 300, "body":
     "ನಮಸ್ಕಾರ! ನಾನು GAMLA ಪರವಾಗಿ ಮಾತನಾಡುತ್ತಿರುವ AI ಸಹಾಯಕ — GAMLA ಪುಣೆಯಲ್ಲಿ ಅಲಂಕಾರಿಕ "
     "ಕುಂಡಗಳು ಮತ್ತು ಗಿಡಗಳ ವ್ಯಾಪಾರ ನಡೆಸುತ್ತಿದೆ. ನಮಗೆ 3 ವಾರಗಳಲ್ಲಿ 400 ಗ್ಲಾಸ್ ಮತ್ತು ಸ್ಟೀಲ್ "
     "ವಾಟರ್ ಬಾಟಲಿಗಳು ಬೇಕಾಗಿವೆ. ದಯವಿಟ್ಟು ತಿಳಿಸಿ, ನೀವು English, ಹಿಂದಿ ಅಥವಾ ಕನ್ನಡದಲ್ಲಿ "
     "ಮಾತನಾಡಲು ಬಯಸುವಿರಾ?"},
    {"direction": "inbound", "vendor": _V2, "ts": _T + 370, "body":
     "ಕನ್ನಡ ಚೆನ್ನಾಗಿದೆ. 400 ಬಾಟಲಿಗಳಿಗೆ ನಮ್ಮ ದರ 170 ರೂಪಾಯಿ ಪ್ರತಿ ಯೂನಿಟ್, ಡೆಲಿವರಿ 4 "
     "ವಾರಗಳಲ್ಲಿ."},
    {"direction": "outbound", "vendor": _V2, "ts": _T + 400, "body":
     "ಧನ್ಯವಾದಗಳು. ನಮ್ಮ ಬಜೆಟ್ 150 ರೂಪಾಯಿ ಪ್ರತಿ ಯೂನಿಟ್ ಮತ್ತು ಡೆಲಿವರಿ 3 ವಾರಗಳಲ್ಲಿ ಬೇಕು. "
     "ದಯವಿಟ್ಟು 150ಕ್ಕೆ ಸಾಧ್ಯವೇ?"},
    {"direction": "inbound", "vendor": _V2, "ts": _T + 470, "body":
     "ಕ್ಷಮಿಸಿ, ಈ ಪ್ರಮಾಣಕ್ಕೆ 165 ರೂಪಾಯಿಗಿಂತ ಕಡಿಮೆ ಸಾಧ್ಯವಿಲ್ಲ, ಮತ್ತು ಡೆಲಿವರಿ 3 "
     "ವಾರಗಳಲ್ಲಿ ಆಗುವುದಿಲ್ಲ."},
    {"direction": "outbound", "vendor": _V2, "ts": _T + 495, "body":
     "ಅರ್ಥವಾಯಿತು — ಸದ್ಯಕ್ಕೆ ಇದು ನಮಗೆ ಸಾಧ್ಯವಿಲ್ಲ. ಸಮಯ ನೀಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು."},

    # --- Vendor 3: Aditya Materials (Hindi) — succeeds
    {"direction": "outbound", "vendor": _V3, "ts": _T + 530, "body":
     "नमस्ते! मैं GAMLA की ओर से एक AI सहायक हूँ — GAMLA पुणे में सजावटी गमले और "
     "पौधों का व्यवसाय है। हमें 3 सप्ताह में 400 ग्लास-एंड-स्टील वॉटर बोतल चाहिए। "
     "आप English, हिंदी या ಕನ್ನಡ में से किस भाषा में बात करना पसंद करेंगे?"},
    {"direction": "inbound", "vendor": _V3, "ts": _T + 610, "body":
     "हिंदी ठीक रहेगी। 400 पीस के लिए हमारा रेट 155 रुपये प्रति यूनिट है, डिलीवरी 3 हफ्ते में।"},
    {"direction": "outbound", "vendor": _V3, "ts": _T + 640, "body":
     "धन्यवाद! हमारा बजट 150 रुपये प्रति यूनिट है। क्या आप 400 यूनिट पर 145 रुपये कर सकते हैं? "
     "अगर हाँ, तो हम आज ही आगे बढ़ सकते हैं।"},
    {"direction": "inbound", "vendor": _V3, "ts": _T + 750, "body":
     "145 थोड़ा कम है। हम 140 रुपये प्रति यूनिट दे सकते हैं अगर 50% एडवांस हो — "
     "डिलीवरी 3 हफ्ते में पुणे तक, शिपिंग 3,000 रुपये अलग से।"},
    {"direction": "outbound", "vendor": _V3, "ts": _T + 790, "body":
     "बहुत बढ़िया — 140 रुपये प्रति यूनिट, 50% एडवांस और बाकी डिलीवरी पर, 3 हफ्ते में पुणे। "
     "मैं यह प्रस्ताव व्यवसाय के मालिक को भेज रहा हूँ। अंतिम पुष्टि उनकी मंज़ूरी के बाद ही होगी।"},
]

_SWITCH_LOG = [
    {
        "from": _V1, "to": _V2, "ts": _T + 285,
        "reason": "best offer 162 INR/unit vs 150 budget, and 4-week delivery misses the 3-week timeline",
    },
    {
        "from": _V2, "to": _V3, "ts": _T + 515,
        "reason": "best offer 165 INR/unit vs 150 budget, and 4-week delivery misses the 3-week timeline",
    },
]

_DEAL = {
    "vendor_name": _V3,
    "item": "Glass and Steel Water Bottle",
    "quantity": 400,
    "unit_price": 140.0,
    "currency": "INR",
    "total": 56000.0,
    "delivery_timeline": "3 weeks to Pune",
    "payment_terms": "50% advance, 50% on delivery. ₹3,000 shipping extra.",
}


def demo_state(finalized: bool = True) -> dict:
    """Frozen pipeline state for the canned demo."""
    state = {
        "discovered_vendors": _DISCOVERED,
        "verified_vendors": _VERIFIED,
        "whatsapp_transcript": list(_TRANSCRIPT),
        "vendor_switch_log": list(_SWITCH_LOG),
        "active_vendor": {"name": _V3, "contact": "919130039898"},
        "tried_vendor_names": [_V1, _V2, _V3],
        "proposed_deal": {**_DEAL, "status": "awaiting_human_approval"},
        "guardrail_blocked_attempts": [
            {"tool": "finalize_deal", "args": {"confirmation_message": "Confirming the order…"}}
        ],
        "negotiated_deal": {
            "vendor_name": _V3,
            "negotiation_language": "Hindi",
            "terms": {
                "quantity": 400, "unit_price": 140.0, "currency": "INR",
                "delivery_timeline": "3 weeks to Pune",
                "payment_terms": "50% advance, 50% on delivery. ₹3,000 shipping extra.",
            },
            "rounds": 2,
            "switched_vendor": True,
            "status": "finalized" if finalized else "awaiting_human_approval",
        },
    }
    if finalized:
        state["final_deal"] = {**_DEAL, "status": "finalized"}
        state["human_approved"] = True
        state["whatsapp_transcript"].append({
            "direction": "outbound", "vendor": _V3, "ts": _T + 900,
            "body": "पुष्टि हो गई! GAMLA की ओर से ऑर्डर कन्फर्म — 400 यूनिट @ 140 रुपये, "
                    "कुल 56,000 रुपये, 50% एडवांस, 3 हफ्ते में पुणे डिलीवरी। धन्यवाद!",
        })
    return state
