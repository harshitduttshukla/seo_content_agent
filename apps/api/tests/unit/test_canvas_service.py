from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.domains.canvas.models import Claim, ClaimRow
from app.domains.canvas.service import CanvasService
from app.domains.job_runs.models import JobRun


@asynccontextmanager
async def passthrough_transaction(session: object):
    yield session


@pytest.mark.asyncio
async def test_check_claim_edit_only_reads_citation_count() -> None:
    service = CanvasService(AsyncMock())
    claim = Claim(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        canvas_id=uuid4(),
        row=ClaimRow.PITCH,
        text="Original claim",
        evidence="Evidence",
    )
    service.repository.get_claim_by_id = AsyncMock(return_value=claim)
    service.repository.get_citation_count = AsyncMock(return_value=7)
    service.repository.add = MagicMock()

    result = await service.check_claim_edit(claim.organization_id, claim.project_id, claim.id)

    assert result.citation_count == 7
    assert result.claim_text == "Original claim"
    service.repository.add.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_claim_edit_creates_new_version_and_job_run() -> None:
    session = AsyncMock()
    service = CanvasService(session)
    old_claim = Claim(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        canvas_id=uuid4(),
        row=ClaimRow.PITCH,
        text="Original claim",
        evidence="Old evidence",
        approved=True,
        version=4,
    )
    service.repository.get_claim_by_id = AsyncMock(return_value=old_claim)
    added: list[object] = []

    def add(entity: object) -> None:
        added.append(entity)

    service.repository.add = MagicMock(side_effect=add)
    with patch(
        "app.domains.canvas.service.transactional_session",
        passthrough_transaction,
    ):
        result = await service.confirm_claim_edit(
            old_claim.organization_id,
            old_claim.project_id,
            old_claim.id,
            "New claim",
            "New evidence",
            uuid4(),
        )

    new_claim = next(entity for entity in added if isinstance(entity, Claim))
    job_run = next(entity for entity in added if isinstance(entity, JobRun))
    assert new_claim.text == "New claim"
    assert new_claim.version == 5
    assert old_claim.text == "Original claim"
    assert old_claim.superseded_by == new_claim.id
    assert job_run.prompt_version == "v3.stale-claim-scan.v1"
    assert result.new_claim_id == new_claim.id
