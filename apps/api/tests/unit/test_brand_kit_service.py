from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.core.errors import PermissionDenied
from app.domains.brand_kit.models import BrandKit
from app.domains.brand_kit.schemas import BrandKitUpsertRequest, SocialProofCreateRequest
from app.domains.brand_kit.service import BrandKitService
from app.security.principal import AuthenticatedUser, PermissionCode


@asynccontextmanager
async def passthrough_transaction(session: object):
    yield session


def actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="brand-kit-test",
        email="brand@example.com",
        display_name="Brand Tester",
    )


@pytest.mark.asyncio
async def test_upsert_brand_kit_scopes_the_singleton_to_authorized_project() -> None:
    session = AsyncMock()
    service = BrandKitService(session)
    organization_id, project_id = uuid4(), uuid4()
    current_actor = actor()
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get = AsyncMock(return_value=None)
    service.repository.add = MagicMock()

    async def assign_database_defaults() -> None:
        record = service.repository.add.call_args.args[0]
        record.revision = 1
        record.updated_at = datetime.now(UTC)

    session.flush.side_effect = assign_database_defaults

    with (
        patch("app.domains.brand_kit.service.transactional_session", passthrough_transaction),
        patch("app.domains.brand_kit.service.set_actor_context", AsyncMock()),
    ):
        result = await service.upsert(
            organization_id,
            project_id,
            BrandKitUpsertRequest(spelling="en-GB", banned_words=["seamless"]),
            actor=current_actor,
        )

    record = service.repository.add.call_args.args[0]
    assert isinstance(record, BrandKit)
    assert record.organization_id == organization_id
    assert record.project_id == project_id
    assert result.spelling == "en-GB"
    service._authorization.require_project.assert_awaited_once_with(
        session,
        user_id=current_actor.user_id,
        organization_id=organization_id,
        project_id=project_id,
        permission=PermissionCode.STRATEGY_WRITE,
    )


@pytest.mark.asyncio
async def test_social_proof_rejects_an_area_outside_the_authorized_project() -> None:
    service = BrandKitService(AsyncMock())
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.area_exists = AsyncMock(return_value=False)
    service.repository.add = MagicMock()

    with (
        patch("app.domains.brand_kit.service.transactional_session", passthrough_transaction),
        patch("app.domains.brand_kit.service.set_actor_context", AsyncMock()),
        pytest.raises(Exception, match="does not belong to this project"),
    ):
        await service.create_social_proof(
            uuid4(),
            uuid4(),
            SocialProofCreateRequest(
                label="Example", proof_type="case study", area_ids=[uuid4()], approved=True
            ),
            actor=actor(),
        )

    service.repository.add.assert_not_called()


@pytest.mark.asyncio
async def test_write_denial_precedes_any_brand_kit_lookup() -> None:
    service = BrandKitService(AsyncMock())
    service._authorization.require_project = AsyncMock(side_effect=PermissionDenied())
    service.repository.get = AsyncMock()
    service.repository.add = MagicMock()

    with (
        patch("app.domains.brand_kit.service.transactional_session", passthrough_transaction),
        patch("app.domains.brand_kit.service.set_actor_context", AsyncMock()),
        pytest.raises(PermissionDenied),
    ):
        await service.upsert(uuid4(), uuid4(), BrandKitUpsertRequest(), actor=actor())

    service.repository.get.assert_not_awaited()
    service.repository.add.assert_not_called()
