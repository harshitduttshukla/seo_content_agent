"""Deterministic search intent classification, funnel stage mapping, and scoring formulas."""

import math
import re
from typing import NamedTuple

from app.domains.keywords.models import FunnelStage, SearchIntent


class IntentClassificationResult(NamedTuple):
    intent: SearchIntent
    confidence: float
    funnel_stage: FunnelStage
    reason: str


# Deterministic signals
TRANSACTIONAL_SIGNALS = {
    "buy",
    "purchase",
    "order",
    "coupon",
    "discount",
    "deal",
    "pricing",
    "cheap",
    "sale",
    "quote",
    "subscription",
    "hire",
    "shop",
    "checkout",
    "software license",
    "for sale",
}

COMMERCIAL_SIGNALS = {
    "best",
    "top",
    "review",
    "reviews",
    "comparison",
    "vs",
    "versus",
    "alternative",
    "alternatives",
    "recommended",
    "tools",
    "platforms",
    "solutions",
    "agency",
    "agencies",
    "services",
    "cost of",
    "vendors",
}

NAVIGATIONAL_SIGNALS = {
    "login",
    "log in",
    "signin",
    "sign in",
    "portal",
    "website",
    "official",
    "dashboard",
    "support",
    "contact us",
    "documentation",
    "app download",
}

LOCAL_SIGNALS = {
    "near me",
    "in london",
    "in new york",
    "in usa",
    "in uk",
    "nearby",
    "san francisco",
    "austin",
    "toronto",
    "location",
    "address",
    "phone number",
}

INFORMATIONAL_SIGNALS = {
    "how",
    "what",
    "why",
    "when",
    "where",
    "who",
    "which",
    "guide",
    "tutorial",
    "example",
    "examples",
    "tips",
    "ideas",
    "checklist",
    "definition",
    "meaning",
    "template",
    "learn",
    "basics",
    "strategy",
    "audit",
    "explained",
    "process",
    "framework",
}


def classify_intent_and_funnel(keyword: str) -> IntentClassificationResult:
    """Deterministic intent and funnel classifier based on lexical signals."""
    kw_lower = keyword.strip().lower()
    words = set(re.findall(r"\b\w+\b", kw_lower))

    # 1. Navigational signals
    for signal in NAVIGATIONAL_SIGNALS:
        if signal in kw_lower or (signal in words):
            return IntentClassificationResult(
                intent=SearchIntent.NAVIGATIONAL,
                confidence=0.92,
                funnel_stage=FunnelStage.BOFU,
                reason=f"Matched navigational keyword signal: '{signal}'",
            )

    # 2. Local signals
    for signal in LOCAL_SIGNALS:
        if signal in kw_lower:
            return IntentClassificationResult(
                intent=SearchIntent.LOCAL,
                confidence=0.90,
                funnel_stage=FunnelStage.BOFU,
                reason=f"Matched local keyword modifier: '{signal}'",
            )

    # 3. Transactional signals
    for signal in TRANSACTIONAL_SIGNALS:
        if signal in kw_lower or (signal in words):
            return IntentClassificationResult(
                intent=SearchIntent.TRANSACTIONAL,
                confidence=0.95,
                funnel_stage=FunnelStage.BOFU,
                reason=f"Matched transactional commercial purchase trigger: '{signal}'",
            )

    # 4. Commercial signals
    for signal in COMMERCIAL_SIGNALS:
        if signal in kw_lower or (signal in words):
            return IntentClassificationResult(
                intent=SearchIntent.COMMERCIAL,
                confidence=0.88,
                funnel_stage=FunnelStage.MOFU,
                reason=f"Matched commercial evaluation trigger: '{signal}'",
            )

    # 5. Informational signals
    for signal in INFORMATIONAL_SIGNALS:
        if signal in kw_lower or (signal in words):
            return IntentClassificationResult(
                intent=SearchIntent.INFORMATIONAL,
                confidence=0.85,
                funnel_stage=FunnelStage.TOFU,
                reason=f"Matched informational question/guide pattern: '{signal}'",
            )

    # 6. Default fallback
    return IntentClassificationResult(
        intent=SearchIntent.INFORMATIONAL,
        confidence=0.60,
        funnel_stage=FunnelStage.TOFU,
        reason="No specific modifier matched; categorized as informational query",
    )


def calculate_business_value(
    intent: SearchIntent | str,
    cpc: float = 0.0,
    keyword: str = "",
    strategy_terms: list[str] | None = None,
) -> float:
    """Calculate an explainable Business Value Score (0 - 100)."""
    intent_str = str(intent).upper()
    base_scores = {
        SearchIntent.TRANSACTIONAL: 90.0,
        SearchIntent.COMMERCIAL: 75.0,
        SearchIntent.LOCAL: 70.0,
        SearchIntent.INFORMATIONAL: 40.0,
        SearchIntent.NAVIGATIONAL: 20.0,
        SearchIntent.UNKNOWN: 30.0,
    }
    resolved_intent = (
        SearchIntent(intent_str) if intent_str in SearchIntent.__members__ else SearchIntent.UNKNOWN
    )
    score = base_scores.get(resolved_intent, 35.0)

    # Strategic match
    if strategy_terms:
        kw_lower = keyword.lower()
        matched = any(term.lower() in kw_lower for term in strategy_terms if term)
        if matched:
            score += 15.0

    # CPC value indicator
    if cpc > 0:
        cpc_bonus = min(10.0, math.log10(cpc + 1.0) * 8.0)
        score += cpc_bonus

    return min(100.0, round(score, 1))


def calculate_priority_score(
    search_volume: int,
    keyword_difficulty: float,
    business_value_score: float,
    intent: SearchIntent | str,
) -> float:
    """Calculate an explainable Keyword Priority Score (0 - 100)."""
    if search_volume > 0:
        norm_volume = min(100.0, (math.log10(max(10, search_volume)) / 5.0) * 100.0)
    else:
        norm_volume = 10.0

    opportunity = max(0.0, min(100.0, 100.0 - keyword_difficulty))
    bv = max(0.0, min(100.0, business_value_score))

    intent_weights = {
        SearchIntent.TRANSACTIONAL: 100.0,
        SearchIntent.COMMERCIAL: 85.0,
        SearchIntent.LOCAL: 80.0,
        SearchIntent.INFORMATIONAL: 50.0,
        SearchIntent.NAVIGATIONAL: 30.0,
        SearchIntent.UNKNOWN: 40.0,
    }
    intent_str = str(intent).upper()
    resolved_intent = (
        SearchIntent(intent_str) if intent_str in SearchIntent.__members__ else SearchIntent.UNKNOWN
    )
    intent_val = intent_weights.get(resolved_intent, 50.0)

    priority = (norm_volume * 0.30) + (opportunity * 0.25) + (bv * 0.35) + (intent_val * 0.10)
    return round(max(0.0, min(100.0, priority)), 1)
