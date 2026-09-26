"""Route-level tests for the Google Search Console endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.core.errors import DomainError
from tests.api.test_v3_content_hub_api import _client

PROJECT, WEBSITE = uuid4(), uuid4()
SERVICE = "app.domains.search_console.service.SearchConsoleService"
ROUTES = [
    ("GET", f"/api/v1/projects/{PROJECT}/search-console", None),
    ("POST", f"/api/v1/projects/{PROJECT}/search-console/connect", None),
    ("POST", "/api/v1/search-console/oauth/callback", {"code": "c", "state": "s" * 20}),
    ("DELETE", f"/api/v1/projects/{PROJECT}/search-console/connection", None),
    ("GET", f"/api/v1/projects/{PROJECT}/search-console/properties", None),
    (
        "PUT",
        f"/api/v1/websites/{WEBSITE}/search-console/property",
        {"site_url": "sc-domain:x.test"},
    ),
    ("POST", f"/api/v1/websites/{WEBSITE}/search-console/sync", {}),
    ("GET", f"/api/v1/websites/{WEBSITE}/search-console/analytics", None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_routes_require_authentication(method: str, path: str, body: object) -> None:
    async with _client(authenticated=False) as client:
        response = await client.request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/v1/search-console/oauth/callback", {"code": "c"}),
        ("POST", "/api/v1/search-console/oauth/callback", {"code": "c", "state": "short"}),
        (
            "POST",
            "/api/v1/search-console/oauth/callback",
            {"code": "c", "state": "s" * 20, "project_id": "x"},
        ),
        ("PUT", f"/api/v1/websites/{WEBSITE}/search-console/property", {}),
        ("POST", f"/api/v1/websites/{WEBSITE}/search-console/sync", {"start_date": "2026-09-01"}),
        (
            "POST",
            f"/api/v1/websites/{WEBSITE}/search-console/sync",
            {"start_date": "yesterday", "end_date": "x"},
        ),
        ("GET", f"/api/v1/websites/{WEBSITE}/search-console/analytics?start_date=2026-09-01", None),
        ("GET", f"/api/v1/websites/{WEBSITE}/search-console/analytics?limit=100000", None),
        ("GET", f"/api/v1/websites/{WEBSITE}/search-console/analytics?sort=secret", None),
    ],
)
async def test_bad_input_is_rejected_before_the_service(
    method: str, path: str, body: object
) -> None:
    names = ["complete_connect", "map_property", "sync", "analytics"]
    mocks = {n: AsyncMock() for n in names}
    with patch.multiple(SERVICE, **mocks):
        async with _client() as client:
            response = await client.request(method, path, json=body)
    assert response.status_code == 422
    for mock in mocks.values():
        mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_errors_use_the_envelope_without_secrets() -> None:
    error = DomainError(
        "GSC_REAUTH_REQUIRED", "Google access expired or was revoked. Reconnect Google.", 409
    )
    with patch(f"{SERVICE}.sync", AsyncMock(side_effect=error)):
        async with _client() as client:
            response = await client.post(f"/api/v1/websites/{WEBSITE}/search-console/sync", json={})
    assert response.status_code == 409
    body = response.json()
    assert body["data"] is None and body["errors"][0]["code"] == "GSC_REAUTH_REQUIRED"
