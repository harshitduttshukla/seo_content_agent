from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.canvas.schemas import (
    AreaResponse,
    CanvasFullResponse,
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
async def test_canvas_routes_expose_create_and_two_step_claim_edit() -> None:
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
    created_canvas_id = uuid4()
    create_canvas = AsyncMock(
        return_value=CanvasFullResponse(
            id=created_canvas_id,
            product_line=None,
            name="Company canvas",
            anchors=[],
            problem_summary="",
            differentiation_summary="",
            version=1,
            arguments=[],
            pitch_claim=None,
        )
    )
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch(
            "app.domains.canvas.service.CanvasService.create_company_canvas",
            create_canvas,
        ),
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
            created = await client.post(f"/api/v3/canvases?{query}", headers=headers)
            canvases = await client.get(f"/api/v3/canvases?{query}", headers=headers)
            check = await client.post(
                f"/api/v3/claims/{claim_id}/edit/check?{query}", headers=headers
            )
            confirm = await client.post(
                f"/api/v3/claims/{claim_id}/edit/confirm?{query}",
                headers=headers,
                json={"text": "New version", "evidence": "Customer research"},
            )
    assert created.status_code == 201
    assert created.json()["data"] == {
        "id": str(created_canvas_id),
        "product_line": None,
        "name": "Company canvas",
        "anchors": [],
        "problem_summary": "",
        "differentiation_summary": "",
        "version": 1,
        "arguments": [],
        "problem_summary_claim": None,
        "differentiation_summary_claim": None,
        "pitch_claim": None,
    }
    assert canvases.status_code == 200
    assert check.json()["data"]["citation_count"] == 3
    assert confirm.json()["data"]["new_version"] == 2
    create_canvas.assert_awaited_once_with(organization_id, project_id, actor=actor)


@pytest.mark.asyncio
async def test_area_list_route_is_project_scoped() -> None:
    organization_id = uuid4()
    project_id = uuid4()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="v3-test",
        email="v3@example.com",
        display_name="V3 Tester",
    )
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    area = AreaResponse(
        id=uuid4(),
        canvas_id=uuid4(),
        parent_id=None,
        name="International sales",
        default_argument_id=None,
    )
    list_areas = AsyncMock(return_value=[area])
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch("app.domains.canvas.service.CanvasService.list_areas", list_areas),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v3/areas",
                headers={"Authorization": "Bearer token"},
                params={"organization_id": str(organization_id), "project_id": str(project_id)},
            )

    assert response.status_code == 200
    assert response.json()["data"][0]["name"] == "International sales"
    assert list_areas.await_args.args[:2] == (organization_id, project_id)
    assert list_areas.await_args.kwargs == {"canvas_id": None, "actor": actor}


def test_canvas_openapi_has_distinct_check_and_confirm_operations() -> None:
    app = create_app(Settings(_env_file=None, APP_ENV="test"), engine=AsyncMock())
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v3/canvases"]
    assert "/api/v3/areas" in paths
    assert paths["/api/v3/canvases"]["post"]["responses"]["201"]
    assert "post" in paths["/api/v3/canvases/{canvas_id}/anchors"]
    assert "post" in paths["/api/v3/canvases/{canvas_id}/arguments"]
    assert "post" in paths["/api/v3/canvases/{canvas_id}/claims"]
    assert "/api/v3/claims/{claim_id}/edit/check" in paths
    assert "/api/v3/claims/{claim_id}/edit/confirm" in paths
    assert "/api/v3/claims/{claim_id}/approve" in paths
    assert "/api/v3/content-cards" in paths
    assert "/api/v3/claims/{claim_id}/citations" in paths


@pytest.mark.asyncio
async def test_canvas_api_approve_and_citations() -> None:
    organization_id = uuid4()
    project_id = uuid4()
    claim_id = uuid4()
    card_id = uuid4()
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
            "app.domains.canvas.service.CanvasService.approve_claim",
            AsyncMock(
                return_value={
                    "id": str(claim_id),
                    "row": "pitch",
                    "text": "Pitch text",
                    "evidence": "",
                    "approved": True,
                    "approved_by": str(user_id),
                    "version": 1,
                    "superseded_by": None,
                    "market_overrides": {},
                    "inherited": False,
                    "clm_number": "CLM-000",
                    "citation_count": 2,
                }
            ),
        ),
        patch(
            "app.domains.canvas.service.CanvasService.list_content_cards",
            AsyncMock(
                return_value=[
                    {
                        "id": str(card_id),
                        "title": "Live Home",
                        "kind": "cluster",
                        "state": "live",
                        "url": "https://example.com",
                    }
                ]
            ),
        ),
        patch(
            "app.domains.canvas.service.CanvasService.add_citation",
            AsyncMock(
                return_value={
                    "argument_chain": [],
                    "demand_nodes": [],
                    "content_cards": [
                        {
                            "id": str(card_id),
                            "title": "Live Home",
                            "kind": "cluster",
                            "state": "live",
                            "url": "https://example.com",
                        }
                    ],
                }
            ),
        ),
    ):
        query = f"organization_id={organization_id}&project_id={project_id}"
        headers = {"Authorization": "Bearer token"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            approved = await client.post(
                f"/api/v3/claims/{claim_id}/approve?{query}", headers=headers
            )
            cards = await client.get(f"/api/v3/content-cards?{query}", headers=headers)
            citation = await client.post(
                f"/api/v3/claims/{claim_id}/citations?{query}",
                headers=headers,
                json={"content_card_id": str(card_id)},
            )
    assert approved.status_code == 200
    assert approved.json()["data"]["approved"] is True
    assert cards.status_code == 200
    assert len(cards.json()["data"]) == 1
    assert citation.status_code == 201
