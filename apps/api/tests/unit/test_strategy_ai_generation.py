"""Unit and integration tests for AI-Generated SEO Strategy V1."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.ai.provider import GenerationResult, Usage
from app.core.errors import DomainError, PermissionDenied
from app.domains.ai.service import MockAIProvider
from app.domains.projects.models import Project
from app.domains.strategy.models import SEOStrategy, SEOStrategyVersion, StrategyStatus
from app.domains.strategy.schemas import StrategyDataSchema, StrategyUpdateRequest
from app.domains.strategy.service import SEOStrategyService
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
    return session


@pytest.fixture
def mock_actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-sub",
        email="test@example.com",
        display_name="Test User",
    )


@pytest.fixture
def mock_project() -> Project:
    p = Project()
    p.id = uuid4()
    p.organization_id = uuid4()
    p.name = "FleetIQ Telematics"
    p.description = "Advanced diagnostic and fleet optimization platform."
    p.slug = "fleetiq"
    p.default_locale = "en"
    p.default_country = "US"
    p.status = "active"
    return p


@pytest.mark.asyncio
async def test_generate_initial_strategy_draft_success(
    mock_actor: AuthenticatedUser,
    mock_project: Project,
) -> None:
    service = SEOStrategyService()
    session = make_mock_session()

    # Mock ProjectService.get_model
    service._projects.get_model = AsyncMock(return_value=mock_project)

    # Mock query executions
    mock_result_empty = MagicMock()
    mock_result_empty.scalars.return_value.all.return_value = []
    mock_result_empty.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result_empty)

    # Mock repository
    service._repository.get_by_project_id = AsyncMock(return_value=None)
    service._audit.add = MagicMock()

    with patch("app.domains.strategy.service.get_ai_provider", return_value=MockAIProvider()):
        draft = await service.generate_initial_strategy_draft(
            session,
            actor=mock_actor,
            project_id=mock_project.id,
            request_id="req-123",
        )

    assert isinstance(draft, StrategyDataSchema)
    assert draft.business_context.business_name == "FleetIQ Telematics"
    assert len(draft.products) >= 1
    assert len(draft.audience.personas) >= 1
    assert len(draft.seo_objectives) >= 1

    # Verify audit event recorded
    service._audit.add.assert_called_once()
    assert service._audit.add.call_args[1]["action"] == "strategy.ai_draft_generated"


@pytest.mark.asyncio
async def test_generate_initial_strategy_draft_does_not_save_to_database(
    mock_actor: AuthenticatedUser,
    mock_project: Project,
) -> None:
    service = SEOStrategyService()
    session = make_mock_session()

    service._projects.get_model = AsyncMock(return_value=mock_project)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    service._repository.get_by_project_id = AsyncMock(return_value=None)
    service._repository.create_strategy = AsyncMock()
    service._repository.create_version = AsyncMock()

    with patch("app.domains.strategy.service.get_ai_provider", return_value=MockAIProvider()):
        draft = await service.generate_initial_strategy_draft(
            session,
            actor=mock_actor,
            project_id=mock_project.id,
        )

    assert draft is not None
    # Verify that NO version or strategy row was created in DB
    service._repository.create_strategy.assert_not_called()
    service._repository.create_version.assert_not_called()


@pytest.mark.asyncio
async def test_generate_initial_strategy_draft_malformed_ai_output_fails_safely(
    mock_actor: AuthenticatedUser,
    mock_project: Project,
) -> None:
    service = SEOStrategyService()
    session = make_mock_session()

    service._projects.get_model = AsyncMock(return_value=mock_project)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    service._repository.get_by_project_id = AsyncMock(return_value=None)

    fake_bad_provider = MagicMock()
    fake_bad_provider.generate = AsyncMock(
        return_value=GenerationResult(
            text="I cannot fulfill this request because of XYZ",
            provider="fake",
            model="fake-1",
            usage=Usage(input_tokens=10, output_tokens=10),
            finish_reason="stop",
        )
    )

    with patch("app.domains.strategy.service.get_ai_provider", return_value=fake_bad_provider):
        with pytest.raises(DomainError) as exc_info:
            await service.generate_initial_strategy_draft(
                session,
                actor=mock_actor,
                project_id=mock_project.id,
            )
        assert exc_info.value.code == "MALFORMED_AI_OUTPUT"


@pytest.mark.asyncio
async def test_generate_initial_strategy_draft_cross_tenant_denied(
    mock_actor: AuthenticatedUser,
) -> None:
    service = SEOStrategyService()
    session = make_mock_session()

    service._projects.get_model = AsyncMock(
        side_effect=PermissionDenied("Cannot access project in another organization")
    )

    with pytest.raises(PermissionDenied):
        await service.generate_initial_strategy_draft(
            session,
            actor=mock_actor,
            project_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_version_1_and_version_2_lifecycle(
    mock_actor: AuthenticatedUser,
    mock_project: Project,
) -> None:
    service = SEOStrategyService()
    session = make_mock_session()
    service._projects.get_model = AsyncMock(return_value=mock_project)

    strategy_id = uuid4()
    existing_strat = SEOStrategy()
    existing_strat.id = strategy_id
    existing_strat.organization_id = mock_project.organization_id
    existing_strat.project_id = mock_project.id
    existing_strat.current_version = 1
    existing_strat.status = StrategyStatus.DRAFT
    existing_strat.revision = 1
    existing_strat.created_at = datetime.now(UTC)
    existing_strat.updated_at = datetime.now(UTC)

    template_v1 = SEOStrategyVersion()
    template_v1.id = uuid4()
    template_v1.strategy_id = strategy_id
    template_v1.organization_id = mock_project.organization_id
    template_v1.project_id = mock_project.id
    template_v1.version = 1
    template_v1.change_summary = "Initial strategy template initialized"
    template_v1.strategy_data = {}

    service._repository.get_by_project_id = AsyncMock(return_value=existing_strat)
    service._repository.get_latest_version = AsyncMock(return_value=template_v1)
    service._repository.create_version = AsyncMock()
    service._audit.add = MagicMock()
    service._outbox.add = MagicMock()

    # 1. User reviews AI draft and saves as Version 1
    v1_payload = StrategyUpdateRequest(
        change_summary="Initial SEO strategy reviewed and saved as Version 1",
        strategy_data=StrategyDataSchema(
            business_context={"business_name": "FleetIQ", "industry": "Fleet Tech"},
            seo_objectives=["Rank top 3 for OBD telematics"],
        ),
    )

    res_v1 = await service.update_strategy(
        session,
        actor=mock_actor,
        project_id=mock_project.id,
        payload=v1_payload,
    )

    assert res_v1.current_version == 1
    assert template_v1.change_summary == "Initial SEO strategy reviewed and saved as Version 1"
    assert existing_strat.status == StrategyStatus.ACTIVE
    # create_version shouldn't be called because v1 template was updated in-place
    service._repository.create_version.assert_not_called()
    assert service._audit.add.call_args[1]["action"] == "strategy.created"

    # 2. User edits Version 1 and saves -> Version 2
    v2_version_obj = SEOStrategyVersion()
    v2_version_obj.version = 2
    v2_version_obj.change_summary = "Added enterprise target market"
    service._repository.create_version = AsyncMock(return_value=v2_version_obj)
    template_v1.change_summary = "Initial SEO strategy reviewed and saved as Version 1"

    v2_payload = StrategyUpdateRequest(
        change_summary="Added enterprise target market",
        strategy_data=StrategyDataSchema(
            business_context={"business_name": "FleetIQ Enterprise", "industry": "Fleet Tech"},
        ),
    )

    res_v2 = await service.update_strategy(
        session,
        actor=mock_actor,
        project_id=mock_project.id,
        payload=v2_payload,
    )

    assert res_v2.current_version == 2
    service._repository.create_version.assert_called_once()
    assert service._repository.create_version.call_args[1]["version"] == 2
    assert service._audit.add.call_args[1]["action"] == "strategy.updated"
