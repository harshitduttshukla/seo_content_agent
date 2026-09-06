"""API integration tests for Phase 4: Content Map, Planned Pages, SEO Guides,
and Internal Linking."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.core.errors import PermissionDenied
from app.domains.content.models import PageContentType, PageType, PlannedPageStatus
from app.domains.content.schemas import (
    PlannedContentPageDetail,
    PlannedContentPageList,
)
from app.domains.content_map.models import ContentMapNodeType
from app.domains.content_map.schemas import (
    ContentMapGraphResponse,
    ContentMapNodeData,
    ContentMapNodeDTO,
    ContentMapStats,
    ContentMapValidationResponse,
)
from app.domains.internal_linking.schemas import (
    LinkOpportunityDetail,
    LinkOpportunityList,
    OrphanPageList,
)
from app.domains.seo.schemas import (
    SEOGuideDetail,
    SEOGuideOutlineSection,
    SEOGuideVersionDetail,
    SEOGuideVersionList,
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
        app_env="testing",
        jwt_secret_key="test-secret-key-that-is-at-least-32-chars",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        redis_url="redis://localhost:6379/0",
    )
    app = create_app(settings)
    app.state.token_verifier = MockTokenVerifier()
    return app


@pytest.fixture
def test_actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-user-sub",
        email="tester@example.com",
        display_name="Tester",
    )


@pytest.mark.asyncio
async def test_planned_pages_crud_api(test_app: FastAPI, test_actor: AuthenticatedUser) -> None:
    project_id = uuid4()
    page_id = uuid4()
    org_id = uuid4()

    mock_page = PlannedContentPageDetail(
        id=page_id,
        organization_id=org_id,
        project_id=project_id,
        title="Zero Trust Network Architecture",
        slug="zero-trust-network-architecture",
        url="/zero-trust-network-architecture",
        page_type=PageType.PLANNED.value,
        content_type=PageContentType.CLUSTER_PAGE.value,
        status=PlannedPageStatus.PLANNED.value,
        intent="INFORMATIONAL",
        primary_keyword="zero trust network architecture",
        business_value=85.0,
        priority=1,
        inbound_links_count=0,
        outbound_links_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
            return_value=test_actor,
        ),
        patch(
            "app.domains.content.service.ContentService.list_planned_pages",
            new_callable=AsyncMock,
            return_value=PlannedContentPageList(items=[mock_page], total=1),
        ),
        patch(
            "app.domains.content.service.ContentService.create_planned_page",
            new_callable=AsyncMock,
            return_value=mock_page,
        ),
        patch(
            "app.domains.content.service.ContentService.get_planned_page",
            new_callable=AsyncMock,
            return_value=mock_page,
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            # 1. List planned pages
            res = await client.get(f"/api/v1/projects/{project_id}/content-pages")
            assert res.status_code == 200
            data = res.json()["data"]
            assert len(data["items"]) == 1
            assert data["items"][0]["title"] == "Zero Trust Network Architecture"

            # 2. Create planned page
            res = await client.post(
                f"/api/v1/projects/{project_id}/content-pages",
                json={
                    "title": "Zero Trust Network Architecture",
                    "slug": "zero-trust-network-architecture",
                    "page_type": "PLANNED",
                    "content_type": "CLUSTER_PAGE",
                    "primary_keyword": "zero trust network architecture",
                },
            )
            assert res.status_code == 201
            assert res.json()["data"]["slug"] == "zero-trust-network-architecture"

            # 3. Get single planned page
            res = await client.get(f"/api/v1/content-pages/{page_id}")
            assert res.status_code == 200
            assert res.json()["data"]["id"] == str(page_id)


@pytest.mark.asyncio
async def test_content_map_graph_api(test_app: FastAPI, test_actor: AuthenticatedUser) -> None:
    project_id = uuid4()
    mock_graph = ContentMapGraphResponse(
        nodes=[
            ContentMapNodeDTO(
                id="pillar-1",
                type="pillar",
                data=ContentMapNodeData(
                    entity_id=uuid4(),
                    node_type=ContentMapNodeType.PILLAR.value,
                    title="Security Architecture",
                    label="Security Architecture",
                ),
            )
        ],
        edges=[],
        graph_revision=1,
        stats=ContentMapStats(
            total_pillars=1,
            total_topics=2,
            total_clusters=5,
            planned_pages=8,
            existing_pages=12,
            orphan_pages=0,
            cannibalization_warnings=0,
            total_pages=20,
        ),
    )

    mock_validation = ContentMapValidationResponse(
        is_valid=True,
        issues=[],
        total_issues=0,
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
            return_value=test_actor,
        ),
        patch(
            "app.domains.content_map.service.ContentMapService.get_content_map",
            new_callable=AsyncMock,
            return_value=mock_graph,
        ),
        patch(
            "app.domains.content_map.service.ContentMapService.validate_architecture",
            new_callable=AsyncMock,
            return_value=mock_validation,
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            # Graph
            res = await client.get(f"/api/v1/projects/{project_id}/content-map")
            assert res.status_code == 200
            assert len(res.json()["data"]["nodes"]) == 1

            # Validation
            res = await client.get(f"/api/v1/projects/{project_id}/content-map/validation")
            assert res.status_code == 200
            assert res.json()["data"]["is_valid"] is True


@pytest.mark.asyncio
async def test_seo_guide_and_approval_api(test_app: FastAPI, test_actor: AuthenticatedUser) -> None:
    project_id = uuid4()
    page_id = uuid4()
    guide_id = uuid4()
    org_id = uuid4()

    mock_guide = SEOGuideDetail(
        id=guide_id,
        organization_id=org_id,
        project_id=project_id,
        page_id=page_id,
        version=1,
        status="DRAFT",
        primary_keyword="kubernetes threat modeling",
        secondary_keywords=["k8s security", "container vulnerabilities"],
        search_intent="INFORMATIONAL",
        target_audience="Security Architects",
        recommended_title="Complete Kubernetes Threat Modeling Guide",
        meta_title="Kubernetes Threat Modeling: Complete Guide & Best Practices",
        meta_description=(
            "Learn how to perform threat modeling on Kubernetes clusters "
            "with step-by-step frameworks."
        ),
        recommended_url="kubernetes-threat-modeling-guide",
        content_type="GUIDE",
        word_count_target=2500,
        required_topics=["STRIDE", "RBAC", "Pod Security"],
        key_entities=["Kubernetes", "API Server", "Kubelet"],
        serp_notes="Top 3 rankings lack container breakout attack scenarios.",
        content_requirements=["Include original threat vector diagram."],
        outline=[
            SEOGuideOutlineSection(
                level=1, title="Kubernetes Threat Modeling Guide", required=True
            ),
            SEOGuideOutlineSection(level=2, title="STRIDE Methodology on K8s", required=True),
        ],
        seo_rules={"min_h2_count": 4},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    approved_guide = SEOGuideDetail(
        **{**mock_guide.model_dump(), "status": "APPROVED", "version": 2}
    )

    mock_version = SEOGuideVersionDetail(
        id=uuid4(),
        guide_id=guide_id,
        page_id=page_id,
        version=2,
        snapshot_data={"primary_keyword": "kubernetes threat modeling"},
        change_summary="Approved and locked guidelines for writing team.",
        created_by_id=test_actor.user_id,
        created_at=datetime.now(UTC),
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
            return_value=test_actor,
        ),
        patch(
            "app.domains.seo.service.SEOGuideService.get_or_create_guide",
            new_callable=AsyncMock,
            return_value=mock_guide,
        ),
        patch(
            "app.domains.seo.service.SEOGuideService.approve_guide",
            new_callable=AsyncMock,
            return_value=approved_guide,
        ),
        patch(
            "app.domains.seo.service.SEOGuideService.list_versions",
            new_callable=AsyncMock,
            return_value=SEOGuideVersionList(items=[mock_version]),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            # 1. Get SEO Guide
            res = await client.get(f"/api/v1/content-pages/{page_id}/seo-guide")
            assert res.status_code == 200
            assert res.json()["data"]["primary_keyword"] == "kubernetes threat modeling"

            # 2. Approve SEO Guide
            res = await client.post(f"/api/v1/content-pages/{page_id}/seo-guide/approve")
            assert res.status_code == 200
            assert res.json()["data"]["version"] == 2
            assert res.json()["data"]["status"] == "APPROVED"

            # 3. List SEO Guide Versions
            res = await client.get(f"/api/v1/content-pages/{page_id}/seo-guide/versions")
            assert res.status_code == 200
            assert len(res.json()["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_internal_linking_opportunities_and_governance(
    test_app: FastAPI, test_actor: AuthenticatedUser
) -> None:
    project_id = uuid4()
    opp_id = uuid4()
    source_id = uuid4()
    target_id = uuid4()
    org_id = uuid4()

    mock_opp = LinkOpportunityDetail(
        id=opp_id,
        organization_id=org_id,
        project_id=project_id,
        source_page_id=source_id,
        source_page_title="Kubernetes Security Overview",
        target_page_id=target_id,
        target_page_title="Threat Modeling Guide",
        target_page_url="threat-modeling-guide",
        anchor_suggestion="Kubernetes threat modeling",
        confidence=0.92,
        priority=1,
        reason="Contextual parent-to-supporting semantic match",
        status="PROPOSED",
        created_at=datetime.now(UTC),
    )

    approved_opp = LinkOpportunityDetail(**{**mock_opp.model_dump(), "status": "APPROVED"})

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
            return_value=test_actor,
        ),
        patch(
            "app.domains.internal_linking.service.InternalLinkingService.list_opportunities",
            new_callable=AsyncMock,
            return_value=LinkOpportunityList(items=[mock_opp]),
        ),
        patch(
            "app.domains.internal_linking.service.InternalLinkingService.approve_opportunity",
            new_callable=AsyncMock,
            return_value=approved_opp,
        ),
        patch(
            "app.domains.internal_linking.service.InternalLinkingService.detect_orphan_pages",
            new_callable=AsyncMock,
            return_value=OrphanPageList(items=[]),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            # List opportunities
            res = await client.get(f"/api/v1/projects/{project_id}/link-opportunities")
            assert res.status_code == 200
            assert len(res.json()["data"]["items"]) == 1

            # Approve opportunity
            res = await client.post(
                f"/api/v1/projects/{project_id}/link-opportunities/{opp_id}/approve"
            )
            assert res.status_code == 200
            assert res.json()["data"]["status"] == "APPROVED"

            # Check orphans
            res = await client.get(f"/api/v1/projects/{project_id}/orphan-pages")
            assert res.status_code == 200
            assert res.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_tenant_isolation_negative_denial(
    test_app: FastAPI, test_actor: AuthenticatedUser
) -> None:
    """Mandatory negative test: Accessing resources across tenants returns 403 Forbidden."""
    foreign_project_id = uuid4()

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
            return_value=test_actor,
        ),
        patch(
            "app.domains.content.service.ContentService.list_planned_pages",
            side_effect=PermissionDenied("Cross-tenant access forbidden."),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            res = await client.get(f"/api/v1/projects/{foreign_project_id}/content-pages")
            assert res.status_code == 403
            assert res.json()["errors"][0]["code"] == "PERMISSION_DENIED"
