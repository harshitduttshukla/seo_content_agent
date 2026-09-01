from app.config.settings import Settings
from app.main import create_app
from httpx import ASGITransport, AsyncClient


async def test_liveness_has_envelope_request_id_and_security_headers() -> None:
    app = create_app(Settings(_env_file=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live", headers={"X-Request-ID": "req_test"})

    assert response.status_code == 200
    assert response.json() == {
        "data": {"status": "ok"},
        "meta": {"request_id": "req_test", "next_cursor": None, "has_more": None},
        "errors": [],
    }
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"] == "req_test"


async def test_protected_route_returns_stable_unauthorized_error() -> None:
    app = create_app(Settings(_env_file=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.headers["www-authenticate"] == "Bearer"
