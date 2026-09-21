from contextlib import asynccontextmanager
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.domains.demand.models import DemandNodeStatus
from app.domains.demand.schemas import BulkActionRequest, DemandImportRequest
from app.domains.demand.service import DemandService
from app.security.principal import AuthenticatedUser


@asynccontextmanager
async def passthrough_transaction(session: object):
    yield session


@pytest.mark.asyncio
async def test_bulk_pending_classify_is_tenant_scoped_and_audited() -> None:
    service = DemandService(AsyncMock())
    organization_id = uuid4()
    project_id = uuid4()
    node_ids = [uuid4(), uuid4()]
    service.repository.bulk_update_status = AsyncMock(return_value=2)
    service._authorization.require_project = AsyncMock()
    jobs: list[object] = []
    service.repository.add_job_run = MagicMock(side_effect=jobs.append)
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="test",
        subject="test",
        email="test@example.com",
        display_name="Test",
    )
    with patch("app.domains.demand.service.transactional_session", passthrough_transaction):
        result = await service.bulk_set_pending_classify(
            organization_id, project_id, node_ids, actor
        )

    service.repository.bulk_update_status.assert_awaited_once_with(
        organization_id, project_id, node_ids, DemandNodeStatus.PENDING_CLASSIFY
    )
    assert result.updated_count == 2
    assert jobs[0].prompt_version == "v3.demand_pending_classify.v1"


@pytest.mark.asyncio
async def test_csv_import_skips_existing_identity() -> None:
    service = DemandService(AsyncMock())
    service.repository.get_by_identity = AsyncMock(side_effect=[None, object()])
    service.repository.add_node = MagicMock()
    service.repository.add_job_run = MagicMock()
    service._authorization.require_project = AsyncMock()
    payload = DemandImportRequest.model_validate(
        {
            "items": [
                {"text": "new keyword", "type": "keyword"},
                {"text": "existing keyword", "type": "keyword"},
            ]
        }
    )
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="test",
        subject="test",
        email="test@example.com",
        display_name="Test",
    )
    with patch("app.domains.demand.service.transactional_session", passthrough_transaction):
        result = await service.import_nodes(uuid4(), uuid4(), payload, actor)

    assert result.created_count == 1
    assert result.existing_count == 1
    service.repository.add_node.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,status", [("keep", DemandNodeStatus.KEPT), ("discard", DemandNodeStatus.DISCARDED)]
)
async def test_bulk_status_actions_are_tenant_scoped(action: str, status: DemandNodeStatus) -> None:
    service = DemandService(AsyncMock())
    service._authorization.require_project = AsyncMock()
    service.repository.bulk_update_status = AsyncMock(return_value=1)
    service.repository.add_job_run = MagicMock()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="test",
        subject="test",
        email="test@example.com",
        display_name="Test",
    )
    payload = BulkActionRequest(ids=[uuid4()], action=action)
    with patch("app.domains.demand.service.transactional_session", passthrough_transaction):
        await service.bulk_action(uuid4(), uuid4(), payload, actor)
    service.repository.bulk_update_status.assert_awaited_once_with(ANY, ANY, payload.ids, status)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "repository_method", "destination_field"),
    [
        ("reassign_area", "bulk_reassign_area", "area_id"),
        ("set_argument", "bulk_set_argument", "argument_id"),
    ],
)
async def test_bulk_destination_actions_are_tenant_scoped(
    action: str, repository_method: str, destination_field: str
) -> None:
    service = DemandService(AsyncMock())
    service._authorization.require_project = AsyncMock()
    destination_id = uuid4()
    repository_action = AsyncMock(return_value=1)
    setattr(service.repository, repository_method, repository_action)
    service.repository.add_job_run = MagicMock()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="test",
        subject="test",
        email="test@example.com",
        display_name="Test",
    )
    payload = BulkActionRequest(ids=[uuid4()], action=action, **{destination_field: destination_id})

    with patch("app.domains.demand.service.transactional_session", passthrough_transaction):
        await service.bulk_action(uuid4(), uuid4(), payload, actor)

    repository_action.assert_awaited_once_with(ANY, ANY, payload.ids, destination_id)
