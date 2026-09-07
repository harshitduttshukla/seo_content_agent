"""API integration tests for Phase 6: AI Orchestrator Workflows, Steps,

Approvals, Tools, and Tenant Boundaries.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.orchestrator.models import StepStatus, WorkflowIntent, WorkflowStatus
from app.domains.orchestrator.schemas import (
    WorkflowDetail,
    WorkflowStepDetail,
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


@pytest.mark.asyncio
async def test_orchestrator_tools_endpoint(
    test_app: FastAPI, test_actor: AuthenticatedUser
) -> None:
    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
        return_value=test_actor,
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(
                "/api/v1/orchestrator/tools",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert isinstance(data, list)
            names = [t["name"] for t in data]
            assert "read_document" in names
            assert "seo_quality_check" in names
            assert "find_link_opportunities" in names


@pytest.mark.asyncio
async def test_orchestrator_workflow_api_flow(
    test_app: FastAPI, test_actor: AuthenticatedUser
) -> None:
    doc_id = uuid4()
    org_id = uuid4()
    proj_id = uuid4()
    wf_id = uuid4()
    step_id = uuid4()
    proposal_id = uuid4()

    mock_step = WorkflowStepDetail(
        id=step_id,
        workflow_id=wf_id,
        step_index=0,
        step_type="tool_call",
        tool_name="read_document",
        status=StepStatus.COMPLETED,
        input={"document_id": doc_id},
        output={"title": "Test Doc", "word_count": 500},
    )

    mock_wf_detail = WorkflowDetail(
        id=wf_id,
        organization_id=org_id,
        project_id=proj_id,
        document_id=doc_id,
        created_by_id=test_actor.user_id,
        intent=WorkflowIntent.MULTI_STEP_CONTENT_TASK.value,
        status=WorkflowStatus.WAITING_FOR_APPROVAL,
        current_step=1,
        plan=[
            {
                "step_index": 0,
                "tool_name": "read_document",
                "risk_level": "READ",
                "requires_approval": False,
            },
            {
                "step_index": 1,
                "tool_name": "rewrite_section",
                "risk_level": "WRITE",
                "requires_approval": True,
            },
        ],
        result={"read_document": {"title": "Test Doc"}},
        error=None,
        token_usage={"total_tokens": 350},
        steps=[mock_step],
        pending_proposal_id=proposal_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
        return_value=test_actor,
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. POST /api/v1/orchestrator/workflows
            with patch(
                "app.domains.orchestrator.orchestrator_service.OrchestratorService.initiate_workflow",
                AsyncMock(return_value=mock_wf_detail),
            ):
                resp = await client.post(
                    "/api/v1/orchestrator/workflows",
                    headers={"Authorization": "Bearer test-token"},
                    json={
                        "document_id": str(doc_id),
                        "message": "Optimize this article and add internal links",
                    },
                )
                assert resp.status_code == 201
                data = resp.json()["data"]
                assert data["id"] == str(wf_id)
                assert data["status"] == "WAITING_FOR_APPROVAL"

            # 2. GET /api/v1/orchestrator/workflows/{wf_id}
            with patch(
                "app.domains.orchestrator.orchestrator_service.OrchestratorService.get_workflow",
                AsyncMock(return_value=mock_wf_detail),
            ):
                resp = await client.get(
                    f"/api/v1/orchestrator/workflows/{wf_id}",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
                assert resp.json()["data"]["current_step"] == 1

            # 3. GET /api/v1/orchestrator/workflows/{wf_id}/steps
            with patch(
                "app.domains.orchestrator.orchestrator_service.OrchestratorService.list_workflow_steps",
                AsyncMock(return_value=[mock_step]),
            ):
                resp = await client.get(
                    f"/api/v1/orchestrator/workflows/{wf_id}/steps",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
                assert len(resp.json()["data"]) == 1
                assert resp.json()["data"][0]["tool_name"] == "read_document"

            # 4. POST /api/v1/orchestrator/workflows/{wf_id}/steps/{step_id}/approve
            mock_approved = mock_wf_detail.model_copy(
                update={"status": WorkflowStatus.COMPLETED, "current_step": 2}
            )
            with patch(
                "app.domains.orchestrator.orchestrator_service.OrchestratorService.approve_step",
                AsyncMock(return_value=mock_approved),
            ):
                resp = await client.post(
                    f"/api/v1/orchestrator/workflows/{wf_id}/steps/{step_id}/approve",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
                assert resp.json()["data"]["status"] == "COMPLETED"

            # 5. POST /api/v1/orchestrator/workflows/{wf_id}/steps/{step_id}/reject
            mock_rejected = mock_wf_detail.model_copy(
                update={"status": WorkflowStatus.COMPLETED, "current_step": 2}
            )
            with patch(
                "app.domains.orchestrator.orchestrator_service.OrchestratorService.reject_step",
                AsyncMock(return_value=mock_rejected),
            ):
                resp = await client.post(
                    f"/api/v1/orchestrator/workflows/{wf_id}/steps/{step_id}/reject",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200

            # 6. POST /api/v1/orchestrator/workflows/{wf_id}/cancel
            mock_cancelled = mock_wf_detail.model_copy(update={"status": WorkflowStatus.CANCELLED})
            with patch(
                "app.domains.orchestrator.orchestrator_service.OrchestratorService.cancel_workflow",
                AsyncMock(return_value=mock_cancelled),
            ):
                resp = await client.post(
                    f"/api/v1/orchestrator/workflows/{wf_id}/cancel",
                    headers={"Authorization": "Bearer test-token"},
                    json={"reason": "Testing cancellation"},
                )
                assert resp.status_code == 200
                assert resp.json()["data"]["status"] == "CANCELLED"

            # 7. POST /api/v1/orchestrator/workflows/{wf_id}/resume
            with patch(
                "app.domains.orchestrator.orchestrator_service.OrchestratorService.resume_workflow",
                AsyncMock(return_value=mock_wf_detail),
            ):
                resp = await client.post(
                    f"/api/v1/orchestrator/workflows/{wf_id}/resume",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
