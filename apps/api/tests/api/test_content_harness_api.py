"""API integration tests for Content Harness routes, scoring, and tenant boundaries."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.core.errors import PermissionDenied, ResourceNotFound
from app.domains.content_harness.schemas import (
    ContentHarnessComparison,
    ContentHarnessRunDetail,
    ContentHarnessRunListItem,
    HarnessFinding,
    HarnessScorecard,
)
from app.main import create_app
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class MockTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://identity.example.com",
            subject="test-user-sub",
            email="tester@example.com",
            display_name="Tester",
        )


@pytest.fixture
def test_app() -> FastAPI:
    settings = Settings(
        _env_file=None,
        app_env="testing",
        jwt_secret_key="test-secret-key-that-is-at-least-32-chars",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        redis_url="redis://localhost:6379/0",
    )
    app = create_app(settings)
    app.state.token_verifier = MockTokenVerifier()
    return app


@pytest.fixture
def test_actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-user-sub",
        email="tester@example.com",
        display_name="Tester",
    )


@pytest.fixture
def sample_run_detail() -> ContentHarnessRunDetail:
    now = datetime.now(UTC)
    org_id = uuid4()
    proj_id = uuid4()
    run_id = uuid4()
    return ContentHarnessRunDetail(
        id=run_id,
        organization_id=org_id,
        project_id=proj_id,
        name="API Test Run",
        status="COMPLETED",
        prompt_version="v1",
        model="mock-v1",
        provider="mock",
        input_data={"primary_keyword": "fleet vehicle tracking"},
        context_data={"project_id": str(proj_id)},
        prompt_data={"system_prompt": "sys", "user_prompt": "user"},
        output_data={"title": "Fleet Vehicle Tracking Guide"},
        evaluation_data={
            "seo_score": 85.0,
            "content_score": 80.0,
            "brand_score": 100.0,
            "linking_score": 80.0,
            "technical_validity": "PASS",
            "overall_score": 85.5,
            "status": "PASS",
            "findings": [
                {
                    "category": "SEO",
                    "rule": "primary_keyword_in_title",
                    "status": "PASS",
                    "impact": "HIGH",
                    "message": "Keyword present",
                }
            ],
        },
        score=85.5,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_api_list_golden_cases(
    test_app: FastAPI,
    test_actor: AuthenticatedUser,
) -> None:
    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
        return_value=test_actor,
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(
                "/api/v1/content-harness/golden-cases",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert isinstance(data, list)
            assert len(data) == 6
            case_ids = [c["case_id"] for c in data]
            assert "case-1-normal-seo" in case_ids
            assert "case-6-invalid-output" in case_ids


@pytest.mark.asyncio
async def test_api_create_harness_run(
    test_app: FastAPI,
    test_actor: AuthenticatedUser,
    sample_run_detail: ContentHarnessRunDetail,
) -> None:
    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
        return_value=test_actor,
    ), patch(
        "app.domains.content_harness.service.ContentHarnessService.run_harness",
        new_callable=AsyncMock,
        return_value=sample_run_detail,
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            payload = {
                "project_id": str(sample_run_detail.project_id),
                "name": "Integration Test Run",
                "primary_keyword": "fleet vehicle tracking",
                "secondary_keywords": ["gps tracking"],
            }
            resp = await client.post(
                "/api/v1/content-harness/runs",
                headers={"Authorization": "Bearer test-token"},
                json=payload,
            )
            assert resp.status_code == 201
            res_data = resp.json()["data"]
            assert res_data["id"] == str(sample_run_detail.id)
            assert res_data["score"] == 85.5


@pytest.mark.asyncio
async def test_api_get_harness_run(
    test_app: FastAPI,
    test_actor: AuthenticatedUser,
    sample_run_detail: ContentHarnessRunDetail,
) -> None:
    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
        return_value=test_actor,
    ), patch(
        "app.domains.content_harness.service.ContentHarnessService.get_run",
        new_callable=AsyncMock,
        return_value=sample_run_detail,
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(
                f"/api/v1/content-harness/runs/{sample_run_detail.id}?project_id={sample_run_detail.project_id}",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["id"] == str(sample_run_detail.id)


@pytest.mark.asyncio
async def test_api_compare_runs(
    test_app: FastAPI,
    test_actor: AuthenticatedUser,
    sample_run_detail: ContentHarnessRunDetail,
) -> None:
    comparison = ContentHarnessComparison(
        run_a=sample_run_detail,
        run_b=sample_run_detail,
        score_diffs={"overall": 0.0, "seo": 0.0, "content": 0.0, "brand": 0.0, "linking": 0.0},
        improvements=[],
        regressions=[],
        summary="No score difference",
    )

    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
        return_value=test_actor,
    ), patch(
        "app.domains.content_harness.service.ContentHarnessService.compare_runs",
        new_callable=AsyncMock,
        return_value=comparison,
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/v1/content-harness/runs/compare",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "project_id": str(sample_run_detail.project_id),
                    "run_id_a": str(sample_run_detail.id),
                    "run_id_b": str(sample_run_detail.id),
                },
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["summary"] == "No score difference"


@pytest.mark.asyncio
async def test_api_tenant_isolation_negative_denial(
    test_app: FastAPI,
    test_actor: AuthenticatedUser,
) -> None:
    """Verifies that an unauthorized project/tenant attempt is denied with 404 or 403."""
    foreign_proj_id = uuid4()

    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
        return_value=test_actor,
    ), patch(
        "app.domains.content_harness.service.ContentHarnessService.run_harness",
        side_effect=ResourceNotFound("project"),
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/v1/content-harness/runs",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "project_id": str(foreign_proj_id),
                    "primary_keyword": "cross tenant test",
                },
            )
            assert resp.status_code == 404
            assert resp.json()["errors"][0]["code"] in ("PROJECT_NOT_FOUND", "RESOURCE_NOT_FOUND")


@pytest.mark.asyncio
async def test_api_unauthorized_without_token(
    test_app: FastAPI,
) -> None:
    """Verifies that an unauthenticated request is rejected."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/content-harness/golden-cases")
        assert resp.status_code == 401
