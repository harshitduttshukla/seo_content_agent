"""Keyword-cluster deletion service regression tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.core.errors import ResourceNotFound
from app.domains.audit.repository import AuditWriter
from app.domains.keywords.service import KeywordService
from app.security.principal import AuthenticatedUser, PermissionCode


def make_mock_session() -> MagicMock:
    session = MagicMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    session.begin.return_value = context_manager
    return session


def make_actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-user-sub",
        email="tester@example.com",
        display_name="Tester",
    )


@pytest.mark.asyncio
async def test_delete_cluster_is_project_scoped_and_audited() -> None:
    service = KeywordService()
    session = make_mock_session()
    actor = make_actor()
    project_id = uuid4()
    organization_id = uuid4()
    cluster_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=organization_id)
    cluster = SimpleNamespace(id=cluster_id, cluster_name="Duplicate SEO")
    audit = MagicMock(spec=AuditWriter)

    service._projects.get_model = AsyncMock(return_value=project)  # type: ignore[method-assign]
    service._repository.get_cluster_by_id = AsyncMock(  # type: ignore[method-assign]
        return_value=cluster
    )
    service._repository.delete_cluster = AsyncMock()  # type: ignore[method-assign]
    service._audit = audit

    with patch("app.domains.keywords.service.set_actor_context", new_callable=AsyncMock):
        result = await service.delete_cluster(
            session,
            actor=actor,
            project_id=project_id,
            cluster_id=cluster_id,
            request_id="req_delete_cluster",
        )

    service._projects.get_model.assert_awaited_once_with(
        session,
        actor=actor,
        project_id=project_id,
        permission=PermissionCode.KEYWORD_WRITE,
    )
    service._repository.get_cluster_by_id.assert_awaited_once_with(
        session,
        cluster_id=cluster_id,
        project_id=project_id,
    )
    service._repository.delete_cluster.assert_awaited_once_with(
        session,
        cluster_id=cluster_id,
        project_id=project_id,
    )
    audit.add.assert_called_once_with(
        session,
        actor_user_id=actor.user_id,
        organization_id=organization_id,
        project_id=project_id,
        action="cluster.deleted",
        resource_type="keyword_cluster",
        resource_id=cluster_id,
        request_id="req_delete_cluster",
        metadata={"cluster_name": "Duplicate SEO"},
    )
    assert result.cluster_id == cluster_id
    assert result.cluster_name == "Duplicate SEO"


@pytest.mark.asyncio
async def test_delete_cluster_denies_cluster_outside_project_scope() -> None:
    service = KeywordService()
    session = make_mock_session()
    actor = make_actor()
    project_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=uuid4())

    service._projects.get_model = AsyncMock(return_value=project)  # type: ignore[method-assign]
    service._repository.get_cluster_by_id = AsyncMock(  # type: ignore[method-assign]
        return_value=None
    )
    service._repository.delete_cluster = AsyncMock()  # type: ignore[method-assign]

    with (
        patch("app.domains.keywords.service.set_actor_context", new_callable=AsyncMock),
        pytest.raises(ResourceNotFound),
    ):
        await service.delete_cluster(
            session,
            actor=actor,
            project_id=project_id,
            cluster_id=uuid4(),
        )

    service._repository.delete_cluster.assert_not_awaited()
