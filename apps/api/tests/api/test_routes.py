from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.users.schemas import UserDetail
from app.main import create_app
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from httpx import ASGITransport, AsyncClient


class MockTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://identity.example.com",
            subject="test-user-sub",
            email="tester@example.com",
            display_name="Tester",
        )


@pytest.mark.asyncio
async def test_users_me_route() -> None:
    user_id = uuid4()
    mock_detail = UserDetail(
        id=user_id,
        email="tester@example.com",
        display_name="Tester",
        status="active",
        created_at=datetime.now(UTC),
        last_seen_at=None,
    )

    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
    )
    engine = AsyncMock()
    app = create_app(settings, engine=engine, token_verifier=MockTokenVerifier())

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.domains.users.service.UserService.detail",
            new_callable=AsyncMock,
        ) as mock_user_detail,
    ):
        mock_resolve.return_value = AuthenticatedUser(
            user_id=user_id,
            issuer="https://identity.example.com",
            subject="test-user-sub",
            email="tester@example.com",
            display_name="Tester",
        )
        mock_user_detail.return_value = mock_detail

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["email"] == "tester@example.com"
            assert data["data"]["id"] == str(user_id)
            assert "errors" in data
            assert len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_create_organization_validation_error() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
    )
    engine = AsyncMock()
    app = create_app(settings, engine=engine, token_verifier=MockTokenVerifier())

    user_id = uuid4()
    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
    ) as mock_resolve:
        mock_resolve.return_value = AuthenticatedUser(
            user_id=user_id,
            issuer="https://identity.example.com",
            subject="test-user-sub",
            email="tester@example.com",
            display_name="Tester",
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Missing Idempotency-Key
            response = await client.post(
                "/api/v1/organizations",
                headers={"Authorization": "Bearer token"},
                json={"name": "A"},  # Name too short
            )
            assert response.status_code == 422
            assert response.json()["errors"][0]["code"] == "VALIDATION_ERROR"
