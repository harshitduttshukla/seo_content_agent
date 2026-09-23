from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.domains.content_cards.service import SiteImportService
from app.domains.job_runs.models import JobRun


@asynccontextmanager
async def passthrough_transaction(session: object):
    yield session


@pytest.mark.asyncio
async def test_site_import_creates_one_card_and_job_run() -> None:
    service = SiteImportService(AsyncMock())
    service.repository.get_by_url = AsyncMock(return_value=None)
    service.repository.add_content_card = MagicMock()
    jobs: list[JobRun] = []
    service.repository.add_job_run = MagicMock(side_effect=jobs.append)
    with patch(
        "app.domains.content_cards.service.transactional_session",
        passthrough_transaction,
    ):
        result = await service.run_site_import(uuid4(), uuid4(), "https://example.com/", uuid4())

    assert result.created_count == 1
    assert result.existing_count == 0
    service.repository.add_content_card.assert_called_once()
    assert jobs[0].prompt_version == "v3.site-import.v1"


@pytest.mark.asyncio
async def test_site_import_rerun_does_not_duplicate_content_card() -> None:
    service = SiteImportService(AsyncMock())
    service.repository.get_by_url = AsyncMock(return_value=object())
    service.repository.add_content_card = MagicMock()
    service.repository.add_job_run = MagicMock()
    with patch(
        "app.domains.content_cards.service.transactional_session",
        passthrough_transaction,
    ):
        result = await service.run_site_import(
            uuid4(), uuid4(), "https://example.com", uuid4(), force_refresh=True
        )

    assert result.created_count == 0
    assert result.existing_count == 1
    service.repository.add_content_card.assert_not_called()
    service.repository.add_job_run.assert_called_once()
