from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.domains.ai.service import MockAIProvider
from app.domains.content_harness.fixtures import GOLDEN_TEST_CASES
from app.domains.content_harness.models import ContentHarnessRun
from app.domains.content_harness.repository import ContentHarnessRepository
from app.domains.content_harness.schemas import (
    ContentHarnessInput,
    EvaluateContentRequest,
    HarnessGeneratedContent,
)
from app.domains.content_harness.service import ContentHarnessService
from app.domains.projects.models import Project
from app.security.principal import AuthenticatedUser


def make_mock_session() -> MagicMock:
    session = MagicMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    session.begin.return_value = context_manager
    session.execute = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-sub",
        email="harness-test@example.com",
        display_name="Harness Tester",
    )


@pytest.fixture
def mock_project() -> Project:
    p = Project()
    p.id = uuid4()
    p.organization_id = uuid4()
    p.name = "FleetIQ Telematics"
    p.slug = "fleetiq"
    return p


@pytest.mark.asyncio
async def test_service_run_harness_success(
    mock_actor: AuthenticatedUser,
    mock_project: Project,
) -> None:
    session = make_mock_session()
    service = ContentHarnessService(provider=MockAIProvider())
    service._projects.get_model = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    input_data = ContentHarnessInput(
        project_id=mock_project.id,
        name="Unit Test Run",
        primary_keyword="fleet vehicle tracking",
        secondary_keywords=["gps fleet tracking"],
        prompt_version="v1",
    )

    detail = await service.run_harness(
        session,
        actor=mock_actor,
        input_data=input_data,
    )

    assert detail.project_id == mock_project.id
    assert detail.organization_id == mock_project.organization_id
    assert detail.prompt_version == "v1"
    assert detail.provider == "mock"
    assert detail.score is not None
    assert detail.score > 0
    assert detail.status in ("COMPLETED", "FAILED")
    assert "fleet vehicle tracking" in detail.output_data.get("title", "").lower()


@pytest.mark.asyncio
async def test_service_golden_case_1_normal_seo(
    mock_actor: AuthenticatedUser,
    mock_project: Project,
) -> None:
    session = make_mock_session()
    service = ContentHarnessService(provider=MockAIProvider())
    service._projects.get_model = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    detail = await service.run_golden_case(
        session,
        actor=mock_actor,
        project_id=mock_project.id,
        case_id="case-1-normal-seo",
    )

    assert detail.status == "COMPLETED"
    eval_data = detail.evaluation_data
    assert eval_data["technical_validity"] == "PASS"
    assert eval_data["seo_score"] >= 70.0


@pytest.mark.asyncio
async def test_service_golden_case_6_malformed_output(
    mock_actor: AuthenticatedUser,
    mock_project: Project,
) -> None:
    session = make_mock_session()
    service = ContentHarnessService(provider=MockAIProvider())
    service._projects.get_model = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    detail = await service.run_golden_case(
        session,
        actor=mock_actor,
        project_id=mock_project.id,
        case_id="case-6-invalid-output",
    )

    # Malformed output should be handled safely and status flagged
    assert detail.status == "FAILED"
    assert detail.error_message is not None
    assert "validation failed" in detail.error_message.lower() or "malformed" in detail.error_message.lower()
    eval_data = detail.evaluation_data
    assert eval_data["technical_validity"] == "FAIL"


@pytest.mark.asyncio
async def test_service_compare_runs(
    mock_actor: AuthenticatedUser,
    mock_project: Project,
) -> None:
    session = make_mock_session()
    repo = ContentHarnessRepository()
    service = ContentHarnessService(provider=MockAIProvider(), repository=repo)
    service._projects.get_model = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    run_a_id = uuid4()
    run_b_id = uuid4()

    run_a = ContentHarnessRun(
        id=run_a_id,
        organization_id=mock_project.organization_id,
        project_id=mock_project.id,
        name="Run A",
        status="COMPLETED",
        prompt_version="v1",
        model="mock-v1",
        provider="mock",
        input_data={},
        context_data={},
        prompt_data={},
        output_data={},
        evaluation_data={
            "overall_score": 70.0,
            "seo_score": 65.0,
            "content_score": 75.0,
            "brand_score": 80.0,
            "linking_score": 60.0,
            "findings": [
                {"rule": "primary_keyword_in_title", "status": "FAIL"},
                {"rule": "forbidden_words", "status": "PASS"},
            ],
        },
        score=70.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    run_b = ContentHarnessRun(
        id=run_b_id,
        organization_id=mock_project.organization_id,
        project_id=mock_project.id,
        name="Run B",
        status="COMPLETED",
        prompt_version="v2",
        model="mock-v1",
        provider="mock",
        input_data={},
        context_data={},
        prompt_data={},
        output_data={},
        evaluation_data={
            "overall_score": 85.0,
            "seo_score": 85.0,
            "content_score": 80.0,
            "brand_score": 90.0,
            "linking_score": 85.0,
            "findings": [
                {"rule": "primary_keyword_in_title", "status": "PASS"},
                {"rule": "forbidden_words", "status": "PASS"},
            ],
        },
        score=85.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    repo.get_by_id = AsyncMock(side_effect=[run_a, run_b])  # type: ignore[method-assign]

    comparison = await service.compare_runs(
        session,
        actor=mock_actor,
        project_id=mock_project.id,
        run_id_a=run_a_id,
        run_id_b=run_b_id,
    )

    assert comparison.score_diffs["overall"] == 15.0
    assert comparison.score_diffs["seo"] == 20.0
    assert len(comparison.improvements) == 1
    assert "primary_keyword_in_title" in comparison.improvements[0]
    assert len(comparison.regressions) == 0


@pytest.mark.asyncio
async def test_service_evaluate_content_direct(
    mock_actor: AuthenticatedUser,
    mock_project: Project,
) -> None:
    session = make_mock_session()
    service = ContentHarnessService(provider=MockAIProvider())
    service._projects.get_model = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    req = EvaluateContentRequest(
        project_id=mock_project.id,
        input_data=ContentHarnessInput(
            project_id=mock_project.id,
            primary_keyword="fleet diagnostics",
        ),
        content=HarnessGeneratedContent(
            title="Complete Guide to Fleet Diagnostics",
            content="fleet diagnostics is essential for fleet monitoring and maintenance.",
            sections=[],
        ),
    )

    scorecard = await service.evaluate_content_direct(
        session,
        actor=mock_actor,
        payload=req,
    )

    assert scorecard.seo_score > 0
