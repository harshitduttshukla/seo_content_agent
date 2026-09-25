"""Route-level tests for the V3 card detail and Bundle → Outline endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from tests.api.test_v3_content_hub_api import SCOPE, _client

CARD = uuid4()
BASE = f"/api/v3/content-hub/cards/{CARD}"
SERVICE = "app.domains.content_cards.workflow_service.CardWorkflowService"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", BASE),
        ("POST", f"{BASE}/bundle"),
        ("POST", f"{BASE}/outline/generate"),
        ("PUT", f"{BASE}/outline"),
    ],
)
async def test_workflow_routes_require_authentication(method: str, path: str) -> None:
    async with _client(authenticated=False) as client:
        response = await client.request(method, f"{path}?{SCOPE}", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", f"{BASE}/bundle", {}),
        ("POST", f"{BASE}/bundle", {"revision": 0}),
        ("POST", f"{BASE}/outline/generate", {"state": "outlined"}),
        ("PUT", f"{BASE}/outline", {"revision": 1}),
        ("PUT", f"{BASE}/outline", {"revision": 1, "outline": {"primary_mode": "keyword"}}),
        (
            "PUT",
            f"{BASE}/outline",
            {
                "revision": 1,
                "outline": {
                    "primary_mode": "keyword",
                    "title": "t",
                    "sections": [{"section_id": "s1", "order": 1, "heading": "h"}],
                    "sql": "DROP TABLE claims",
                },
            },
        ),
    ],
)
async def test_workflow_routes_validate_bodies_before_the_service(
    method: str, path: str, body: dict[str, object]
) -> None:
    with (
        patch(f"{SERVICE}.build_bundle", AsyncMock()) as bundle,
        patch(f"{SERVICE}.generate_outline", AsyncMock()) as generate,
        patch(f"{SERVICE}.save_outline", AsyncMock()) as save,
    ):
        async with _client() as client:
            response = await client.request(method, f"{path}?{SCOPE}", json=body)
    assert response.status_code == 422
    for mock in (bundle, generate, save):
        mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_workflow_routes_require_scope_parameters() -> None:
    async with _client() as client:
        response = await client.get(BASE)
    assert response.status_code == 422
