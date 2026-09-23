"""Route-level tests for POST /api/v3/demand/plan/preview and /api/v3/demand/plan."""

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from app.domains.demand.schemas import PlanKindCounts, PlanPreviewResponse, PlanResultResponse
from app.security.principal import AuthenticatedUser
from httpx import ASGITransport, AsyncClient, Response
from tests.api.test_v3_strategy_map_api import build_client_app


def _preview() -> PlanPreviewResponse:
    return PlanPreviewResponse(
        selected_count=2,
        eligible_count=1,
        skipped_count=1,
        totals=PlanKindCounts(pillar=1),
        groups=[],
        skipped=[],
        deferred=["refresh deferred"],
    )


async def _post(
    path: str, body: dict[str, object], service_method: str, result: object
) -> tuple[Response, AsyncMock, tuple[UUID, UUID, AuthenticatedUser]]:
    organization_id, project_id = uuid4(), uuid4()
    app, actor = build_client_app()
    service = AsyncMock(return_value=result)
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch(f"app.domains.demand.service.DemandService.{service_method}", service),
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v3/demand/{path}?organization_id={organization_id}&project_id={project_id}",
                json=body,
                headers={"Authorization": "Bearer token"},
            )
    return response, service, (organization_id, project_id, actor)


@pytest.mark.asyncio
async def test_preview_route_returns_the_enveloped_preview() -> None:
    node_ids = [str(uuid4()), str(uuid4())]
    response, service, (org, project, _actor) = await _post(
        "plan/preview", {"node_ids": node_ids}, "preview_plan", _preview()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["totals"]["pillar"] == 1
    assert body["data"]["deferred"] == ["refresh deferred"]
    service.assert_awaited_once()
    assert service.await_args is not None
    assert service.await_args.args[:2] == (org, project)
    assert [str(i) for i in service.await_args.args[2]] == node_ids


@pytest.mark.asyncio
async def test_confirm_route_returns_created_cards_and_job_run() -> None:
    result = PlanResultResponse(
        **_preview().model_dump(),
        created_count=1,
        created_card_ids=[uuid4()],
        job_run_id=uuid4(),
    )
    response, service, _ = await _post("plan", {"node_ids": [str(uuid4())]}, "confirm_plan", result)

    assert response.status_code == 200
    assert response.json()["data"]["created_count"] == 1
    service.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{"node_ids": []}, {}, {"node_ids": ["not-a-uuid"]}])
async def test_plan_routes_reject_an_invalid_selection(body: dict[str, object]) -> None:
    for path, method in (("plan/preview", "preview_plan"), ("plan", "confirm_plan")):
        response, service, _ = await _post(path, body, method, None)
        assert response.status_code == 422
        service.assert_not_awaited()


@pytest.mark.asyncio
async def test_plan_routes_require_authentication() -> None:
    app, _ = build_client_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("plan/preview", "plan"):
            response = await client.post(
                f"/api/v3/demand/{path}?organization_id={uuid4()}&project_id={uuid4()}",
                json={"node_ids": [str(uuid4())]},
            )
            assert response.status_code == 401
