"""Typed context assembly contracts; retrieval is implemented in a later phase."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContextKind(StrEnum):
    STRATEGY = "strategy"
    BRAND = "brand"
    SEO_RULES = "seo_rules"
    KEYWORDS = "keywords"
    CONTENT_MAP = "content_map"
    CONTENT_BRIEF = "content_brief"
    LINKING_RULES = "linking_rules"
    KNOWLEDGE = "knowledge"
    CURRENT_DOCUMENT = "current_document"
    SELECTED_TEXT = "selected_text"
    PREVIOUS_VERSION = "previous_version"


class ContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    project_id: UUID
    user_id: UUID
    purpose: str
    allowed_kinds: set[ContextKind]
    max_input_tokens: int = Field(default=12_000, ge=256, le=200_000)


class ContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ContextKind
    source_id: UUID
    version_id: UUID | None = None
    text: str
    relevance_score: float = Field(ge=0, le=1)
    token_count: int = Field(ge=0)
    content_hash: str


class AssembledContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ContextItem]
    total_tokens: int = Field(ge=0)
    truncated: bool
