from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.domains.demand.models import DemandNodeStatus
from app.domains.demand.schemas import DemandImportRequest
from app.domains.demand.service import DemandService


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
    jobs: list[object] = []
    service.repository.add_job_run = MagicMock(side_effect=jobs.append)
    with patch("app.domains.demand.service.transactional_session", passthrough_transaction):
        result = await service.bulk_set_pending_classify(
            organization_id, project_id, node_ids, uuid4()
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
    payload = DemandImportRequest.model_validate(
        {
            "items": [
                {"text": "new keyword", "type": "keyword"},
                {"text": "existing keyword", "type": "keyword"},
            ]
        }
    )
    with patch("app.domains.demand.service.transactional_session", passthrough_transaction):
        result = await service.import_nodes(uuid4(), uuid4(), payload, uuid4())

    assert result.created_count == 1
    assert result.existing_count == 1
    service.repository.add_node.assert_called_once()
