"""Route-level tests for the V3 G1 review and draft endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.core.errors import ConflictError, PermissionDenied
from tests.api.test_v3_content_hub_api import SCOPE, _client

CARD = uuid4()
BASE = f"/api/v3/content-hub/cards/{CARD}"
SERVICE = "app.domains.content_cards.workflow_service.CardWorkflowService"
ROUTES = [f"{BASE}/g1/approve", f"{BASE}/g1/send-back", f"{BASE}/draft/generate"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ROUTES)
async def test_routes_require_authentication(path: str) -> None:
    async with _client(authenticated=False) as client:
        response = await client.post(f"{path}?{SCOPE}", json={"revision": 1})
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "body"),
    [
        (f"{BASE}/g1/approve", {}),
        (f"{BASE}/g1/approve", {"revision": 0}),
        (f"{BASE}/g1/approve", {"revision": 1, "state": "approved"}),
        (f"{BASE}/g1/send-back", {"revision": 1, "reason": "plan"}),  # feedback required
        (f"{BASE}/g1/send-back", {"revision": 1, "reason": "plan", "feedback": "   "}),
        (f"{BASE}/g1/send-back", {"revision": 1, "reason": "whatever", "feedback": "x"}),
        (f"{BASE}/g1/send-back", {"revision": 1, "reason": "plan", "feedback": "x" * 4001}),
        (f"{BASE}/draft/generate", {}),
        (f"{BASE}/draft/generate", {"revision": 1, "draft": {"sections": []}}),
    ],
)
async def test_bodies_are_validated_before_the_service(path: str, body: dict[str, object]) -> None:
    with (
        patch(f"{SERVICE}.approve_g1", AsyncMock()) as approve,
        patch(f"{SERVICE}.send_back_g1", AsyncMock()) as send_back,
        patch(f"{SERVICE}.generate_draft", AsyncMock()) as generate,
    ):
        async with _client() as client:
            response = await client.post(f"{path}?{SCOPE}", json=body)
    assert response.status_code == 422
    for mock in (approve, send_back, generate):
        mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_routes_require_scope_parameters() -> None:
    async with _client() as client:
        response = await client.post(f"{BASE}/g1/approve", json={"revision": 1})
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (PermissionDenied(), 403, "PERMISSION_DENIED"),
        (ConflictError("VERSION_CONFLICT", "stale"), 409, "VERSION_CONFLICT"),
        (ConflictError("G1_CHECKS_FAILED", "checks"), 409, "G1_CHECKS_FAILED"),
    ],
)
async def test_service_errors_map_to_the_envelope(error: Exception, status: int, code: str) -> None:
    with patch(f"{SERVICE}.approve_g1", AsyncMock(side_effect=error)):
        async with _client() as client:
            response = await client.post(f"{BASE}/g1/approve?{SCOPE}", json={"revision": 3})
    assert response.status_code == status
    body = response.json()
    assert body["data"] is None and body["errors"][0]["code"] == code
