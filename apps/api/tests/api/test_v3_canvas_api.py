from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.canvas.schemas import (
    CanvasListResponse,
    ClaimEditCheckResponse,
    ClaimEditConfirmResponse,
)
from app.main import create_app
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from httpx import ASGITransport, AsyncClient


class MockTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://identity.example.com",
            subject="v3-test",
            email="v3@example.com",
            display_name="V3 Tester",
        )


@pytest.mark.asyncio
async def test_canvas_routes_expose_two_step_claim_edit() -> None:
    organization_id = uuid4()
    project_id = uuid4()
    claim_id = uuid4()
    user_id = uuid4()
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    actor = AuthenticatedUser(
        user_id=user_id,
        issuer="https://identity.example.com",
        subject="v3-test",
        email="v3@example.com",
        display_name="V3 Tester",
    )
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch(
            "app.security.authorization.AuthorizationService.require_project",
            AsyncMock(return_value="admin"),
        ) as authorize,
        patch(
            "app.domains.canvas.service.CanvasService.list_canvases",
            AsyncMock(return_value=CanvasListResponse(company_canvas=None, product_lines=[])),
        ),
        patch(
            "app.domains.canvas.service.CanvasService.check_claim_edit",
            AsyncMock(
                return_value=ClaimEditCheckResponse(
                    citation_count=3,
                    claim_text="Original",
                    claim_id=claim_id,
                )
            ),
        ),
        patch(
            "app.domains.canvas.service.CanvasService.confirm_claim_edit",
            AsyncMock(
                return_value=ClaimEditConfirmResponse(
                    old_claim_id=claim_id,
                    new_claim_id=uuid4(),
                    new_version=2,
                    job_run_id=uuid4(),
                )
            ),
        ),
    ):
        query = f"organization_id={organization_id}&project_id={project_id}"
        headers = {"Authorization": "Bearer token"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            canvases = await client.get(f"/api/v3/canvases?{query}", headers=headers)
            check = await client.post(
                f"/api/v3/claims/{claim_id}/edit/check?{query}", headers=headers
            )
            confirm = await client.post(
                f"/api/v3/claims/{claim_id}/edit/confirm?{query}",
                headers=headers,
                json={"text": "New version", "evidence": "Customer research"},
            )
    assert canvases.status_code == 200
    assert check.json()["data"]["citation_count"] == 3
    assert confirm.json()["data"]["new_version"] == 2
    assert authorize.await_count == 3


def test_canvas_openapi_has_distinct_check_and_confirm_operations() -> None:
    app = create_app(Settings(_env_file=None, APP_ENV="test"), engine=AsyncMock())
    paths = app.openapi()["paths"]
    assert "/api/v3/claims/{claim_id}/edit/check" in paths
    assert "/api/v3/claims/{claim_id}/edit/confirm" in paths
