"""Route-level tests for POST /api/v3/plan/lock."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.domains.projects.schemas import PlanLockState
from httpx import ASGITransport, AsyncClient
from tests.api.test_v3_strategy_map_api import build_client_app

SERVER_TIME = datetime(2026, 9, 24, 10, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_lock_route_returns_the_lock_state_and_ignores_a_client_timestamp() -> None:
    organization_id, project_id = uuid4(), uuid4()
    app, actor = build_client_app()
    service = AsyncMock(
        return_value=PlanLockState(
            project_id=project_id, plan_locked_at=SERVER_TIME, locked_now=True
        )
    )
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch("app.domains.projects.service.ProjectService.lock_plan", service),
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v3/plan/lock?organization_id={organization_id}&project_id={project_id}"
                "&plan_locked_at=1999-01-01T00:00:00Z",
                json={"plan_locked_at": "1999-01-01T00:00:00Z"},
                headers={"Authorization": "Bearer token"},
            )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["plan_locked_at"].startswith("2026-09-24T10:00:00")
    assert data["locked_now"] is True
    # The service receives scope and actor only — there is no timestamp to pass.
    service.assert_awaited_once()
    assert service.await_args is not None
    assert set(service.await_args.kwargs) == {
        "actor",
        "organization_id",
        "project_id",
        "request_id",
    }
    assert service.await_args.kwargs["organization_id"] == organization_id
    assert service.await_args.kwargs["project_id"] == project_id


@pytest.mark.asyncio
async def test_lock_route_requires_authentication() -> None:
    app, _ = build_client_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v3/plan/lock?organization_id={uuid4()}&project_id={uuid4()}"
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_lock_route_requires_scope_parameters() -> None:
    app, actor = build_client_app()
    with patch(
        "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v3/plan/lock", headers={"Authorization": "Bearer token"}
            )
    assert response.status_code == 422
