"""V3 Demand domain Pydantic v2 schemas.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §4.5, §4.7
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DemandNodeType(StrEnum):
    """V3 §3.1: A demand node is either a keyword or a prompt."""

    KEYWORD = "keyword"
    PROMPT = "prompt"


class DemandNodeStatus(StrEnum):
    """V3 §4.5: Status in the review pipeline."""

    PENDING = "pending"
    KEPT = "kept"
    DISCARDED = "discarded"


class DemandNodeOrigin(StrEnum):
    """V3 §3.1: How a demand node was created."""

    UPLOAD = "upload"
    GSC_STRIKING_DISTANCE = "gsc_striking_distance"
    INSIGHT = "insight"


class DemandNodeFunnel(StrEnum):
    """V3 §4.5: Funnel stages (lowercase per V3 convention)."""

    TOFU = "tofu"
    MOFU = "mofu"
    BOFU = "bofu"


class KeywordScoreBreakdown(BaseModel):
    """V3 §4.5: Keyword scoring breakdown.

    Score = w_v × norm(volume) + w_g × competitor_gap + w_f × funnel_weight[funnel]
    """

    volume_component: float = Field(default=0.0, ge=0.0)
    gap_component: float = Field(default=0.0, ge=0.0)
    funnel_component: float = Field(default=0.0, ge=0.0)


class PromptScoreBreakdown(BaseModel):
    """V3 §4.7: Prompt scoring breakdown.

    Score = citation_gap × platforms
    """

    citation_gap: float = Field(default=0.0, ge=0.0, le=1.0)
    platform_count: int = Field(default=0, ge=0)
