"""Route-level tests for the V3 Production QA, repair, section and G2 endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.core.errors import ConflictError, PermissionDenied
from tests.api.test_v3_content_hub_api import SCOPE, _client

CARD = uuid4()
BASE = f"/api/v3/content-hub/cards/{CARD}"
SERVICE = "app.domains.content_cards.production_service.ProductionService"
ROUTES = {
    f"{BASE}/qa/run": "run_qa",
    f"{BASE}/qa/repair": "repair_draft",
    f"{BASE}/sections/s1/regenerate": "regenerate_section",
    f"{BASE}/g2/approve": "approve_g2",
    f"{BASE}/g2/send-back": "send_back_g2",
    f"{BASE}/g2/warning-dismiss": "dismiss_warning",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("path", list(ROUTES))
async def test_routes_require_authentication(path: str) -> None:
    async with _client(authenticated=False) as client:
        response = await client.post(f"{path}?{SCOPE}", json={"revision": 1})
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "body"),
    [
        (f"{BASE}/qa/run", {}),
        (f"{BASE}/qa/run", {"revision": 1, "state": "qa_passed"}),
        (f"{BASE}/qa/repair", {"revision": 0}),
        (f"{BASE}/sections/s1/regenerate", {"revision": 1}),
        (f"{BASE}/sections/s1/regenerate", {"revision": 1, "feedback": "  "}),
        (f"{BASE}/g2/approve", {"revision": 1, "qa_report": {}}),
        (f"{BASE}/g2/send-back", {"revision": 1, "reason": "writer"}),
        (f"{BASE}/g2/send-back", {"revision": 1, "reason": "publish", "feedback": "x"}),
        (f"{BASE}/g2/warning-dismiss", {"revision": 1, "finding_id": "abc"}),
        (f"{BASE}/g2/warning-dismiss", {"revision": 1, "finding_id": "abc", "reason": " "}),
    ],
)
async def test_bodies_are_validated_before_the_service(path: str, body: dict[str, object]) -> None:
    mocks = {name: AsyncMock() for name in ROUTES.values()}
    with patch.multiple(SERVICE, **mocks):
        async with _client() as client:
            response = await client.post(f"{path}?{SCOPE}", json=body)
    assert response.status_code == 422
    for mock in mocks.values():
        mock.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (PermissionDenied(), 403, "PERMISSION_DENIED"),
        (ConflictError("QA_STALE", "stale"), 409, "QA_STALE"),
        (ConflictError("G2_BLOCKED", "blocked"), 409, "G2_BLOCKED"),
    ],
)
async def test_service_errors_map_to_the_envelope(error: Exception, status: int, code: str) -> None:
    with patch(f"{SERVICE}.approve_g2", AsyncMock(side_effect=error)):
        async with _client() as client:
            response = await client.post(f"{BASE}/g2/approve?{SCOPE}", json={"revision": 3})
    assert response.status_code == status
    body = response.json()
    assert body["data"] is None and body["errors"][0]["code"] == code
