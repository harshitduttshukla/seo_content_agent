"""V3 draft contract (prompt ``v3.draft.v1``) and its claim-grounding validation.

A draft executes the G1-approved outline; it never restructures it. The model
writes one body per outline section. Everything structural (title, section ids,
order, headings, demand targets, planned links) is copied from the outline, so
the model cannot rewrite it.

Grounding (handoff §6.3): every assertion about the company, its products,
clients or competitors carries an inline ``[CLM:<claim uuid>]`` marker for a
claim the approved outline attached. Where no claim exists the writer emits
``[NEEDS-CLAIM: …]`` instead of inventing one; those are stored as unresolved
requirements for QA and a human, never turned into claims.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.domains.ai.context import BundleClaim, CardContextBundle
from app.domains.content_cards.outline import (
    DIRECT_ANSWER_MAX_WORDS,
    OutlineIssue,
    OutlineV3,
    word_count,
)
from pydantic import BaseModel, ConfigDict, Field

V3_DRAFT_SCHEMA_VERSION: Literal["v3.draft.v1"] = "v3.draft.v1"
SECTION_BODY_MAX_CHARS = 20_000

CLAIM_MARKER = re.compile(r"\[CLM:([0-9a-fA-F-]{36})\]")
# Anything that looks like a claim marker; used to catch malformed ones.
ANY_CLAIM_MARKER = re.compile(r"\[CLM[^\]]*\]")
NEEDS_CLAIM_MARKER = re.compile(r"\[NEEDS-CLAIM:\s*([^\]]+?)\s*\]")
MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\((\S+?)\)")
BARE_URL = re.compile(r"https?://[^\s\"'<>)\]]+")
# Page and section headings belong to the outline; bodies may only use ### and below.
STRUCTURAL_HEADING = re.compile(r"^\s{0,3}#{1,2}\s", re.MULTILINE)


class DraftModelSection(BaseModel):
    """What the model returns for one section: the id it answers and the body."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(min_length=1, max_length=64)
    body: str = Field(min_length=1, max_length=SECTION_BODY_MAX_CHARS)


class DraftModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v3.draft.v1"] = V3_DRAFT_SCHEMA_VERSION
    direct_answer: str | None = Field(default=None, max_length=800)
    sections: list[DraftModelSection] = Field(min_length=1, max_length=30)


class DraftLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: UUID
    url: str
    anchor_text: str = ""


class DraftSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    order: int = Field(ge=1)
    heading: str
    target_demand_id: UUID | None = None
    body: str
    # Derived from the body's markers; the body stays the source of truth.
    claim_ids: list[UUID] = Field(default_factory=list)
    needs_claim: list[str] = Field(default_factory=list)
    internal_links: list[DraftLink] = Field(default_factory=list)


class DraftV3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v3.draft.v1"] = V3_DRAFT_SCHEMA_VERSION
    primary_mode: Literal["keyword", "prompt"]
    title: str
    prompt_target_id: UUID | None = None
    direct_answer: str | None = None
    sections: list[DraftSection] = Field(min_length=1)


class UnresolvedClaimNeed(BaseModel):
    """A ``[NEEDS-CLAIM]`` marker: an assertion waiting for an approved claim."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    text: str


class StoredDraft(BaseModel):
    """``ContentCard.draft``: the validated draft plus where it came from."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    draft: DraftV3
    unresolved: list[UnresolvedClaimNeed] = Field(default_factory=list)
    job_run_id: UUID
    prompt_version: str
    provider: str
    model: str
    bundle_ref: UUID
    bundle_hash: str
    # The card revision the draft was generated against.
    source_revision: int
    generated_at: datetime
    generated_by: UUID
    # History (Phase 4): how this version was made and from what. Every version's full
    # draft also stays on its JobRun, so earlier versions are never lost.
    generation_type: Literal["generate", "repair", "section_regeneration"] = "generate"
    previous_version: int | None = None
    trigger: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DraftInput:
    """Everything a draft is generated from, resolved and scoped by the caller.

    ``claims`` are the outline's claims (approved and current) and ``pages`` are
    the project's stored page URLs; production and the Harness build this the
    same way, so validation is identical in both.
    """

    bundle: CardContextBundle
    outline: OutlineV3
    claims: tuple[BundleClaim, ...]
    pages: dict[UUID, str] = field(default_factory=dict)

    @property
    def outline_claim_ids(self) -> frozenset[UUID]:
        return frozenset(c for s in self.outline.sections for c in s.claim_ids)


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


def _issue(
    code: str, message: str, section_id: str | None = None, ref: str | None = None
) -> OutlineIssue:
    return OutlineIssue(code=code, message=message, section_id=section_id, ref=ref)


def body_urls(body: str) -> list[str]:
    """Every URL a body links to, markdown or bare, in order."""
    urls = [url for _, url in MARKDOWN_LINK.findall(body)]
    stripped = MARKDOWN_LINK.sub("", body)
    return urls + BARE_URL.findall(stripped)


def validate_draft(
    output: DraftModelOutput, source: DraftInput, *, compose_with_issues: bool = False
) -> tuple[DraftV3 | None, list[OutlineIssue]]:
    """Check model output against the approved outline; compose the stored draft.

    Pure. Returns the composed draft only when there are no issues.
    """
    outline = source.outline
    issues: list[OutlineIssue] = []
    expected = [s.section_id for s in outline.sections]
    got = [s.section_id for s in output.sections]
    if sorted(got) != sorted(expected) or len(set(got)) != len(got):
        missing = sorted(set(expected) - set(got))
        extra = sorted(set(got) - set(expected))
        issues.append(
            _issue(
                "SECTION_MISMATCH",
                f"sections must be exactly the outline's: missing {missing or 'none'}, "
                f"unexpected {extra or 'none'}",
            )
        )
    elif got != expected:
        issues.append(_issue("SECTION_ORDER", "sections must follow the outline order"))

    allowed_claims = source.outline_claim_ids & {c.id for c in source.claims}
    stored_urls = {url: page_id for page_id, url in source.pages.items()}
    bodies = {s.section_id: s.body for s in output.sections}
    sections: list[DraftSection] = []
    for spec in outline.sections:
        body = bodies.get(spec.section_id)
        if body is None:
            continue
        if not body.strip():
            issues.append(_issue("EMPTY_SECTION", "section body is empty", spec.section_id))
        if STRUCTURAL_HEADING.search(body):
            issues.append(
                _issue(
                    "STRUCTURE_CHANGED",
                    "bodies may not add # or ## headings; the outline owns the structure",
                    spec.section_id,
                )
            )
        markers = CLAIM_MARKER.findall(body)
        for malformed in ANY_CLAIM_MARKER.findall(body):
            if not CLAIM_MARKER.fullmatch(malformed):
                issues.append(
                    _issue(
                        "MALFORMED_CLAIM_MARKER", "use [CLM:<claim id>]", spec.section_id, malformed
                    )
                )
        cited: list[UUID] = []
        for raw in markers:
            try:
                claim_id = UUID(raw)
            except ValueError:
                issues.append(
                    _issue("MALFORMED_CLAIM_MARKER", "not a claim id", spec.section_id, raw)
                )
                continue
            if claim_id not in allowed_claims:
                issues.append(
                    _issue(
                        "CLAIM_NOT_IN_OUTLINE",
                        "cites a claim the approved outline did not attach",
                        spec.section_id,
                        str(claim_id),
                    )
                )
            elif claim_id not in cited:
                cited.append(claim_id)
        for claim_id in spec.claim_ids:
            if claim_id in allowed_claims and claim_id not in cited:
                issues.append(
                    _issue(
                        "MISSING_CLAIM_MARKER",
                        "the section does not cite a claim the outline attached to it",
                        spec.section_id,
                        str(claim_id),
                    )
                )
        links: list[DraftLink] = []
        for url in body_urls(body):
            page_id = stored_urls.get(url)
            if page_id is None:
                issues.append(
                    _issue(
                        "INVENTED_URL", "links only to stored project pages", spec.section_id, url
                    )
                )
            elif all(link.url != url for link in links):
                links.append(DraftLink(page_id=page_id, url=url))
        for planned in spec.planned_internal_links:
            if all(link.url != planned.url for link in links):
                issues.append(
                    _issue(
                        "MISSING_PLANNED_LINK",
                        "a planned internal link is missing from the section",
                        spec.section_id,
                        planned.url,
                    )
                )
        anchors = {p.url: p.anchor_text for p in spec.planned_internal_links}
        links = [
            link.model_copy(update={"anchor_text": anchors.get(link.url, "")}) for link in links
        ]
        if (
            outline.primary_mode == "prompt"
            and spec.citable_statement
            and _normalise(spec.citable_statement) not in _normalise(body)
        ):
            issues.append(
                _issue(
                    "MISSING_CITABLE_STATEMENT",
                    "prompt-primary sections keep the outline's citable statement verbatim",
                    spec.section_id,
                )
            )
        sections.append(
            DraftSection(
                section_id=spec.section_id,
                order=spec.order,
                heading=spec.heading,
                target_demand_id=spec.target_demand_id,
                body=body,
                claim_ids=cited,
                needs_claim=NEEDS_CLAIM_MARKER.findall(body),
                internal_links=links,
            )
        )

    direct_answer: str | None = None
    if outline.primary_mode == "prompt":
        direct_answer = (output.direct_answer or "").strip() or None
        if direct_answer is None:
            issues.append(
                _issue("MISSING_DIRECT_ANSWER", "prompt-primary drafts open with a direct answer")
            )
        elif word_count(direct_answer) > DIRECT_ANSWER_MAX_WORDS:
            issues.append(
                _issue(
                    "DIRECT_ANSWER_TOO_LONG",
                    f"the direct answer must be at most {DIRECT_ANSWER_MAX_WORDS} words",
                )
            )
        elif ANY_CLAIM_MARKER.search(direct_answer) or body_urls(direct_answer):
            issues.append(
                _issue("DIRECT_ANSWER_MARKUP", "the direct answer carries no markers or links")
            )

    if issues and not compose_with_issues:
        return None, issues
    return (
        DraftV3(
            primary_mode=outline.primary_mode,
            title=outline.title,
            prompt_target_id=outline.prompt_target_id,
            direct_answer=direct_answer,
            sections=sections,
        ),
        issues,
    )


def unresolved_needs(draft: DraftV3) -> list[UnresolvedClaimNeed]:
    return [
        UnresolvedClaimNeed(section_id=section.section_id, text=text)
        for section in draft.sections
        for text in section.needs_claim
    ]
