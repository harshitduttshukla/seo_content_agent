"""Regression tests for Phase 4 application-service workflows."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.domains.audit.repository import AuditWriter
from app.domains.content.models import PlannedContentPage
from app.domains.content.schemas import PlannedContentPageCreate, PlannedContentPageDetail
from app.domains.content.service import ContentService
from app.domains.seo.models import SEOGuide, SEOGuideVersion
from app.domains.seo.service import SEOGuideService
from app.security.principal import AuthenticatedUser, PermissionCode


def make_mock_session() -> MagicMock:
    session = MagicMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    session.begin.return_value = context_manager
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_planned_page_records_audit_event() -> None:
    service = ContentService()
    session = make_mock_session()
    project_id = uuid4()
    organization_id = uuid4()
    page_id = uuid4()
    cluster_id = uuid4()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-user-sub",
        email="tester@example.com",
        display_name="Tester",
    )
    project = SimpleNamespace(id=project_id, organization_id=organization_id)
    audit = MagicMock(spec=AuditWriter)

    async def create_page(_session: MagicMock, page: PlannedContentPage) -> PlannedContentPage:
        page.id = page_id
        page.created_at = datetime.now(UTC)
        page.updated_at = datetime.now(UTC)
        return page

    service._projects.get_model = AsyncMock(return_value=project)  # type: ignore[method-assign]
    service._content.get_planned_page_by_slug = AsyncMock(  # type: ignore[method-assign]
        return_value=None
    )
    service._content.create_planned_page = AsyncMock(  # type: ignore[method-assign]
        side_effect=create_page
    )
    service._content.list_page_keywords = AsyncMock(return_value=[])  # type: ignore[method-assign]
    service._keywords.get_cluster_by_id = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(cluster_name="SEO")
    )
    service._audit = audit

    with patch("app.domains.content.service.set_actor_context", new_callable=AsyncMock):
        result = await service.create_planned_page(
            session,
            actor=actor,
            project_id=project_id,
            payload=PlannedContentPageCreate(
                title="SEO Audit Guide",
                slug="seo-audit-guide",
                content_type="CLUSTER_PAGE",
                primary_keyword="seo audit",
                cluster_id=cluster_id,
            ),
            request_id="req_create_page",
        )

    assert isinstance(result, PlannedContentPageDetail)
    assert result.cluster_id == cluster_id
    assert result.cluster_name == "SEO"
    service._keywords.get_cluster_by_id.assert_awaited_once_with(
        session,
        cluster_id=cluster_id,
        project_id=project_id,
    )
    audit.add.assert_called_once_with(
        session,
        organization_id=organization_id,
        project_id=project_id,
        actor_user_id=actor.user_id,
        action="content.planned_page.create",
        resource_type="planned_content_page",
        resource_id=page_id,
        outcome="success",
        request_id="req_create_page",
        metadata={"title": "SEO Audit Guide", "slug": "seo-audit-guide"},
    )


@pytest.mark.asyncio
async def test_create_seo_guide_reads_audience_from_latest_strategy_version() -> None:
    service = SEOGuideService()
    session = make_mock_session()
    project_id = uuid4()
    organization_id = uuid4()
    page_id = uuid4()
    guide_id = uuid4()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-user-sub",
        email="tester@example.com",
        display_name="Tester",
    )
    page = SimpleNamespace(
        id=page_id,
        organization_id=organization_id,
        project_id=project_id,
        title="Enterprise SEO Guide",
        slug="enterprise-seo-guide",
        url=None,
        content_type="GUIDE",
        primary_keyword="enterprise seo",
        intent="INFORMATIONAL",
    )
    strategy = SimpleNamespace(id=uuid4())
    strategy_version = SimpleNamespace(
        strategy_data={
            "audience": {
                "segments": ["SEO leaders", "Content operations teams"],
                "personas": [],
            }
        }
    )
    now = datetime.now(UTC)

    async def create_guide(_session: MagicMock, guide: SEOGuide) -> SEOGuide:
        guide.id = guide_id
        guide.created_at = now
        guide.updated_at = now
        guide.revision = 1
        return guide

    service._content.get_planned_page_by_id = AsyncMock(return_value=page)  # type: ignore[method-assign]
    service._projects.get_model = AsyncMock(return_value=SimpleNamespace(id=project_id))  # type: ignore[method-assign]
    service._seo.get_guide_by_page_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._strategy.get_by_project_id = AsyncMock(return_value=strategy)  # type: ignore[method-assign]
    service._strategy.get_latest_version = AsyncMock(return_value=strategy_version)  # type: ignore[method-assign]
    service._content.list_page_keywords = AsyncMock(return_value=[])  # type: ignore[method-assign]
    service._seo.create_guide = AsyncMock(side_effect=create_guide)  # type: ignore[method-assign]
    service._seo.create_version = AsyncMock()  # type: ignore[method-assign]

    with patch("app.domains.seo.service.set_actor_context", new_callable=AsyncMock):
        result = await service.get_or_create_guide(
            session,
            actor=actor,
            page_id=page_id,
        )

    assert result.id == guide_id
    assert result.target_audience == "SEO leaders, Content operations teams"
    service._projects.get_model.assert_awaited_once_with(
        session,
        actor=actor,
        project_id=project_id,
        permission=PermissionCode.SEO_READ,
    )
    service._strategy.get_latest_version.assert_awaited_once_with(
        session,
        strategy_id=strategy.id,
    )
    create_guide_call = service._seo.create_guide.await_args
    assert create_guide_call is not None
    session.refresh.assert_awaited_once_with(create_guide_call.args[1])

    create_version_call = service._seo.create_version.await_args
    assert create_version_call is not None
    version = create_version_call.args[1]
    assert isinstance(version, SEOGuideVersion)
    assert version.snapshot_data["id"] == str(guide_id)
    assert version.snapshot_data["page_id"] == str(page_id)
    assert version.snapshot_data["target_audience"] == result.target_audience
