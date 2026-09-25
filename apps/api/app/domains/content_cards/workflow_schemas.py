"""API contracts for the V3 card detail and Bundle → Outline workflow (§5.1, §6)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from app.domains.ai.context import CardContextBundle
from app.domains.content_cards.outline import OutlineV3
from app.domains.content_cards.schemas import BoardCard
from pydantic import BaseModel, ConfigDict, Field


class BundleStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_ref: UUID
    content_hash: str
    built_at: datetime
    # False when the stored bundle no longer matches what the sources would give now.
    is_current: bool


class ClaimOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    text: str
    evidence: str
    row: str
    argument_id: UUID | None
    argument_name: str | None
    version: int
    approved: bool


class CardCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    status: Literal["pass", "fail", "not_applicable"]
    detail: str = ""


class CardActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_build_bundle: bool
    can_generate_outline: bool
    can_save_outline: bool


class CardDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: BoardCard
    outline: OutlineV3 | None
    # A stored outline that no longer parses is reported, not silently dropped.
    outline_unreadable: bool
    bundle: BundleStatus | None
    # The context the next bundle would contain, from current project data.
    context: CardContextBundle
    claim_options: list[ClaimOption]
    checks: list[CardCheck]
    actions: CardActions


class BundleBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)


class BundleBuildResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: BoardCard
    bundle: BundleStatus
    reused: bool


class OutlineGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str | None = Field(default=None, max_length=128)


class OutlineProposal(BaseModel):
    """A validated outline for the human to review; the card is not changed."""

    model_config = ConfigDict(extra="forbid")

    outline: OutlineV3
    job_run_id: UUID
    prompt_version: str
    provider: str
    model: str
    attempts: int
    bundle_ref: UUID


class OutlineSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outline: OutlineV3
    revision: int = Field(ge=1)


class OutlineSaveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card: BoardCard
    outline: OutlineV3
