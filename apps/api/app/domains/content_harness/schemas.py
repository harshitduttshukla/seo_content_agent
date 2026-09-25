"""Pydantic schemas for the Content Harness domain."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrandRequirements(BaseModel):
    tone: str | None = None
    voice: str | None = None
    style: str | None = None
    words_to_avoid: list[str] = Field(default_factory=list)
    formatting_rules: list[str] = Field(default_factory=list)


class InternalLinkTarget(BaseModel):
    url: str
    target_page_id: UUID | None = None
    anchor_suggestion: str | None = None
    reason: str | None = None
    priority: int = 1


class FindingImpact(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


class HarnessSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    heading: str
    level: int = 2
    content: str


class HarnessGeneratedContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    meta_description: str = ""
    content: str = ""
    sections: list[HarnessSection] = Field(default_factory=list)
    used_keywords: list[str] = Field(default_factory=list)
    internal_links: list[dict[str, str]] = Field(default_factory=list)
    word_count: int = 0


class ContentHarnessInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project_id: UUID
    name: str = "Content Harness Run"
    content_brief_id: UUID | None = None
    document_id: UUID | None = None
    primary_keyword: str = ""
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = "INFORMATIONAL"
    target_audience: str = ""
    target_word_count: int = Field(default=1500, ge=100, le=50000)
    required_topics: list[str] = Field(default_factory=list)
    required_questions: list[str] = Field(default_factory=list)
    brand_rules: BrandRequirements = Field(default_factory=BrandRequirements)
    internal_link_targets: list[InternalLinkTarget] = Field(default_factory=list)
    website_context: str = ""
    prompt_version: str = "v1"
    custom_system_prompt: str | None = None
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    run_ai_evaluator: bool = False


class HarnessFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str  # SEO, CONTENT, BRAND, INTERNAL_LINKING, TECHNICAL
    rule: str
    status: FindingStatus
    impact: FindingImpact
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class HarnessScorecard(BaseModel):
    model_config = ConfigDict(extra="ignore")

    seo_score: float = Field(ge=0.0, le=100.0)
    content_score: float = Field(ge=0.0, le=100.0)
    brand_score: float = Field(ge=0.0, le=100.0)
    linking_score: float = Field(ge=0.0, le=100.0)
    technical_validity: str  # PASS / FAIL
    overall_score: float = Field(ge=0.0, le=100.0)
    status: str  # PASS / NEEDS IMPROVEMENT
    findings: list[HarnessFinding] = Field(default_factory=list)
    summary: str = ""
    ai_evaluation: dict[str, object] | None = None


class ContentHarnessRunDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    organization_id: UUID
    project_id: UUID
    created_by_id: UUID | None = None
    name: str
    status: str = "COMPLETED"
    prompt_version: str
    model: str
    provider: str
    input_data: dict[str, object]
    context_data: dict[str, object]
    prompt_data: dict[str, object]
    output_data: dict[str, object]
    evaluation_data: dict[str, object]
    score: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ContentHarnessRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str
    status: str = "COMPLETED"
    prompt_version: str
    model: str
    provider: str
    score: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class ContentHarnessComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    run_id_a: UUID
    run_id_b: UUID


class ContentHarnessComparison(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_a: ContentHarnessRunDetail
    run_b: ContentHarnessRunDetail
    score_diffs: dict[str, float]
    improvements: list[str]
    regressions: list[str]
    summary: str


class EvaluateContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    input_data: ContentHarnessInput
    content: HarnessGeneratedContent


# V3 outline mode (prompt v3.outline.v1): the same generation contract as the
# Content Hub, run against a real ContentCard's bundle.


class V3OutlineHarnessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    card_id: UUID
    name: str = Field(default="V3 outline run", max_length=200)
    model: str | None = Field(default=None, max_length=128)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class V3OutlineEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=100.0)
    status: str  # PASS / NEEDS IMPROVEMENT
    findings: list[HarnessFinding] = Field(default_factory=list)


class V3DraftHarnessInput(BaseModel):
    """Run the production draft contract on a card that has a saved outline."""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    card_id: UUID
    name: str = Field(default="V3 draft run", max_length=200)
    model: str | None = Field(default=None, max_length=128)
    temperature: float = Field(default=0.5, ge=0.0, le=2.0)


# Same scorecard shape as the outline evaluation (score, status, findings).
V3DraftEvaluation = V3OutlineEvaluation


class V3ProductionHarnessInput(BaseModel):
    """Run production QA, repair or section regeneration on a drafted card."""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    card_id: UUID
    mode: Literal["qa", "repair", "section"]
    section_id: str | None = Field(default=None, max_length=64)
    feedback: str | None = Field(default=None, max_length=4000)
    name: str = Field(default="V3 production run", max_length=200)
    model: str | None = Field(default=None, max_length=128)
