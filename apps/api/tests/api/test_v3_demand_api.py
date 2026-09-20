from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.demand.schemas import (
    BulkUpdateResponse,
    DemandImportResponse,
    DemandNodeListResponse,
    DemandSummaryCounts,
    PageMetadata,
)
from app.main import create_app
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from httpx import ASGITransport, AsyncClient


class MockTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://identity.example.com",
            subject="demand-test",
            email="demand@example.com",
            display_name="Demand Tester",
        )


@pytest.mark.asyncio
async def test_demand_list_import_and_bulk_routes_are_scoped() -> None:
    organization_id = uuid4()
    project_id = uuid4()
    node_id = uuid4()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="demand-test",
        email="demand@example.com",
        display_name="Demand Tester",
    )
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    empty = DemandNodeListResponse(
        items=[],
        summary=DemandSummaryCounts(
            total_discarded=0,
            below_065_confidence=0,
            total_kept=0,
            gsc_striking_distance_count=0,
        ),
        meta=PageMetadata(total_count=0, page=1, page_size=100),
    )
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch(
            "app.security.authorization.AuthorizationService.require_project",
            AsyncMock(return_value="admin"),
        ) as authorize,
        patch("app.domains.demand.service.DemandService.list_nodes", AsyncMock(return_value=empty)),
        patch(
            "app.domains.demand.service.DemandService.import_nodes",
            AsyncMock(
                return_value=DemandImportResponse(
                    created_count=1, existing_count=0, job_run_id=uuid4()
                )
            ),
        ),
        patch(
            "app.domains.demand.service.DemandService.bulk_set_pending_classify",
            AsyncMock(return_value=BulkUpdateResponse(updated_count=1, job_run_id=uuid4())),
        ),
    ):
        query = f"organization_id={organization_id}&project_id={project_id}"
        headers = {"Authorization": "Bearer token"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listed = await client.get(f"/api/v3/demand?{query}", headers=headers)
            imported = await client.post(
                f"/api/v3/demand/import?{query}",
                headers=headers,
                json={"items": [{"text": "cross-border SEO", "type": "keyword"}]},
            )
            updated = await client.post(
                f"/api/v3/demand/bulk/pending-classify?{query}",
                headers=headers,
                json={"node_ids": [str(node_id)]},
            )
    assert listed.status_code == 200
    assert imported.json()["data"]["created_count"] == 1
    assert updated.json()["data"]["updated_count"] == 1
    assert authorize.await_count == 3
