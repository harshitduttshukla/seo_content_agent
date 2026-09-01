from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.core.errors import ConflictError, ResourceNotFound
from app.domains.organizations.models import Organization, OrganizationStatus
from app.domains.organizations.schemas import OrganizationUpdate
from app.domains.organizations.service import OrganizationService
from app.domains.projects.models import Project, ProjectStatus
from app.domains.projects.schemas import ProjectUpdate
from app.domains.projects.service import ProjectService
from app.domains.websites.service import WebsiteService
from app.security.principal import AuthenticatedUser, RoleCode


def make_mock_session() -> MagicMock:
    session = MagicMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    session.begin.return_value = context_manager
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-sub",
        email="test@example.com",
        display_name="Test User",
    )


@pytest.mark.asyncio
async def test_organization_update_revision_conflict(actor: AuthenticatedUser) -> None:
    service = OrganizationService()
    org_id = uuid4()
    mock_org = Organization(
        id=org_id,
        name="Old Name",
        slug="old-name",
        status=OrganizationStatus.ACTIVE,
        revision=2,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    service._organizations.get_for_user = AsyncMock(return_value=mock_org)  # type: ignore[method-assign]
    service._authorization.require_organization = AsyncMock(  # type: ignore[method-assign]
        return_value=RoleCode.ADMIN
    )

    session = make_mock_session()

    payload = OrganizationUpdate(
        name="New Name",
        slug="new-name",
        status=OrganizationStatus.ACTIVE,
        revision=1,  # Stale revision
    )

    with pytest.raises(ConflictError) as exc_info:
        await service.update(
            session,
            actor=actor,
            organization_id=org_id,
            payload=payload,
            request_id="req_test",
        )
    assert exc_info.value.code == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_project_update_revision_conflict(actor: AuthenticatedUser) -> None:
    service = ProjectService()
    project_id = uuid4()
    org_id = uuid4()
    mock_project = Project(
        id=project_id,
        organization_id=org_id,
        name="Old Project",
        slug="old-project",
        description="",
        status=ProjectStatus.ACTIVE,
        default_locale="en",
        default_country="US",
        revision=3,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    service._projects.get_for_organization_member = AsyncMock(  # type: ignore[method-assign]
        return_value=mock_project
    )
    service._authorization.require_project = AsyncMock(  # type: ignore[method-assign]
        return_value=RoleCode.ADMIN
    )

    session = make_mock_session()

    payload = ProjectUpdate(
        name="Updated Project",
        slug="updated-project",
        description="Updated",
        status=ProjectStatus.ACTIVE,
        default_locale="en",
        default_country="US",
        revision=2,  # Stale revision
    )

    with pytest.raises(ConflictError) as exc_info:
        await service.update(
            session,
            actor=actor,
            project_id=project_id,
            payload=payload,
            request_id="req_test",
        )
    assert exc_info.value.code == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_website_get_model_not_found(actor: AuthenticatedUser) -> None:
    service = WebsiteService()
    website_id = uuid4()

    service._websites.get_for_organization_member = AsyncMock(  # type: ignore[method-assign]
        return_value=None
    )

    session = AsyncMock()
    with pytest.raises(ResourceNotFound):
        await service.get_model(
            session,
            actor=actor,
            website_id=website_id,
            permission=MagicMock(),
        )
