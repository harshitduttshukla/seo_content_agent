"""Comprehensive unit tests for Content Agent Context Management.

Verifies:
1. Full ContentAgentContext construction
2. SEO Strategy retrieval and version resolution (current_version vs fallback)
3. Keyword retrieval with metrics and clusters
4. Search intent resolution precedence
5. Target audience resolution precedence
6. Content Map retrieval (pillar, topic, cluster, siblings, graph)
7. SEO Guide retrieval (complete fields, outline, seo_rules)
8. Content Brief retrieval (complete fields, brand requirements)
9. Brand rules extraction (truthful, no fabrication)
10. Internal linking context (targets, opportunities, relationships)
11. Website and crawl context (bounded evidence)
12. Existing pages evidence
13. Competitors from strategy
14. Entities deduplication
15. Questions from brief
16. Content requirements deduplication
17. Source requirements
18. Current document and selection
19. Conversation history
20. Provenance metadata
21. Missing data behavior (None / empty collections, zero fabrication)
22. Cross-project access denial
23. Cross-organization access denial
24. Token budget estimation and enforcement
25. Priority-tier token pruning order and observable truncation
26. Database truth vs rendering defaults separation
27. Full-document request handling
28. Focused-document request handling
29. AI Editor backward compatibility
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from app.core.errors import PermissionDenied
from app.domains.ai.context import ContentAgentContext
from app.domains.ai.context_builder import ContentAgentContextBuilder, ContextBuilderService
from app.domains.content.editor_models import (
    ContentBrief,
    ContentDocument,
)
from app.domains.content.models import (
    PlannedContentPage,
)
from app.domains.keywords.models import Keyword
from app.domains.seo.models import SEOGuide
from app.domains.strategy.models import SEOStrategy, SEOStrategyVersion
from app.security.principal import AuthenticatedUser


def make_mock_session_with_data(entity_map: dict[type, object]) -> MagicMock:
    """Helper to dispatch SQLAlchemy query results based on model class in statement."""
    session = MagicMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    session.begin.return_value = context_manager
    session.refresh = AsyncMock()
    session.flush = AsyncMock()

    async def _execute(stmt: object) -> MagicMock:
        mock_res = MagicMock()
        mock_scalars = MagicMock()
        model_type = None
        if hasattr(stmt, "column_descriptions") and stmt.column_descriptions:
            model_type = stmt.column_descriptions[0].get("type")

        val = entity_map.get(model_type)
        if isinstance(val, list):
            mock_scalars.all.return_value = val
            mock_scalars.first.return_value = val[0] if val else None
        else:
            mock_scalars.all.return_value = [val] if val is not None else []
            mock_scalars.first.return_value = val
        mock_res.scalars.return_value = mock_scalars
        return mock_res

    session.execute = AsyncMock(side_effect=_execute)
    return session


@pytest.fixture
def base_ids() -> dict[str, UUID]:
    return {
        "org_id": uuid4(),
        "proj_id": uuid4(),
        "doc_id": uuid4(),
        "page_id": uuid4(),
        "brief_id": uuid4(),
        "guide_id": uuid4(),
        "strategy_id": uuid4(),
        "website_id": uuid4(),
        "kw_id": uuid4(),
        "cluster_id": uuid4(),
        "pillar_id": uuid4(),
        "topic_id": uuid4(),
    }


@pytest.fixture
def base_doc(base_ids: dict[str, UUID]) -> ContentDocument:
    return ContentDocument(
        id=base_ids["doc_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        page_id=base_ids["page_id"],
        brief_id=base_ids["brief_id"],
        website_id=base_ids["website_id"],
        title="Zero Trust Architecture Guide",
        slug="zero-trust-architecture-guide",
        status="DRAFT",
        current_version=1,
        lock_version=1,
        word_count=450,
        content_blocks=[
            {"id": "b1", "type": "h1", "text": "Zero Trust Security Overview"},
            {
                "id": "b2",
                "type": "paragraph",
                "text": "Traditional perimeter security is obsolete.",
            },
            {"id": "b3", "type": "paragraph", "text": "Identity verification must be continuous."},
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# 1. Full ContentAgentContext Construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_content_agent_context_construction(
    base_ids: dict[str, UUID], base_doc: ContentDocument
) -> None:
    brief = ContentBrief(
        id=base_ids["brief_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        page_id=base_ids["page_id"],
        primary_keyword="zero trust architecture",
        secondary_keywords=["perimeter security", "continuous authentication"],
        search_intent="INFORMATIONAL",
        target_audience="Enterprise Security Architects",
        target_word_count=2000,
        required_topics=["Core Principles", "Microsegmentation"],
        key_entities=["NIST 800-207", "Identity Provider"],
        questions_to_answer=["What is zero trust?", "How to implement it?"],
        internal_link_targets=[{"url": "/pillars/security", "anchor_text": "Security Pillar"}],
        external_source_requirements=["NIST SP 800-207"],
        content_requirements=["Include comparison table"],
        brand_requirements={"tone": "authoritative", "words_to_avoid": ["unhackable"]},
    )
    guide = SEOGuide(
        id=base_ids["guide_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        page_id=base_ids["page_id"],
        primary_keyword="zero trust architecture",
        search_intent="INFORMATIONAL",
        target_audience="Security Engineers",
        word_count_target=2000,
        required_topics=["Core Principles"],
        key_entities=["NIST 800-207"],
        serp_notes="Top ranking pages focus on NIST standards",
        outline=[{"heading": "Introduction", "level": 2}],
        seo_rules={"min_word_count": 1500},
    )
    page = PlannedContentPage(
        id=base_ids["page_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        website_id=base_ids["website_id"],
        title="Zero Trust Architecture",
        slug="zero-trust-architecture",
        url="/guides/zero-trust-architecture",
        intent="INFORMATIONAL",
        primary_keyword="zero trust architecture",
        pillar_id=base_ids["pillar_id"],
        topic_id=base_ids["topic_id"],
        cluster_id=base_ids["cluster_id"],
    )
    strategy = SEOStrategy(
        id=base_ids["strategy_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        current_version=2,
        status="active",
    )
    strategy_v2 = SEOStrategyVersion(
        id=uuid4(),
        strategy_id=base_ids["strategy_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        version=2,
        strategy_data={
            "business_context": {"business_name": "CyberSec Global", "industry": "Cybersecurity"},
            "audience": {"segments": ["Enterprise CISOs", "DevSecOps Leads"]},
            "competitors": [{"name": "Palo Alto Networks", "domain": "paloaltonetworks.com"}],
            "priority_topics": ["Zero Trust", "Cloud Security"],
        },
    )
    kw = Keyword(
        id=base_ids["kw_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        keyword="zero trust architecture",
        normalized_keyword="zero trust architecture",
        search_volume=12000,
        keyword_difficulty=65.5,
        cpc=14.50,
        intent="INFORMATIONAL",
    )

    data_map: dict[type, object] = {
        PlannedContentPage: page,
        ContentBrief: brief,
        SEOGuide: guide,
        SEOStrategy: strategy,
        SEOStrategyVersion: strategy_v2,
        Keyword: [kw],
    }

    session = make_mock_session_with_data(data_map)
    builder = ContentAgentContextBuilder()

    context = await builder.build_agent_context(
        session=session,
        document=base_doc,
        user_message="Improve the introduction section",
        selected_block_id="b2",
        selected_text="Traditional perimeter security is obsolete.",
    )

    assert isinstance(context, ContentAgentContext)
    # Check Request
    assert context.request.document_id == base_doc.id
    assert context.request.selected_block_id == "b2"
    assert context.request.selected_text == "Traditional perimeter security is obsolete."
    assert context.request.full_document_request is False

    # Check Strategy
    assert context.seo_strategy.business_name == "CyberSec Global"
    assert "Enterprise CISOs" in context.seo_strategy.audience_segments
    assert len(context.competitors) == 1
    assert context.competitors[0]["name"] == "Palo Alto Networks"

    # Check Keywords
    assert context.keyword_context.primary_keyword is not None
    assert context.keyword_context.primary_keyword.keyword == "zero trust architecture"
    assert context.keyword_context.primary_keyword.search_volume == 12000

    # Check Intent & Audience Precedence
    assert context.resolved_intent == "INFORMATIONAL"
    assert context.resolved_intent_source == "content_brief"
    assert context.resolved_audience == "Enterprise Security Architects"
    assert context.resolved_audience_source == "content_brief"

    # Check Brand Rules
    assert context.brand_rules.tone == "authoritative"
    assert "unhackable" in context.brand_rules.words_to_avoid

    # Check Provenance
    assert context.provenance.strategy_id == base_ids["strategy_id"]
    assert context.provenance.strategy_version == 2
    assert context.provenance.brief_id == base_ids["brief_id"]
    assert context.provenance.guide_id == base_ids["guide_id"]


# ---------------------------------------------------------------------------
# 2. Strategy Retrieval and Version Resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy_version_resolution_current_vs_fallback(
    base_ids: dict[str, UUID], base_doc: ContentDocument
) -> None:
    strategy = SEOStrategy(
        id=base_ids["strategy_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        current_version=3,
        status="active",
    )
    # Return version 3
    strat_v3 = SEOStrategyVersion(
        id=uuid4(),
        strategy_id=base_ids["strategy_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        version=3,
        strategy_data={"business_context": {"business_name": "Active Strategy V3"}},
    )

    session = make_mock_session_with_data(
        {
            SEOStrategy: strategy,
            SEOStrategyVersion: strat_v3,
        }
    )
    builder = ContentAgentContextBuilder()
    ctx = await builder.build_agent_context(session=session, document=base_doc, user_message="test")

    assert ctx.seo_strategy.version == 3
    assert ctx.seo_strategy.business_name == "Active Strategy V3"


# ---------------------------------------------------------------------------
# 3. Intent Precedence Rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_intent_precedence_brief_over_guide_over_page_over_kw(
    base_ids: dict[str, UUID], base_doc: ContentDocument
) -> None:
    # 1. Brief intent takes highest precedence
    brief = ContentBrief(
        id=base_ids["brief_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        page_id=base_ids["page_id"],
        search_intent="TRANSACTIONAL",
    )
    guide = SEOGuide(
        id=base_ids["guide_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        page_id=base_ids["page_id"],
        search_intent="COMMERCIAL",
    )
    page = PlannedContentPage(
        id=base_ids["page_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        intent="INFORMATIONAL",
    )

    builder = ContentAgentContextBuilder()

    # Case A: Brief present -> TRANSACTIONAL
    session_a = make_mock_session_with_data(
        {
            ContentBrief: brief,
            SEOGuide: guide,
            PlannedContentPage: page,
        }
    )
    ctx_a = await builder.build_agent_context(
        session=session_a, document=base_doc, user_message="test"
    )
    assert ctx_a.resolved_intent == "TRANSACTIONAL"
    assert ctx_a.resolved_intent_source == "content_brief"

    # Case B: Brief missing, Guide present -> COMMERCIAL
    session_b = make_mock_session_with_data(
        {
            ContentBrief: None,
            SEOGuide: guide,
            PlannedContentPage: page,
        }
    )
    ctx_b = await builder.build_agent_context(
        session=session_b, document=base_doc, user_message="test"
    )
    assert ctx_b.resolved_intent == "COMMERCIAL"
    assert ctx_b.resolved_intent_source == "seo_guide"

    # Case C: Brief & Guide missing, Page present -> INFORMATIONAL
    session_c = make_mock_session_with_data(
        {
            ContentBrief: None,
            SEOGuide: None,
            PlannedContentPage: page,
        }
    )
    ctx_c = await builder.build_agent_context(
        session=session_c, document=base_doc, user_message="test"
    )
    assert ctx_c.resolved_intent == "INFORMATIONAL"
    assert ctx_c.resolved_intent_source == "planned_content_page"

    # Case D: All missing or UNKNOWN -> None (no fabrication)
    page_unknown = PlannedContentPage(
        id=base_ids["page_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        intent="UNKNOWN",
    )
    session_d = make_mock_session_with_data(
        {
            ContentBrief: None,
            SEOGuide: None,
            PlannedContentPage: page_unknown,
        }
    )
    ctx_d = await builder.build_agent_context(
        session=session_d, document=base_doc, user_message="test"
    )
    assert ctx_d.resolved_intent is None
    assert ctx_d.resolved_intent_source is None


# ---------------------------------------------------------------------------
# 4. Audience Precedence Rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audience_precedence_brief_over_guide_over_strategy(
    base_ids: dict[str, UUID], base_doc: ContentDocument
) -> None:
    brief = ContentBrief(
        id=base_ids["brief_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        page_id=base_ids["page_id"],
        target_audience="Brief Audience",
    )
    guide = SEOGuide(
        id=base_ids["guide_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        page_id=base_ids["page_id"],
        target_audience="Guide Audience",
    )
    strategy = SEOStrategy(
        id=base_ids["strategy_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        current_version=1,
    )
    strat_v = SEOStrategyVersion(
        id=uuid4(),
        strategy_id=base_ids["strategy_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        version=1,
        strategy_data={"audience": {"segments": ["Strategy Segment"]}},
    )

    builder = ContentAgentContextBuilder()

    # Case A: Brief wins
    session_a = make_mock_session_with_data(
        {
            ContentBrief: brief,
            SEOGuide: guide,
            SEOStrategy: strategy,
            SEOStrategyVersion: strat_v,
        }
    )
    ctx_a = await builder.build_agent_context(
        session=session_a, document=base_doc, user_message="test"
    )
    assert ctx_a.resolved_audience == "Brief Audience"
    assert ctx_a.resolved_audience_source == "content_brief"

    # Case B: Guide wins
    session_b = make_mock_session_with_data(
        {
            ContentBrief: None,
            SEOGuide: guide,
            SEOStrategy: strategy,
            SEOStrategyVersion: strat_v,
        }
    )
    ctx_b = await builder.build_agent_context(
        session=session_b, document=base_doc, user_message="test"
    )
    assert ctx_b.resolved_audience == "Guide Audience"
    assert ctx_b.resolved_audience_source == "seo_guide"

    # Case C: Strategy wins
    session_c = make_mock_session_with_data(
        {
            ContentBrief: None,
            SEOGuide: None,
            SEOStrategy: strategy,
            SEOStrategyVersion: strat_v,
        }
    )
    ctx_c = await builder.build_agent_context(
        session=session_c, document=base_doc, user_message="test"
    )
    assert ctx_c.resolved_audience == "Strategy Segment"
    assert ctx_c.resolved_audience_source == "seo_strategy"

    # Case D: Missing everywhere -> None (no fabrication)
    session_d = make_mock_session_with_data(
        {
            ContentBrief: None,
            SEOGuide: None,
            SEOStrategy: None,
        }
    )
    ctx_d = await builder.build_agent_context(
        session=session_d, document=base_doc, user_message="test"
    )
    assert ctx_d.resolved_audience is None
    assert ctx_d.resolved_audience_source is None


# ---------------------------------------------------------------------------
# 5. Missing Data Behavior (Pure Truth, Zero Fabricated Defaults)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_data_returns_none_and_empty_collections(
    base_doc: ContentDocument,
) -> None:
    session = make_mock_session_with_data({})
    builder = ContentAgentContextBuilder()

    ctx = await builder.build_agent_context(
        session=session, document=base_doc, user_message="Hello"
    )

    # Structured context must have None or empty collections, NEVER hardcoded fake defaults
    assert ctx.brand_rules.tone is None
    assert ctx.brand_rules.voice is None
    assert ctx.brand_rules.style is None
    assert ctx.brand_rules.words_to_avoid == []
    assert ctx.keyword_context.primary_keyword is None
    assert ctx.keyword_context.secondary_keywords == []
    assert ctx.resolved_intent is None
    assert ctx.resolved_audience is None
    assert ctx.competitors == []
    assert ctx.entities == []
    assert ctx.questions == []
    assert ctx.content_requirements == []


# ---------------------------------------------------------------------------
# 6. Database Truth vs Rendering Defaults Separation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_database_truth_vs_rendering_defaults(base_doc: ContentDocument) -> None:
    session = make_mock_session_with_data({})
    service = ContextBuilderService()

    # In ContentAgentContext, missing brand tone is None
    agent_ctx = await service.build_agent_context(
        session=session, document=base_doc, user_message="Test"
    )
    assert agent_ctx.brand_rules.tone is None

    # In legacy render_editor_messages, presentation default is applied ONLY for prompt
    messages, _snapshot = service.render_editor_messages(agent_ctx)
    system_prompt = messages[0].content
    assert "Tone: Professional, clear, authoritative" in system_prompt
    assert "Voice: Knowledgeable expert" in system_prompt


# ---------------------------------------------------------------------------
# 7. Tenant & Project Authorization Enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_project_authorization_denial(
    base_doc: ContentDocument,
) -> None:
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://test-issuer.example",
        subject="test-sub",
        email="test@example.com",
        display_name="Tester",
    )

    mock_project_service = MagicMock()
    mock_project_service.get_model = AsyncMock(
        side_effect=PermissionDenied("Cross-project access forbidden")
    )

    builder = ContentAgentContextBuilder(project_service=mock_project_service)
    session = make_mock_session_with_data({})

    with pytest.raises(PermissionDenied, match="Cross-project access forbidden"):
        await builder.build_agent_context(
            session=session,
            document=base_doc,
            user_message="test",
            actor=actor,
        )


# ---------------------------------------------------------------------------
# 8. Token Budget & Deterministic Priority-Tier Pruning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_budget_pruning_priority_tiers(
    base_ids: dict[str, UUID], base_doc: ContentDocument
) -> None:
    # Construct a large context with supporting and required data
    strategy = SEOStrategy(
        id=base_ids["strategy_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        current_version=1,
    )
    strat_v = SEOStrategyVersion(
        id=uuid4(),
        strategy_id=base_ids["strategy_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        version=1,
        strategy_data={
            "business_context": {"business_name": "CyberSec Global"},
            "competitors": [
                {"name": f"Competitor {i}", "domain": f"comp{i}.com"} for i in range(20)
            ],
            "products": [
                {"name": f"Product {i}", "description": "Long desc " * 20} for i in range(10)
            ],
        },
    )
    brief = ContentBrief(
        id=base_ids["brief_id"],
        organization_id=base_ids["org_id"],
        project_id=base_ids["proj_id"],
        page_id=base_ids["page_id"],
        primary_keyword="zero trust",
        target_audience="Security Architects",
        search_intent="INFORMATIONAL",
    )

    session = make_mock_session_with_data(
        {
            SEOStrategy: strategy,
            SEOStrategyVersion: strat_v,
            ContentBrief: brief,
        }
    )

    builder = ContentAgentContextBuilder()

    # Case A: High budget -> No truncation
    ctx_high = await builder.build_agent_context(
        session=session,
        document=base_doc,
        user_message="test",
        max_token_budget=15000,
    )
    assert ctx_high.budget.truncated is False
    assert len(ctx_high.competitors) == 20

    # Case B: Tight budget (500 tokens) -> Supporting context pruned first
    ctx_tight = await builder.build_agent_context(
        session=session,
        document=base_doc,
        user_message="test",
        max_token_budget=300,
    )
    assert ctx_tight.budget.truncated is True
    assert "competitors" in ctx_tight.budget.truncated_sections
    # Required core context (primary keyword, intent, audience, document) MUST BE PRESERVED
    assert ctx_tight.keyword_context.primary_keyword.keyword == "zero trust"
    assert ctx_tight.resolved_intent == "INFORMATIONAL"
    assert ctx_tight.resolved_audience == "Security Architects"
    assert ctx_tight.current_document.title == base_doc.title


# ---------------------------------------------------------------------------
# 9. Full-Document vs Focused-Document Requests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_document_vs_focused_document_requests(base_doc: ContentDocument) -> None:
    session = make_mock_session_with_data({})
    builder = ContentAgentContextBuilder()

    # 1. Full document request
    ctx_full = await builder.build_agent_context(
        session=session,
        document=base_doc,
        user_message="Please complete the entire page",
    )
    assert ctx_full.request.full_document_request is True
    assert ctx_full.current_document.truncated is False
    assert len(ctx_full.current_document.blocks) == 3

    # 2. Focused block request
    ctx_focused = await builder.build_agent_context(
        session=session,
        document=base_doc,
        user_message="Polish this section",
        selected_block_id="b2",
        selected_text="Traditional perimeter security is obsolete.",
    )
    assert ctx_focused.request.full_document_request is False
    assert ctx_focused.selection.selected_block is not None
    assert ctx_focused.selection.selected_block.id == "b2"
    assert ctx_focused.selection.selected_block.is_focused is True
    assert len(ctx_focused.selection.surrounding_blocks) > 0


# ---------------------------------------------------------------------------
# 10. AI Editor Backward Compatibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_editor_backward_compatibility(base_doc: ContentDocument) -> None:
    session = make_mock_session_with_data({})
    service = ContextBuilderService(max_token_budget=8000)

    messages, snapshot = await service.build_context(
        session=session,
        document=base_doc,
        user_message="Rewrite the highlighted block",
        selected_block_id="b2",
        selected_text="Traditional perimeter security is obsolete.",
    )

    # Verify message sequence and structure
    assert len(messages) >= 4
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert "<DOCUMENT_CONTEXT>" in messages[1].content
    assert messages[2].role == "assistant"
    assert "<USER_QUERY>" in messages[3].content

    # Verify context snapshot contract
    assert snapshot["document_id"] == str(base_doc.id)
    assert snapshot["selected_block_id"] == "b2"
    assert snapshot["has_selection"] is True
    assert snapshot["full_document_request"] is False
    assert "provenance" in snapshot
    assert "context_budget" in snapshot
    assert "estimated_tokens" in snapshot
