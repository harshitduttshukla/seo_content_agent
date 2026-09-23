"""Route-level tests for GET /api/v3/strategy/map."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.canvas.schemas import MapAreaNode, MapCanvasNode, StrategyMapResponse
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


def build_client_app() -> tuple[object, AuthenticatedUser]:
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="v3-test",
        email="v3@example.com",
        display_name="V3 Tester",
    )
    return app, actor


@pytest.mark.asyncio
async def test_strategy_map_route_returns_the_nested_tree_in_one_payload() -> None:
    organization_id = uuid4()
    project_id = uuid4()
    app, actor = build_client_app()

    area_id = uuid4()
    sub_area_id = uuid4()
    payload = StrategyMapResponse(
        company_canvas=MapCanvasNode(
            id=uuid4(),
            name="Company canvas",
            product_line=None,
            is_company=True,
            argument_count=3,
            cell_count=41,
            areas=[],
            product_lines=[
                MapCanvasNode(
                    id=uuid4(),
                    name="Duties & Taxes",
                    product_line="Duties & Taxes",
                    is_company=False,
                    argument_count=2,
                    cell_count=12,
                    inherits=["A1"],
                    override_count=0,
                    adds=["A4"],
                    areas=[
                        MapAreaNode(
                            id=area_id,
                            name="Landed cost",
                            parent_id=None,
                            default_argument_id=None,
                            default_argument_pillar="Item-level landed cost",
                            demand_count=412,
                            card_count=4,
                            children=[
                                MapAreaNode(
                                    id=sub_area_id,
                                    name="HS codes",
                                    parent_id=area_id,
                                    default_argument_id=None,
                                    demand_count=61,
                                    card_count=0,
                                    content_gap=True,
                                )
                            ],
                        )
                    ],
                )
            ],
        ),
        unassigned_card_count=37,
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch(
            "app.domains.canvas.map_service.StrategyMapService.get_strategy_map",
            AsyncMock(return_value=payload),
        ),
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v3/strategy/map?organization_id={organization_id}&project_id={project_id}",
                headers={"Authorization": "Bearer token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert "data" in body  # standard api/v3 envelope
    data = body["data"]
    assert data["unassigned_card_count"] == 37
    company = data["company_canvas"]
    assert company["is_company"] is True
    assert company["cell_count"] == 41
    line = company["product_lines"][0]
    assert line["inherits"] == ["A1"]
    assert line["adds"] == ["A4"]
    assert line["areas"][0]["demand_count"] == 412
    assert line["areas"][0]["children"][0]["content_gap"] is True


@pytest.mark.asyncio
async def test_strategy_map_route_returns_null_canvas_when_none_exists() -> None:
    organization_id = uuid4()
    project_id = uuid4()
    app, actor = build_client_app()

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch(
            "app.domains.canvas.map_service.StrategyMapService.get_strategy_map",
            AsyncMock(
                return_value=StrategyMapResponse(company_canvas=None, unassigned_card_count=0)
            ),
        ),
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v3/strategy/map?organization_id={organization_id}&project_id={project_id}",
                headers={"Authorization": "Bearer token"},
            )

    assert response.status_code == 200
    assert response.json()["data"]["company_canvas"] is None


@pytest.mark.asyncio
async def test_strategy_map_route_requires_authentication() -> None:
    app, _ = build_client_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/v3/strategy/map?organization_id={uuid4()}&project_id={uuid4()}"
        )

    assert response.status_code == 401
