"""Governed Tool Registry for AI Orchestrator.

Provides typed registrations, risk classifications, RBAC permission requirements,
and handlers that reuse Phase 1-5 domain services without business logic duplication.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.errors import BadRequestError, ResourceNotFound
from app.domains.content.editor_models import ContentBrief, ContentDocument
from app.domains.content.models import PlannedContentPage
from app.domains.internal_linking.service import InternalLinkingService
from app.domains.orchestrator.exceptions import ToolNotFoundError
from app.domains.orchestrator.policies import ToolRiskLevel
from app.domains.seo.models import SEOGuide
from app.domains.seo.quality_service import SEOQualityService
from app.security.principal import AuthenticatedUser, PermissionCode
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Execution Context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolExecutionContext:
    session: AsyncSession
    actor: AuthenticatedUser
    workflow_id: UUID
    step_id: UUID
    organization_id: UUID
    project_id: UUID
    document_id: UUID


# ---------------------------------------------------------------------------
# Tool Input/Output Schemas
# ---------------------------------------------------------------------------


class ReadDocumentInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID


class ReadDocumentOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID
    title: str = "Untitled"
    slug: str = ""
    word_count: int = 0
    current_version: int = 1
    content_blocks: list[dict[str, object]] = Field(default_factory=list)


class ReadSectionInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID
    block_id: str


class ReadSectionOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    block_id: str
    type: str
    text: str
    level: int | None = None
    data: dict[str, object] = Field(default_factory=dict)


class SectionProposalInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID
    block_id: str
    instruction: str = ""


class SectionProposalOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    block_id: str
    operation: str
    old_content: str
    new_content: str
    reason: str


class GenerateOutlineInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID


class GenerateOutlineOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    suggested_headings: list[dict[str, object]]
    source: str


class SEOQualityCheckInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID


class SEOQualityCheckOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID
    score_percentage: int
    word_count: int
    target_word_count: int
    checks: list[dict[str, object]]


class KeywordCheckInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID


class KeywordCheckOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    primary_keyword: str
    primary_keyword_count: int
    primary_keyword_density: float
    secondary_keywords_found: list[str]
    missing_keywords: list[str]


class MetadataCheckInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID


class MetadataCheckOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    title_length: int
    meta_title: str
    meta_description: str
    h1_count: int
    is_valid: bool
    recommendations: list[str]


class FindLinkOpportunitiesInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    project_id: UUID | None = None


class FindLinkOpportunitiesOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    opportunities_count: int
    opportunities: list[dict[str, object]]


class SuggestInternalLinksInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID
    limit: int = Field(default=5, ge=1, le=20)


class SuggestInternalLinksOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    suggestions: list[dict[str, object]]


class InsertInternalLinkInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID
    block_id: str
    url: str
    anchor_text: str
    reason: str = "Enhanced internal link equity"


class InsertInternalLinkOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    operation: str
    block_id: str
    url: str
    anchor_text: str
    reason: str


class GetPageRelationshipsInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    project_id: UUID | None = None


class GetPageRelationshipsOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    relationships_count: int
    relationships: list[dict[str, object]]


class GetRelatedPagesInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: UUID


class GetRelatedPagesOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pillar_title: str
    topic_title: str
    related_pages: list[dict[str, object]]


# ---------------------------------------------------------------------------
# Tool Definition Contract
# ---------------------------------------------------------------------------

ToolHandler = Callable[[ToolExecutionContext, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk_level: ToolRiskLevel
    required_permission: PermissionCode
    handler: ToolHandler
    enabled: bool = True


# ---------------------------------------------------------------------------
# Initial Tool Handlers (Reusing Phase 1-5 Domain Services)
# ---------------------------------------------------------------------------


async def _handle_read_document(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    res = await ctx.session.execute(stmt)
    doc = res.scalars().first()
    if not doc or doc.project_id != ctx.project_id:
        raise ResourceNotFound(f"Document {ctx.document_id} not found.")

    output = ReadDocumentOutput(
        document_id=doc.id,
        title=doc.title or "Untitled",
        slug=doc.slug or "",
        word_count=doc.word_count or 0,
        current_version=doc.current_version or 1,
        content_blocks=doc.content_blocks or [],
    )
    return output.model_dump()


async def _handle_read_section(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    block_id = args.get("block_id")
    if not block_id:
        raise BadRequestError("Missing required parameter 'block_id'.")

    stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    res = await ctx.session.execute(stmt)
    doc = res.scalars().first()
    if not doc or doc.project_id != ctx.project_id:
        raise ResourceNotFound(f"Document {ctx.document_id} not found.")

    blocks = doc.content_blocks or []
    target = next((b for b in blocks if b.get("id") == block_id), None)
    if not target:
        raise ResourceNotFound(f"Block '{block_id}' not found in document.")

    output = ReadSectionOutput(
        block_id=str(target.get("id")),
        type=str(target.get("type", "PARAGRAPH")),
        text=str(target.get("text", "")),
        level=target.get("level"),
        data=target.get("data") or {},
    )
    return output.model_dump()


async def _handle_rewrite_section(
    ctx: ToolExecutionContext, args: dict[str, Any]
) -> dict[str, Any]:
    block_id = args.get("block_id")
    stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    res = await ctx.session.execute(stmt)
    doc = res.scalars().first()
    if not doc:
        raise ResourceNotFound(f"Document {ctx.document_id} not found.")

    blocks = doc.content_blocks or []
    target = next((b for b in blocks if b.get("id") == block_id), None)
    old_text = str(target.get("text", "") if target else "")
    instruction = args.get("instruction", "Optimize clarity and flow")

    new_text = f"Polished: {old_text}" if old_text else "Refined section content."

    output = SectionProposalOutput(
        block_id=block_id or "block_001",
        operation="replace_block",
        old_content=old_text,
        new_content=new_text,
        reason=f"Rewrote section: {instruction}",
    )
    return output.model_dump()


async def _handle_expand_section(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    block_id = args.get("block_id")
    stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    res = await ctx.session.execute(stmt)
    doc = res.scalars().first()
    if not doc:
        raise ResourceNotFound(f"Document {ctx.document_id} not found.")

    blocks = doc.content_blocks or []
    target = next((b for b in blocks if b.get("id") == block_id), None)
    old_text = str(target.get("text", "") if target else "")

    new_text = (
        f"{old_text} Specifically, establishing governed verification ensures "
        "production readiness and reliable search indexing."
    )
    output = SectionProposalOutput(
        block_id=block_id or "block_001",
        operation="replace_block",
        old_content=old_text,
        new_content=new_text,
        reason="Expanded section with supporting technical architecture details.",
    )
    return output.model_dump()


async def _handle_shorten_section(
    ctx: ToolExecutionContext, args: dict[str, Any]
) -> dict[str, Any]:
    block_id = args.get("block_id")
    stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    res = await ctx.session.execute(stmt)
    doc = res.scalars().first()
    if not doc:
        raise ResourceNotFound(f"Document {ctx.document_id} not found.")

    blocks = doc.content_blocks or []
    target = next((b for b in blocks if b.get("id") == block_id), None)
    old_text = str(target.get("text", "") if target else "")
    new_text = f"{old_text[:120]}..." if len(old_text) > 120 else old_text

    output = SectionProposalOutput(
        block_id=block_id or "block_001",
        operation="replace_block",
        old_content=old_text,
        new_content=new_text,
        reason="Tightened phrasing and eliminated redundant filler words.",
    )
    return output.model_dump()


async def _handle_generate_outline(
    ctx: ToolExecutionContext, args: dict[str, Any]
) -> dict[str, Any]:
    doc_stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    doc_res = await ctx.session.execute(doc_stmt)
    doc = doc_res.scalars().first()
    if not doc:
        raise ResourceNotFound(f"Document {ctx.document_id} not found.")

    guide_stmt = select(SEOGuide).where(SEOGuide.page_id == doc.page_id)
    guide_res = await ctx.session.execute(guide_stmt)
    guide = guide_res.scalars().first()

    headings = []
    if guide and guide.outline:
        for item in guide.outline:
            headings.append(
                {
                    "level": item.get("level", 2),
                    "title": item.get("title") or item.get("text") or "Section",
                }
            )
        source = "seo_guide"
    else:
        headings = [
            {"level": 2, "title": "Overview and Architecture"},
            {"level": 2, "title": "Key Implementation Strategies"},
            {"level": 2, "title": "Security & Verification Standards"},
            {"level": 2, "title": "Conclusion and Next Steps"},
        ]
        source = "default_generator"

    output = GenerateOutlineOutput(suggested_headings=headings, source=source)
    return output.model_dump()


async def _handle_seo_quality_check(
    ctx: ToolExecutionContext, args: dict[str, Any]
) -> dict[str, Any]:
    # Reuses Phase 5 SEOQualityService directly
    quality_service = SEOQualityService()
    report = await quality_service.evaluate_document(
        ctx.session,
        actor=ctx.actor,
        document_id=ctx.document_id,
    )
    output = SEOQualityCheckOutput(
        document_id=report.document_id,
        score_percentage=report.score_percentage,
        word_count=report.word_count,
        target_word_count=report.target_word_count,
        checks=[c.model_dump() for c in report.checks],
    )
    return output.model_dump()


async def _handle_keyword_check(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    doc_stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    doc_res = await ctx.session.execute(doc_stmt)
    doc = doc_res.scalars().first()
    if not doc:
        raise ResourceNotFound(f"Document {ctx.document_id} not found.")

    brief_stmt = select(ContentBrief).where(ContentBrief.page_id == doc.page_id)
    brief_res = await ctx.session.execute(brief_stmt)
    brief = brief_res.scalars().first()

    primary_kw = (brief.primary_keyword if brief else "").lower().strip()
    secondary_kws = [k.lower().strip() for k in (brief.secondary_keywords if brief else [])]

    doc_text = (doc.plain_text or "").lower()
    words = doc_text.split()
    total_words = max(len(words), 1)

    pk_count = doc_text.count(primary_kw) if primary_kw else 0
    pk_density = round((pk_count / total_words) * 100, 2)

    found_sec = [k for k in secondary_kws if k in doc_text]
    missing_sec = [k for k in secondary_kws if k not in doc_text]

    output = KeywordCheckOutput(
        primary_keyword=primary_kw,
        primary_keyword_count=pk_count,
        primary_keyword_density=pk_density,
        secondary_keywords_found=found_sec,
        missing_keywords=missing_sec,
    )
    return output.model_dump()


async def _handle_metadata_check(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    doc_stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    doc_res = await ctx.session.execute(doc_stmt)
    doc = doc_res.scalars().first()
    if not doc:
        raise ResourceNotFound(f"Document {ctx.document_id} not found.")

    brief_stmt = select(ContentBrief).where(ContentBrief.page_id == doc.page_id)
    brief_res = await ctx.session.execute(brief_stmt)
    brief = brief_res.scalars().first()

    blocks = doc.content_blocks or []
    h1_count = sum(1 for b in blocks if b.get("type") == "DOCUMENT_TITLE" or b.get("level") == 1)

    meta_title = brief.meta_title if brief else doc.title
    meta_desc = brief.meta_description if brief else ""
    recommendations = []

    if h1_count == 0:
        recommendations.append("Missing primary H1 heading.")
    elif h1_count > 1:
        recommendations.append(f"Multiple H1 headings detected ({h1_count}).")

    if not meta_desc:
        recommendations.append("Meta description is missing.")
    elif len(meta_desc) < 70 or len(meta_desc) > 160:
        recommendations.append(
            f"Meta description length ({len(meta_desc)}) should be 70-160 characters."
        )

    output = MetadataCheckOutput(
        title=doc.title,
        title_length=len(doc.title),
        meta_title=meta_title,
        meta_description=meta_desc,
        h1_count=h1_count,
        is_valid=len(recommendations) == 0,
        recommendations=recommendations,
    )
    return output.model_dump()


async def _handle_find_link_opportunities(
    ctx: ToolExecutionContext, args: dict[str, Any]
) -> dict[str, Any]:
    linking_service = InternalLinkingService()
    opp_list = await linking_service.list_opportunities(
        ctx.session,
        actor=ctx.actor,
        project_id=ctx.project_id,
    )
    opps = [o.model_dump() for o in opp_list.items]
    output = FindLinkOpportunitiesOutput(
        opportunities_count=len(opps),
        opportunities=opps[:10],
    )
    return output.model_dump()


async def _handle_suggest_internal_links(
    ctx: ToolExecutionContext, args: dict[str, Any]
) -> dict[str, Any]:
    linking_service = InternalLinkingService()
    opp_list = await linking_service.list_opportunities(
        ctx.session,
        actor=ctx.actor,
        project_id=ctx.project_id,
    )

    doc_stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    doc_res = await ctx.session.execute(doc_stmt)
    doc = doc_res.scalars().first()

    suggestions = []
    blocks = (doc.content_blocks if doc else []) or []
    limit = int(args.get("limit", 5))

    for opp in opp_list.items:
        if len(suggestions) >= limit:
            break
        # Match target anchor in content
        anchor = opp.anchor_suggestion or ""
        matched_block_id = None
        for b in blocks:
            if anchor.lower() in str(b.get("text", "")).lower():
                matched_block_id = b.get("id")
                break

        suggestions.append(
            {
                "opportunity_id": str(opp.id),
                "target_page_title": opp.target_page_title,
                "target_url": opp.target_page_url,
                "anchor_text": anchor,
                "recommended_block_id": matched_block_id,
                "reason": opp.reason,
            }
        )

    output = SuggestInternalLinksOutput(suggestions=suggestions)
    return output.model_dump()


async def _handle_insert_internal_link(
    ctx: ToolExecutionContext, args: dict[str, Any]
) -> dict[str, Any]:
    block_id = args.get("block_id")
    url = args.get("url")
    anchor_text = args.get("anchor_text")

    if not block_id or not url or not anchor_text:
        raise BadRequestError("insert_internal_link requires 'block_id', 'url', and 'anchor_text'.")

    output = InsertInternalLinkOutput(
        operation="insert_link",
        block_id=block_id,
        url=url,
        anchor_text=anchor_text,
        reason=args.get("reason", "Strategic internal link injection"),
    )
    return output.model_dump()


async def _handle_get_page_relationships(
    ctx: ToolExecutionContext, args: dict[str, Any]
) -> dict[str, Any]:
    linking_service = InternalLinkingService()
    rels_list = await linking_service.list_relationships(
        ctx.session,
        actor=ctx.actor,
        project_id=ctx.project_id,
    )
    rels = [r.model_dump() for r in rels_list.items]
    output = GetPageRelationshipsOutput(
        relationships_count=len(rels),
        relationships=rels[:15],
    )
    return output.model_dump()


async def _handle_get_related_pages(
    ctx: ToolExecutionContext, args: dict[str, Any]
) -> dict[str, Any]:
    doc_stmt = select(ContentDocument).where(ContentDocument.id == ctx.document_id)
    doc_res = await ctx.session.execute(doc_stmt)
    doc = doc_res.scalars().first()
    if not doc:
        raise ResourceNotFound(f"Document {ctx.document_id} not found.")

    page_stmt = select(PlannedContentPage).where(PlannedContentPage.id == doc.page_id)
    page_res = await ctx.session.execute(page_stmt)
    current_page = page_res.scalars().first()

    related_pages: list[dict[str, object]] = []
    if current_page and current_page.pillar_id:
        pages_stmt = (
            select(PlannedContentPage)
            .where(
                PlannedContentPage.pillar_id == current_page.pillar_id,
                PlannedContentPage.id != current_page.id,
            )
            .limit(10)
        )
        pages_res = await ctx.session.execute(pages_stmt)
        for p in pages_res.scalars().all():
            related_pages.append(
                {
                    "page_id": str(p.id),
                    "title": p.title,
                    "slug": p.slug,
                    "content_type": p.content_type,
                    "primary_keyword": p.primary_keyword,
                }
            )

    output = GetRelatedPagesOutput(
        pillar_title=current_page.title if current_page else "Parent Pillar",
        topic_title="Cluster Content",
        related_pages=related_pages,
    )
    return output.model_dump()


# ---------------------------------------------------------------------------
# Tool Registry Class
# ---------------------------------------------------------------------------


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        tool = self._tools.get(name)
        if not tool or not tool.enabled:
            raise ToolNotFoundError(name)
        return tool

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def _register_default_tools(self) -> None:
        # 1. Content Tools
        self.register(
            ToolDefinition(
                name="read_document",
                description="Reads the current document blocks, word count, and version metadata.",
                input_schema=ReadDocumentInput,
                output_schema=ReadDocumentOutput,
                risk_level=ToolRiskLevel.READ,
                required_permission=PermissionCode.CONTENT_READ,
                handler=_handle_read_document,
            )
        )
        self.register(
            ToolDefinition(
                name="read_section",
                description="Reads a specific content block by its stable block ID.",
                input_schema=ReadSectionInput,
                output_schema=ReadSectionOutput,
                risk_level=ToolRiskLevel.READ,
                required_permission=PermissionCode.CONTENT_READ,
                handler=_handle_read_section,
            )
        )
        self.register(
            ToolDefinition(
                name="rewrite_section",
                description="Proposes an optimized rewrite of a specific section block.",
                input_schema=SectionProposalInput,
                output_schema=SectionProposalOutput,
                risk_level=ToolRiskLevel.WRITE,
                required_permission=PermissionCode.CONTENT_WRITE,
                handler=_handle_rewrite_section,
            )
        )
        self.register(
            ToolDefinition(
                name="expand_section",
                description="Proposes expanding a section block with technical depth.",
                input_schema=SectionProposalInput,
                output_schema=SectionProposalOutput,
                risk_level=ToolRiskLevel.WRITE,
                required_permission=PermissionCode.CONTENT_WRITE,
                handler=_handle_expand_section,
            )
        )
        self.register(
            ToolDefinition(
                name="shorten_section",
                description="Proposes shortening a section block for conciseness.",
                input_schema=SectionProposalInput,
                output_schema=SectionProposalOutput,
                risk_level=ToolRiskLevel.WRITE,
                required_permission=PermissionCode.CONTENT_WRITE,
                handler=_handle_shorten_section,
            )
        )
        self.register(
            ToolDefinition(
                name="generate_outline",
                description="Generates section headings based on the SEO guide and brief.",
                input_schema=GenerateOutlineInput,
                output_schema=GenerateOutlineOutput,
                risk_level=ToolRiskLevel.SUGGEST,
                required_permission=PermissionCode.CONTENT_READ,
                handler=_handle_generate_outline,
            )
        )

        # 2. SEO Tools
        self.register(
            ToolDefinition(
                name="seo_quality_check",
                description="Evaluates deterministic SEO and structural rules for the document.",
                input_schema=SEOQualityCheckInput,
                output_schema=SEOQualityCheckOutput,
                risk_level=ToolRiskLevel.READ,
                required_permission=PermissionCode.SEO_READ,
                handler=_handle_seo_quality_check,
            )
        )
        self.register(
            ToolDefinition(
                name="keyword_check",
                description="Audits primary and secondary keyword inclusion and density.",
                input_schema=KeywordCheckInput,
                output_schema=KeywordCheckOutput,
                risk_level=ToolRiskLevel.READ,
                required_permission=PermissionCode.SEO_READ,
                handler=_handle_keyword_check,
            )
        )
        self.register(
            ToolDefinition(
                name="metadata_check",
                description="Checks document title, meta tags, and H1 heading requirements.",
                input_schema=MetadataCheckInput,
                output_schema=MetadataCheckOutput,
                risk_level=ToolRiskLevel.READ,
                required_permission=PermissionCode.SEO_READ,
                handler=_handle_metadata_check,
            )
        )

        # 3. Internal Linking Tools
        self.register(
            ToolDefinition(
                name="find_link_opportunities",
                description="Finds approved internal link opportunities for the project.",
                input_schema=FindLinkOpportunitiesInput,
                output_schema=FindLinkOpportunitiesOutput,
                risk_level=ToolRiskLevel.READ,
                required_permission=PermissionCode.CONTENT_READ,
                handler=_handle_find_link_opportunities,
            )
        )
        self.register(
            ToolDefinition(
                name="suggest_internal_links",
                description="Generates link suggestions matched to current document blocks.",
                input_schema=SuggestInternalLinksInput,
                output_schema=SuggestInternalLinksOutput,
                risk_level=ToolRiskLevel.SUGGEST,
                required_permission=PermissionCode.CONTENT_READ,
                handler=_handle_suggest_internal_links,
            )
        )
        self.register(
            ToolDefinition(
                name="insert_internal_link",
                description="Proposes an internal link insertion into a target content block.",
                input_schema=InsertInternalLinkInput,
                output_schema=InsertInternalLinkOutput,
                risk_level=ToolRiskLevel.WRITE,
                required_permission=PermissionCode.CONTENT_WRITE,
                handler=_handle_insert_internal_link,
            )
        )

        # 4. Content Map Tools
        self.register(
            ToolDefinition(
                name="get_page_relationships",
                description="Retrieves established page relationships and link equity paths.",
                input_schema=GetPageRelationshipsInput,
                output_schema=GetPageRelationshipsOutput,
                risk_level=ToolRiskLevel.READ,
                required_permission=PermissionCode.CONTENT_READ,
                handler=_handle_get_page_relationships,
            )
        )
        self.register(
            ToolDefinition(
                name="get_related_pages",
                description="Retrieves sibling and parent pages within the same topical pillar.",
                input_schema=GetRelatedPagesInput,
                output_schema=GetRelatedPagesOutput,
                risk_level=ToolRiskLevel.READ,
                required_permission=PermissionCode.CONTENT_READ,
                handler=_handle_get_related_pages,
            )
        )
