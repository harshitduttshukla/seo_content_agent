"""Route-level tests for the V3 Content Hub board endpoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.domains.content_cards.schemas import (
    BoardFilterOptions,
    BoardFilters,
    ContentCardKind,
    ContentHubBoard,
)
from httpx import ASGITransport, AsyncClient
from tests.api.test_v3_strategy_map_api import build_client_app

ORG, PROJECT = uuid4(), uuid4()
SCOPE = f"organization_id={ORG}&project_id={PROJECT}"
AUTH = {"Authorization": "Bearer token"}


def _empty_board() -> ContentHubBoard:
    return ContentHubBoard(
        project_id=PROJECT,
        plan_locked_at=datetime(2026, 9, 24, tzinfo=UTC),
        total_count=0,
        columns=[],
        filter_options=BoardFilterOptions(areas=[], kinds=[], owners=[], arguments=[], markets=[]),
    )


@asynccontextmanager
async def _client(authenticated: bool = True) -> AsyncIterator[AsyncClient]:
    app, actor = build_client_app()
    identity = AsyncMock(return_value=actor)
    with patch("app.domains.users.service.UserService.resolve_identity", identity):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=AUTH if authenticated else {}
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_board_route_passes_allowlisted_filters_to_the_service() -> None:
    area = uuid4()
    service = AsyncMock(return_value=_empty_board())
    with patch("app.domains.content_cards.hub_service.ContentHubService.get_board", service):
        async with _client() as client:
            response = await client.get(
                f"/api/v3/content-hub/board?{SCOPE}&area_id={area}&kind=compare&market=en-GB"
            )
    assert response.status_code == 200
    assert response.json()["data"]["plan_locked_at"].startswith("2026-09-24")
    assert service.await_args is not None
    organization_id, project_id, filters = service.await_args.args
    assert (organization_id, project_id) == (ORG, PROJECT)
    assert filters == BoardFilters(area_id=area, kind=ContentCardKind.COMPARE, market="en-GB")


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["kind=article", "market=english", "owner_id=not-a-uuid"])
async def test_board_route_rejects_unknown_filter_values(query: str) -> None:
    async with _client() as client:
        response = await client.get(f"/api/v3/content-hub/board?{SCOPE}&{query}")
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"target_state": "live", "revision": 1},
        {"target_state": "drafting", "revision": 1},
        {"target_state": "planned"},
        {"target_state": "planned", "revision": 1, "priority": 3},
    ],
)
async def test_move_route_only_accepts_backlog_or_planned(body: dict[str, object]) -> None:
    service = AsyncMock()
    with patch("app.domains.content_cards.hub_service.ContentHubService.move_card", service):
        async with _client() as client:
            response = await client.post(
                f"/api/v3/content-hub/cards/{uuid4()}/move?{SCOPE}", json=body
            )
    assert response.status_code == 422
    service.assert_not_awaited()


@pytest.mark.asyncio
async def test_reorder_route_rejects_an_empty_list() -> None:
    async with _client() as client:
        response = await client.put(
            f"/api/v3/content-hub/planned/order?{SCOPE}", json={"card_ids": []}
        )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v3/content-hub/board"),
        ("POST", f"/api/v3/content-hub/cards/{uuid4()}/move"),
        ("PUT", "/api/v3/content-hub/planned/order"),
    ],
)
async def test_board_routes_require_authentication(method: str, path: str) -> None:
    async with _client(authenticated=False) as client:
        response = await client.request(method, f"{path}?{SCOPE}", json={})
    assert response.status_code == 401
