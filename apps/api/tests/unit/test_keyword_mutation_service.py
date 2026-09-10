"""Keyword edit and deletion service regression tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.core.errors import DomainError, ResourceNotFound
from app.domains.audit.repository import AuditWriter
from app.domains.keywords.intent import calculate_business_value, calculate_priority_score
from app.domains.keywords.schemas import KeywordUpdate
from app.domains.keywords.service import KeywordService
from app.security.principal import AuthenticatedUser, PermissionCode


def make_mock_session() -> MagicMock:
    session = MagicMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    session.begin.return_value = context_manager
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


def make_actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-user-sub",
        email="tester@example.com",
        display_name="Tester",
    )


def make_keyword(*, project_id: object, organization_id: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        website_id=None,
        keyword="seo",
        normalized_keyword="seo",
        search_volume=1000,
        keyword_difficulty=30.0,
        cpc=2.5,
        intent="INFORMATIONAL",
        intent_confidence=0.6,
        funnel_stage="TOFU",
        business_value_score=44.4,
        priority_score=56.0,
        source="MANUAL",
        status="active",
        provider_metadata={},
        revision=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_keyword_renames_recalculates_and_audits() -> None:
    service = KeywordService()
    session = make_mock_session()
    actor = make_actor()
    project_id = uuid4()
    organization_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=organization_id)
    keyword = make_keyword(project_id=project_id, organization_id=organization_id)
    audit = MagicMock(spec=AuditWriter)

    service._projects.get_model = AsyncMock(return_value=project)  # type: ignore[method-assign]
    service._repository.get_by_id = AsyncMock(return_value=keyword)  # type: ignore[method-assign]
    service._repository.get_by_normalized = AsyncMock(  # type: ignore[method-assign]
        return_value=None
    )
    service._get_strategy_terms = AsyncMock(return_value=[])  # type: ignore[method-assign]
    service._audit = audit

    payload = KeywordUpdate(
        keyword="enterprise seo",
        search_volume=2000,
        keyword_difficulty=25,
        cpc=4.0,
        intent="COMMERCIAL",
        funnel_stage="MOFU",
        status="active",
    )
    with patch("app.domains.keywords.service.set_actor_context", new_callable=AsyncMock):
        result = await service.update_keyword(
            session,
            actor=actor,
            project_id=project_id,
            keyword_id=keyword.id,
            payload=payload,
            request_id="req_update_keyword",
        )

    expected_business_value = calculate_business_value(
        "COMMERCIAL",
        cpc=4.0,
        keyword="enterprise seo",
        strategy_terms=[],
    )
    assert result.keyword == "enterprise seo"
    assert result.normalized_keyword == "enterprise seo"
    assert result.business_value_score == expected_business_value
    assert result.priority_score == calculate_priority_score(
        2000,
        25,
        expected_business_value,
        "COMMERCIAL",
    )
    service._repository.get_by_normalized.assert_awaited_once_with(
        session,
        project_id=project_id,
        normalized_keyword="enterprise seo",
    )
    session.flush.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(keyword)
    audit.add.assert_called_once_with(
        session,
        actor_user_id=actor.user_id,
        organization_id=organization_id,
        project_id=project_id,
        action="keyword.updated",
        resource_type="keyword",
        resource_id=keyword.id,
        request_id="req_update_keyword",
        metadata={"old_keyword": "seo", "keyword": "enterprise seo"},
    )


@pytest.mark.asyncio
async def test_update_keyword_rejects_duplicate_normalized_value() -> None:
    service = KeywordService()
    session = make_mock_session()
    actor = make_actor()
    project_id = uuid4()
    organization_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=organization_id)
    keyword = make_keyword(project_id=project_id, organization_id=organization_id)

    service._projects.get_model = AsyncMock(return_value=project)  # type: ignore[method-assign]
    service._repository.get_by_id = AsyncMock(return_value=keyword)  # type: ignore[method-assign]
    service._repository.get_by_normalized = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(id=uuid4())
    )

    with (
        patch("app.domains.keywords.service.set_actor_context", new_callable=AsyncMock),
        pytest.raises(DomainError) as exc_info,
    ):
        await service.update_keyword(
            session,
            actor=actor,
            project_id=project_id,
            keyword_id=keyword.id,
            payload=KeywordUpdate(keyword="Existing Keyword"),
        )

    assert exc_info.value.code == "KEYWORD_DUPLICATE"


@pytest.mark.asyncio
async def test_delete_keyword_is_project_scoped_and_audited() -> None:
    service = KeywordService()
    session = make_mock_session()
    actor = make_actor()
    project_id = uuid4()
    organization_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=organization_id)
    keyword = make_keyword(project_id=project_id, organization_id=organization_id)
    audit = MagicMock(spec=AuditWriter)

    service._projects.get_model = AsyncMock(return_value=project)  # type: ignore[method-assign]
    service._repository.get_by_id = AsyncMock(return_value=keyword)  # type: ignore[method-assign]
    service._repository.delete_keyword = AsyncMock()  # type: ignore[method-assign]
    service._audit = audit

    with patch("app.domains.keywords.service.set_actor_context", new_callable=AsyncMock):
        result = await service.delete_keyword(
            session,
            actor=actor,
            project_id=project_id,
            keyword_id=keyword.id,
            request_id="req_delete_keyword",
        )

    service._projects.get_model.assert_awaited_once_with(
        session,
        actor=actor,
        project_id=project_id,
        permission=PermissionCode.KEYWORD_WRITE,
    )
    service._repository.get_by_id.assert_awaited_once_with(
        session,
        keyword_id=keyword.id,
        project_id=project_id,
    )
    service._repository.delete_keyword.assert_awaited_once_with(
        session,
        keyword_id=keyword.id,
        project_id=project_id,
    )
    audit.add.assert_called_once_with(
        session,
        actor_user_id=actor.user_id,
        organization_id=organization_id,
        project_id=project_id,
        action="keyword.deleted",
        resource_type="keyword",
        resource_id=keyword.id,
        request_id="req_delete_keyword",
        metadata={"keyword": "seo"},
    )
    assert result.keyword_id == keyword.id
    assert result.keyword == "seo"


@pytest.mark.asyncio
async def test_delete_keyword_denies_keyword_outside_project_scope() -> None:
    service = KeywordService()
    session = make_mock_session()
    actor = make_actor()
    project_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=uuid4())

    service._projects.get_model = AsyncMock(return_value=project)  # type: ignore[method-assign]
    service._repository.get_by_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._repository.delete_keyword = AsyncMock()  # type: ignore[method-assign]

    with (
        patch("app.domains.keywords.service.set_actor_context", new_callable=AsyncMock),
        pytest.raises(ResourceNotFound),
    ):
        await service.delete_keyword(
            session,
            actor=actor,
            project_id=project_id,
            keyword_id=uuid4(),
        )

    service._repository.delete_keyword.assert_not_awaited()
