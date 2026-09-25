"""V3 structured outline contract (handoff §6.2) and its reference validation.

One schema and one validator, shared by generation (production and Harness)
and by the human save path. The outline refers to claims, demand and pages by
id only; text lives on those rows, never copied here as a source of truth.
"""

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from app.domains.ai.context import CardContextBundle
from pydantic import BaseModel, ConfigDict, Field, model_validator

V3_OUTLINE_SCHEMA_VERSION: Literal["v3.outline.v1"] = "v3.outline.v1"
DIRECT_ANSWER_MAX_WORDS = 60


def word_count(text: str) -> int:
    return len(text.split())


class PlannedInternalLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: UUID
    url: str = Field(min_length=1, max_length=2048)
    anchor_text: str = Field(default="", max_length=200)


class OutlineSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(min_length=1, max_length=64)
    order: int = Field(ge=1)
    heading: str = Field(min_length=1, max_length=300)
    purpose: str = Field(default="", max_length=1000)
    claim_ids: list[UUID] = Field(default_factory=list, max_length=20)
    target_demand_id: UUID | None = None
    planned_internal_links: list[PlannedInternalLink] = Field(default_factory=list, max_length=10)
    # GEO: the one sentence an answer engine could lift and cite.
    citable_statement: str | None = Field(default=None, max_length=600)
    notes: str = Field(default="", max_length=2000)
    # A company/product/client/competitor assertion with no approved claim yet.
    needs_claim: list[str] = Field(default_factory=list, max_length=10)


class OutlineV3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v3.outline.v1"] = V3_OUTLINE_SCHEMA_VERSION
    primary_mode: Literal["keyword", "prompt"]
    title: str = Field(min_length=1, max_length=300)
    # Prompt-primary only: the prompt targeted and the ≤60-word direct answer.
    prompt_target_id: UUID | None = None
    direct_answer: str | None = Field(default=None, max_length=800)
    sections: list[OutlineSection] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def _structure(self) -> "OutlineV3":
        ids = [section.section_id for section in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("section_id values must be unique")
        if [section.order for section in self.sections] != list(range(1, len(ids) + 1)):
            raise ValueError("section order must run 1..n in list order")
        if self.primary_mode == "prompt":
            if self.prompt_target_id is None:
                raise ValueError("prompt-primary outlines need prompt_target_id")
            if not self.direct_answer or not self.direct_answer.strip():
                raise ValueError("prompt-primary outlines need a direct_answer")
            if word_count(self.direct_answer) > DIRECT_ANSWER_MAX_WORDS:
                raise ValueError(f"direct_answer must be at most {DIRECT_ANSWER_MAX_WORDS} words")
        return self


@dataclass(frozen=True, slots=True)
class ReferenceSet:
    """The ids and URLs an outline may point at."""

    claim_ids: frozenset[UUID]
    demand_ids: frozenset[UUID]
    prompt_ids: frozenset[UUID]
    pages: dict[UUID, str] = field(default_factory=dict)  # page_id → stored url

    @classmethod
    def from_bundle(cls, bundle: CardContextBundle) -> "ReferenceSet":
        return cls(
            claim_ids=frozenset(claim.id for claim in bundle.claims),
            demand_ids=frozenset(item.id for item in bundle.demand),
            prompt_ids=frozenset(item.id for item in bundle.demand if item.type == "prompt"),
            pages={
                page.page_id: page.url
                for page in bundle.references.existing_pages.pages
                if page.page_id is not None
            },
        )


class OutlineIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str  # UNKNOWN_CLAIM, UNKNOWN_DEMAND, UNKNOWN_PAGE, URL_MISMATCH, ...
    message: str
    section_id: str | None = None
    ref: str | None = None


def validate_references(outline: OutlineV3, refs: ReferenceSet) -> list[OutlineIssue]:
    """Every id must resolve and every URL must be the stored URL of its page."""
    issues: list[OutlineIssue] = []
    if outline.primary_mode == "prompt" and outline.prompt_target_id not in refs.prompt_ids:
        issues.append(
            OutlineIssue(
                code="UNKNOWN_PROMPT",
                message="prompt_target_id is not one of this card's prompts",
                ref=str(outline.prompt_target_id),
            )
        )
    for section in outline.sections:
        for claim_id in section.claim_ids:
            if claim_id not in refs.claim_ids:
                issues.append(
                    OutlineIssue(
                        code="UNKNOWN_CLAIM",
                        message="claim is not an approved, current claim available to this card",
                        section_id=section.section_id,
                        ref=str(claim_id),
                    )
                )
        if section.target_demand_id is not None and section.target_demand_id not in refs.demand_ids:
            issues.append(
                OutlineIssue(
                    code="UNKNOWN_DEMAND",
                    message="target_demand_id is not demand attached to this card",
                    section_id=section.section_id,
                    ref=str(section.target_demand_id),
                )
            )
        for link in section.planned_internal_links:
            stored = refs.pages.get(link.page_id)
            if stored is None:
                issues.append(
                    OutlineIssue(
                        code="UNKNOWN_PAGE",
                        message="linked page is not a stored page of this project",
                        section_id=section.section_id,
                        ref=str(link.page_id),
                    )
                )
            elif stored != link.url:
                issues.append(
                    OutlineIssue(
                        code="URL_MISMATCH",
                        message="link URL differs from the stored page URL",
                        section_id=section.section_id,
                        ref=link.url,
                    )
                )
        if outline.primary_mode == "prompt" and not (section.citable_statement or "").strip():
            issues.append(
                OutlineIssue(
                    code="MISSING_CITABLE_STATEMENT",
                    message="prompt-primary sections need a citable statement",
                    section_id=section.section_id,
                )
            )
    return issues
