"""API tests for Phase 3: Strategy, Keywords, Clusters, and Architecture routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.content.schemas import (
    CannibalizationWarningDetail,
    CannibalizationWarningList,
    ContentArchitectureGraphNode,
    ContentArchitectureGraphResponse,
    ContentOpportunityDetail,
    ContentOpportunityList,
    ContentPillarDetail,
    ContentPillarList,
    GraphNodeData,
    KeywordPageMappingDetail,
    KeywordPageMappingList,
    MappingAnalysisResponse,
    TopicDetail,
    TopicList,
)
from app.domains.keywords.schemas import (
    ClusteringRunResponse,
    KeywordClusterDetail,
    KeywordClusterList,
    KeywordClusterMemberDetail,
    KeywordDetail,
    KeywordImportResponse,
    KeywordList,
)
from app.domains.strategy.schemas import (
    StrategyDataSchema,
    StrategyResponse,
    StrategyVersionListResponse,
    StrategyVersionResponse,
)
from app.main import create_app
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class MockTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://identity.example.com",
            subject="test-user-sub",
            email="tester@example.com",
            display_name="Tester",
        )


@pytest.fixture
def test_app() -> FastAPI:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
    )
    engine = AsyncMock()
    return create_app(settings, engine=engine, token_verifier=MockTokenVerifier())


@pytest.mark.asyncio
async def test_strategy_endpoints(test_app: FastAPI) -> None:
    user_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    strat_id = uuid4()

    mock_strat = StrategyResponse(
        id=strat_id,
        organization_id=org_id,
        project_id=project_id,
        current_version=1,
        status="active",
        strategy_data=StrategyDataSchema(),
        change_summary="Initial setup",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
            return_value=AuthenticatedUser(
                user_id=user_id,
                issuer="https://identity.example.com",
                subject="test-user-sub",
                email="tester@example.com",
                display_name="Tester",
            ),
        ),
        patch(
            "app.domains.strategy.service.SEOStrategyService.get_or_create_strategy",
            new_callable=AsyncMock,
            return_value=mock_strat,
        ),
        patch(
            "app.domains.strategy.service.SEOStrategyService.update_strategy",
            new_callable=AsyncMock,
            return_value=mock_strat,
        ),
        patch(
            "app.domains.strategy.service.SEOStrategyService.list_versions",
            new_callable=AsyncMock,
            return_value=StrategyVersionListResponse(
                items=[
                    StrategyVersionResponse(
                        id=uuid4(),
                        strategy_id=strat_id,
                        organization_id=org_id,
                        project_id=project_id,
                        version=1,
                        created_by_id=user_id,
                        change_summary="Initial setup",
                        strategy_data=StrategyDataSchema(),
                        created_at=datetime.now(UTC),
                    )
                ]
            ),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            headers = {"Authorization": "Bearer fake_token"}

            # Get Strategy
            res = await ac.get(f"/api/v1/projects/{project_id}/strategy", headers=headers)
            assert res.status_code == 200
            assert res.json()["data"]["current_version"] == 1

            # Update Strategy
            payload = {
                "change_summary": "Added B2B goals",
                "strategy_data": {"business_summary": "Enterprise SEO Platform"},
            }
            res = await ac.put(
                f"/api/v1/projects/{project_id}/strategy",
                json=payload,
                headers=headers,
            )
            assert res.status_code == 200

            # List Versions
            res = await ac.get(
                f"/api/v1/projects/{project_id}/strategy/versions",
                headers=headers,
            )
            assert res.status_code == 200
            assert len(res.json()["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_keywords_and_clusters_endpoints(test_app: FastAPI) -> None:
    user_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    kw_id = uuid4()
    cluster_id = uuid4()

    mock_kw = KeywordDetail(
        id=kw_id,
        organization_id=org_id,
        project_id=project_id,
        website_id=None,
        keyword="best b2b seo tools",
        normalized_keyword="best b2b seo tools",
        search_volume=1800,
        keyword_difficulty=42.0,
        cpc=6.50,
        intent="COMMERCIAL",
        intent_confidence=0.88,
        funnel_stage="MOFU",
        business_value_score=85.0,
        priority_score=78.0,
        source="MANUAL",
        status="active",
        provider_metadata={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_cluster = KeywordClusterDetail(
        id=cluster_id,
        organization_id=org_id,
        project_id=project_id,
        topic_id=None,
        clustering_run_id=uuid4(),
        cluster_name="B2B SEO Tools",
        primary_keyword_id=kw_id,
        primary_keyword="best b2b seo tools",
        intent="COMMERCIAL",
        cluster_score=82.5,
        status="proposed",
        rationale="Semantic grouping",
        member_count=1,
        members=[
            KeywordClusterMemberDetail(
                id=uuid4(),
                keyword_id=kw_id,
                keyword="best b2b seo tools",
                search_volume=1800,
                keyword_difficulty=42.0,
                cpc=6.50,
                intent="COMMERCIAL",
                priority_score=78.0,
                business_value_score=85.0,
                is_primary=True,
                similarity_score=1.0,
            )
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
            return_value=AuthenticatedUser(
                user_id=user_id,
                issuer="https://identity.example.com",
                subject="test-user-sub",
                email="tester@example.com",
                display_name="Tester",
            ),
        ),
        patch(
            "app.domains.keywords.service.KeywordService.create_keyword",
            new_callable=AsyncMock,
            return_value=mock_kw,
        ),
        patch(
            "app.domains.keywords.service.KeywordService.list_keywords",
            new_callable=AsyncMock,
            return_value=KeywordList(items=[mock_kw], total_count=1),
        ),
        patch(
            "app.domains.keywords.service.KeywordService.import_csv",
            new_callable=AsyncMock,
            return_value=KeywordImportResponse(
                id=uuid4(),
                organization_id=org_id,
                project_id=project_id,
                filename="test.csv",
                source="CSV",
                total_rows=10,
                valid_rows=10,
                invalid_rows=0,
                duplicate_rows=0,
                created_rows=10,
                updated_rows=0,
                status="completed",
                error_summary=None,
                created_by_id=user_id,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            ),
        ),
        patch(
            "app.domains.keywords.service.KeywordService.run_clustering",
            new_callable=AsyncMock,
            return_value=ClusteringRunResponse(
                id=uuid4(),
                organization_id=org_id,
                project_id=project_id,
                status="completed",
                algorithm_version="keyword_cluster_v1",
                parameters={"similarity_threshold": 0.5},
                keyword_count=1,
                cluster_count=1,
                error=None,
                created_by_id=user_id,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
            ),
        ),
        patch(
            "app.domains.keywords.service.KeywordService.list_clusters",
            new_callable=AsyncMock,
            return_value=KeywordClusterList(items=[mock_cluster]),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            headers = {"Authorization": "Bearer fake_token"}

            # Create keyword
            res = await ac.post(
                f"/api/v1/projects/{project_id}/keywords",
                json={"keyword": "best b2b seo tools", "search_volume": 1800},
                headers=headers,
            )
            assert res.status_code == 201
            assert res.json()["data"]["keyword"] == "best b2b seo tools"

            # List keywords
            res = await ac.get(f"/api/v1/projects/{project_id}/keywords", headers=headers)
            assert res.status_code == 200
            assert len(res.json()["data"]["items"]) == 1

            # Import CSV
            files = {"file": ("test.csv", b"keyword,volume\nseo tools,1000", "text/csv")}
            res = await ac.post(
                f"/api/v1/projects/{project_id}/keywords/import",
                files=files,
                headers=headers,
            )
            assert res.status_code == 201
            assert res.json()["data"]["status"] == "completed"

            # Run clustering
            res = await ac.post(
                f"/api/v1/projects/{project_id}/clustering-runs",
                json={"similarity_threshold": 0.5},
                headers=headers,
            )
            assert res.status_code == 201

            # List clusters
            res = await ac.get(f"/api/v1/projects/{project_id}/clusters", headers=headers)
            assert res.status_code == 200
            assert len(res.json()["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_architecture_and_opportunities_endpoints(test_app: FastAPI) -> None:
    user_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    website_id = uuid4()
    pillar_id = uuid4()
    topic_id = uuid4()

    mock_pillar = ContentPillarDetail(
        id=pillar_id,
        organization_id=org_id,
        project_id=project_id,
        name="SEO Intelligence",
        slug="seo-intelligence",
        description="Comprehensive guides to content architecture",
        business_goal="Drive organic demos",
        priority=1,
        status="proposed",
        topic_count=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_topic = TopicDetail(
        id=topic_id,
        organization_id=org_id,
        project_id=project_id,
        pillar_id=pillar_id,
        pillar_name="SEO Intelligence",
        name="Keyword Clustering",
        slug="keyword-clustering",
        description="Techniques for deterministic keyword grouping",
        priority=1,
        status="proposed",
        cluster_count=2,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
            return_value=AuthenticatedUser(
                user_id=user_id,
                issuer="https://identity.example.com",
                subject="test-user-sub",
                email="tester@example.com",
                display_name="Tester",
            ),
        ),
        patch(
            "app.domains.content.service.ContentService.create_pillar",
            new_callable=AsyncMock,
            return_value=mock_pillar,
        ),
        patch(
            "app.domains.content.service.ContentService.list_pillars",
            new_callable=AsyncMock,
            return_value=ContentPillarList(items=[mock_pillar]),
        ),
        patch(
            "app.domains.content.service.ContentService.create_topic",
            new_callable=AsyncMock,
            return_value=mock_topic,
        ),
        patch(
            "app.domains.content.service.ContentService.list_topics",
            new_callable=AsyncMock,
            return_value=TopicList(items=[mock_topic]),
        ),
        patch(
            "app.domains.content.service.ContentService.analyze_keyword_mappings",
            new_callable=AsyncMock,
            return_value=MappingAnalysisResponse(
                total_keywords=10,
                mapped_count=8,
                unmapped_count=2,
                new_mappings_created=10,
                updated_mappings=0,
            ),
        ),
        patch(
            "app.domains.content.service.ContentService.list_mappings",
            new_callable=AsyncMock,
            return_value=KeywordPageMappingList(
                items=[
                    KeywordPageMappingDetail(
                        id=uuid4(),
                        organization_id=org_id,
                        project_id=project_id,
                        website_id=website_id,
                        keyword_id=uuid4(),
                        keyword="keyword clustering",
                        search_volume=1200,
                        intent="INFORMATIONAL",
                        page_id=uuid4(),
                        page_url="https://example.com/keyword-clustering",
                        page_title="Keyword Clustering Guide",
                        mapping_type="PRIMARY_TARGET",
                        confidence=0.95,
                        source="DETERMINISTIC",
                        status="proposed",
                        rationale="URL and Title match",
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                ]
            ),
        ),
        patch(
            "app.domains.content.service.ContentService.detect_cannibalization",
            new_callable=AsyncMock,
            return_value=CannibalizationWarningList(
                items=[
                    CannibalizationWarningDetail(
                        keyword_id=uuid4(),
                        keyword="seo audit",
                        intent="INFORMATIONAL",
                        competing_pages=[
                            {
                                "page_id": str(uuid4()),
                                "url": "https://example.com/seo-audit",
                                "title": "SEO Audit Checklist",
                            },
                            {
                                "page_id": str(uuid4()),
                                "url": "https://example.com/audit-tools",
                                "title": "SEO Audit Software",
                            },
                        ],
                        severity="HIGH",
                        reason="2 pages competing for 'seo audit'",
                    )
                ]
            ),
        ),
        patch(
            "app.domains.content.service.ContentService.list_opportunities",
            new_callable=AsyncMock,
            return_value=ContentOpportunityList(
                items=[
                    ContentOpportunityDetail(
                        id=uuid4(),
                        organization_id=org_id,
                        project_id=project_id,
                        website_id=website_id,
                        cluster_id=uuid4(),
                        cluster_name="Content Operations",
                        keyword_id=uuid4(),
                        keyword="content operations guide",
                        action="NEW_PAGE",
                        priority=85.0,
                        business_value_score=75.0,
                        existing_page_id=None,
                        existing_page_url=None,
                        reason="No page exists covering this cluster",
                        confidence=0.90,
                        status="proposed",
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                ]
            ),
        ),
        patch(
            "app.domains.content.service.ContentService.get_architecture_graph",
            new_callable=AsyncMock,
            return_value=ContentArchitectureGraphResponse(
                nodes=[
                    ContentArchitectureGraphNode(
                        id=f"pillar-{pillar_id}",
                        type="pillar",
                        data=GraphNodeData(label="SEO Intelligence", subtitle="Pillar"),
                    )
                ],
                edges=[],
            ),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            headers = {"Authorization": "Bearer fake_token"}

            # Pillars
            res = await ac.post(
                f"/api/v1/projects/{project_id}/content-pillars",
                json={"name": "SEO Intelligence", "description": "Pillar desc"},
                headers=headers,
            )
            assert res.status_code == 201

            res = await ac.get(
                f"/api/v1/projects/{project_id}/content-pillars",
                headers=headers,
            )
            assert res.status_code == 200
            assert len(res.json()["data"]["items"]) == 1

            # Topics
            res = await ac.post(
                f"/api/v1/projects/{project_id}/topics",
                json={"name": "Keyword Clustering", "pillar_id": str(pillar_id)},
                headers=headers,
            )
            assert res.status_code == 201

            # Analyze mappings
            res = await ac.post(
                f"/api/v1/projects/{project_id}/keyword-mappings/analyze?website_id={website_id}",
                headers=headers,
            )
            assert res.status_code == 200
            assert res.json()["data"]["mapped_count"] == 8

            # Cannibalization
            res = await ac.get(
                f"/api/v1/projects/{project_id}/cannibalization-warnings?website_id={website_id}",
                headers=headers,
            )
            assert res.status_code == 200
            assert len(res.json()["data"]["items"]) == 1

            # Opportunities
            res = await ac.get(
                f"/api/v1/projects/{project_id}/content-opportunities",
                headers=headers,
            )
            assert res.status_code == 200
            assert len(res.json()["data"]["items"]) == 1

            # Architecture Graph
            res = await ac.get(
                f"/api/v1/projects/{project_id}/content-architecture/graph",
                headers=headers,
            )
            assert res.status_code == 200
            assert len(res.json()["data"]["nodes"]) == 1
