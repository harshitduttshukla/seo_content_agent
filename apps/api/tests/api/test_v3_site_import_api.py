from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.content_cards.schemas import SiteImportResponse, SiteImportStatusResponse
from app.main import create_app
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from httpx import ASGITransport, AsyncClient


class MockTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://identity.example.com",
            subject="import-test",
            email="import@example.com",
            display_name="Import Tester",
        )


@pytest.mark.asyncio
async def test_site_import_run_and_status_contracts() -> None:
    organization_id = uuid4()
    project_id = uuid4()
    job_id = uuid4()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="import-test",
        email="import@example.com",
        display_name="Import Tester",
    )
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch(
            "app.security.authorization.AuthorizationService.require_project",
            AsyncMock(return_value="admin"),
        ),
        patch(
            "app.domains.content_cards.service.SiteImportService.run_site_import",
            AsyncMock(
                return_value=SiteImportResponse(
                    job_run_id=job_id,
                    status="completed",
                    created_count=1,
                    existing_count=0,
                )
            ),
        ),
        patch(
            "app.domains.content_cards.service.SiteImportService.get_import_status",
            AsyncMock(
                return_value=SiteImportStatusResponse(
                    job_run_id=job_id,
                    status="completed",
                    created_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    created_count=1,
                    existing_count=0,
                    unmapped_count=1,
                )
            ),
        ),
    ):
        query = f"organization_id={organization_id}&project_id={project_id}"
        headers = {"Authorization": "Bearer token"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            run = await client.post(
                f"/api/v3/site-import/run?{query}",
                headers=headers,
                json={"url": "https://example.com"},
            )
            status = await client.get(
                f"/api/v3/site-import/{job_id}/status?{query}", headers=headers
            )
    assert run.status_code == 200
    assert run.json()["data"]["job_run_id"] == str(job_id)
    assert status.json()["data"]["unmapped_count"] == 1
