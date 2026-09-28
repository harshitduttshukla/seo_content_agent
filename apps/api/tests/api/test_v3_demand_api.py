from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.demand.schemas import (
    BulkUpdateResponse,
    DemandImportResponse,
    DemandNodeListResponse,
    DemandSummaryCounts,
    PageMetadata,
)
from app.main import create_app
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from httpx import ASGITransport, AsyncClient


class MockTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://identity.example.com",
            subject="demand-test",
            email="demand@example.com",
            display_name="Demand Tester",
        )


@pytest.mark.asyncio
async def test_demand_list_import_and_bulk_routes_are_scoped() -> None:
    organization_id = uuid4()
    project_id = uuid4()
    node_id = uuid4()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="demand-test",
        email="demand@example.com",
        display_name="Demand Tester",
    )
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    empty = DemandNodeListResponse(
        items=[],
        summary=DemandSummaryCounts(
            total_discarded=0,
            below_065_confidence=0,
            total_kept=0,
            gsc_striking_distance_count=0,
        ),
        meta=PageMetadata(total_count=0, page=1, page_size=100),
    )
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch("app.domains.demand.service.DemandService.list_nodes", AsyncMock(return_value=empty)),
        patch(
            "app.domains.demand.service.DemandService.import_nodes",
            AsyncMock(
                return_value=DemandImportResponse(
                    created_count=1, existing_count=0, job_run_id=uuid4()
                )
            ),
        ),
        patch(
            "app.domains.demand.service.DemandService.bulk_set_pending_classify",
            AsyncMock(return_value=BulkUpdateResponse(updated_count=1, job_run_id=uuid4())),
        ),
    ):
        query = f"organization_id={organization_id}&project_id={project_id}"
        headers = {"Authorization": "Bearer token"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listed = await client.get(f"/api/v3/demand?{query}", headers=headers)
            imported = await client.post(
                f"/api/v3/demand/import?{query}",
                headers=headers,
                json={"items": [{"text": "cross-border SEO", "type": "keyword"}]},
            )
            updated = await client.post(
                f"/api/v3/demand/bulk/pending-classify?{query}",
                headers=headers,
                json={"node_ids": [str(node_id)]},
            )
    assert listed.status_code == 200
    assert imported.json()["data"]["created_count"] == 1
    assert updated.json()["data"]["updated_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filter_name", "filter_value", "service_name"),
    [
        ("origin", "upload", "origin"),
        ("area_id", uuid4(), "area_id"),
        ("argument_id", uuid4(), "argument_id"),
        ("type", "keyword", "node_type"),
        ("funnel", "mofu", "funnel"),
    ],
)
async def test_demand_list_individual_filters_are_forwarded(
    filter_name: str, filter_value: str | object, service_name: str
) -> None:
    organization_id = uuid4()
    project_id = uuid4()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="demand-test",
        email="demand@example.com",
        display_name="Demand Tester",
    )
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    response = DemandNodeListResponse(
        items=[],
        summary=DemandSummaryCounts(
            total_discarded=0,
            below_065_confidence=0,
            total_kept=0,
            gsc_striking_distance_count=0,
        ),
        meta=PageMetadata(total_count=0, page=1, page_size=100),
    )
    list_nodes = AsyncMock(return_value=response)
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch("app.domains.demand.service.DemandService.list_nodes", list_nodes),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            result = await client.get(
                "/api/v3/demand",
                headers={"Authorization": "Bearer token"},
                params={
                    "organization_id": str(organization_id),
                    "project_id": str(project_id),
                    filter_name: str(filter_value),
                    "sort": "confidence_asc",
                },
            )

    assert result.status_code == 200
    args = list_nodes.await_args.args
    kwargs = list_nodes.await_args.kwargs
    assert args[:2] == (organization_id, project_id)
    assert kwargs[service_name] == filter_value
    assert kwargs["status"] is None
    assert kwargs["page"] == 1
    assert kwargs["page_size"] == 100
    assert kwargs["actor"] == actor


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "destination_key"),
    [("reassign_area", "area_id"), ("set_argument", "argument_id")],
)
async def test_demand_bulk_destination_actions_are_forwarded(
    action: str, destination_key: str
) -> None:
    organization_id = uuid4()
    project_id = uuid4()
    node_id = uuid4()
    destination_id = uuid4()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="demand-test",
        email="demand@example.com",
        display_name="Demand Tester",
    )
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    bulk_action = AsyncMock(return_value=BulkUpdateResponse(updated_count=1, job_run_id=uuid4()))
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch("app.domains.demand.service.DemandService.bulk_action", bulk_action),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            result = await client.post(
                "/api/v3/demand/bulk",
                headers={"Authorization": "Bearer token"},
                params={"organization_id": str(organization_id), "project_id": str(project_id)},
                json={
                    "ids": [str(node_id)],
                    "action": action,
                    destination_key: str(destination_id),
                },
            )

    assert result.status_code == 200
    args = bulk_action.await_args.args
    assert args[:2] == (organization_id, project_id)
    assert getattr(args[2], destination_key) == destination_id
    assert args[3] == actor


@pytest.mark.asyncio
async def test_demand_csv_mapping_route_is_scoped() -> None:
    from app.domains.demand.schemas import DemandCsvMappingResponse

    organization_id, project_id = uuid4(), uuid4()
    actor = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="v3-test",
        email="v3@example.com",
        display_name="V3 Tester",
    )
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    get_mapping = AsyncMock(
        return_value=DemandCsvMappingResponse(column_mapping={"text": "Keyword"})
    )
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch("app.domains.demand.service.DemandService.get_csv_mapping", get_mapping),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v3/demand/csv-mapping",
                headers={"Authorization": "Bearer token"},
                params={"organization_id": str(organization_id), "project_id": str(project_id)},
            )

    assert response.status_code == 200
    assert response.json()["data"]["column_mapping"] == {"text": "Keyword"}
    assert get_mapping.await_args.args == (organization_id, project_id, actor)
