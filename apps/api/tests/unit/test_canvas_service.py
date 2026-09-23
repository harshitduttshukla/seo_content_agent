from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from app.core.errors import BadRequestError, ConflictError, PermissionDenied
from app.domains.canvas.models import Argument, Canvas, Claim, ClaimRow
from app.domains.canvas.schemas import (
    ArgumentCreateRequest,
    CanvasAnchorType,
    CanvasAnchorUpsertRequest,
    CanvasClaimCreateRequest,
    ClaimCitationCreateRequest,
)
from app.domains.canvas.service import CanvasService
from app.domains.content_cards.models import ContentCard, ContentCardClaim
from app.domains.job_runs.models import JobRun
from app.security.principal import AuthenticatedUser, PermissionCode


@asynccontextmanager
async def passthrough_transaction(session: object):
    yield session


def actor(user_id: UUID | None = None) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id or uuid4(),
        issuer="https://identity.example.com",
        subject="canvas-test",
        email="canvas@example.com",
        display_name="Canvas Tester",
    )


@pytest.mark.asyncio
async def test_create_company_canvas_creates_empty_root_canvas() -> None:
    session = AsyncMock()
    service = CanvasService(session)
    organization_id = uuid4()
    project_id = uuid4()
    current_actor = actor()
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_company_canvas = AsyncMock(return_value=None)
    service.repository.add = MagicMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
    ):
        result = await service.create_company_canvas(
            organization_id,
            project_id,
            actor=current_actor,
        )

    created = service.repository.add.call_args.args[0]
    assert isinstance(created, Canvas)
    assert created.organization_id == organization_id
    assert created.project_id == project_id
    assert created.parent_id is None
    assert created.product_line is None
    assert result.id == created.id
    assert result.name == "Company canvas"
    assert result.arguments == []
    assert result.anchors == []
    service._authorization.require_project.assert_awaited_once_with(
        session,
        user_id=current_actor.user_id,
        organization_id=organization_id,
        project_id=project_id,
        permission=PermissionCode.STRATEGY_WRITE,
    )


@pytest.mark.asyncio
async def test_create_company_canvas_rejects_duplicate() -> None:
    service = CanvasService(AsyncMock())
    organization_id = uuid4()
    project_id = uuid4()
    current_actor = actor()
    existing = Canvas(
        id=uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        parent_id=None,
        product_line=None,
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_company_canvas = AsyncMock(return_value=existing)
    service.repository.add = MagicMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
        pytest.raises(ConflictError, match="already has a company canvas"),
    ):
        await service.create_company_canvas(
            organization_id,
            project_id,
            actor=current_actor,
        )

    service.repository.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_company_canvas_does_not_write_without_project_access() -> None:
    service = CanvasService(AsyncMock())
    current_actor = actor()
    service._authorization.require_project = AsyncMock(side_effect=PermissionDenied())
    service.repository.get_company_canvas = AsyncMock()
    service.repository.add = MagicMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
        pytest.raises(PermissionDenied),
    ):
        await service.create_company_canvas(
            uuid4(),
            uuid4(),
            actor=current_actor,
        )

    service.repository.get_company_canvas.assert_not_awaited()
    service.repository.add.assert_not_called()


@pytest.mark.asyncio
async def test_authoring_writes_anchor_argument_and_initial_claims() -> None:
    session = AsyncMock()
    service = CanvasService(session)
    organization_id = uuid4()
    project_id = uuid4()
    canvas_id = uuid4()
    current_actor = actor()
    canvas = Canvas(
        id=canvas_id,
        organization_id=organization_id,
        project_id=project_id,
        parent_id=None,
        product_line=None,
        company_anchor={},
        persona_anchor={},
        use_case_anchor={},
        alternative_anchor={},
        category_anchor={},
        problem_summary="",
        differentiation_summary="",
        version=1,
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_canvas_by_id = AsyncMock(return_value=canvas)
    service.repository.get_next_argument_order = AsyncMock(return_value=0)
    added: list[object] = []
    service.repository.add = MagicMock(side_effect=added.append)
    service.get_canvas = AsyncMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
    ):
        await service.upsert_anchor(
            organization_id,
            project_id,
            canvas_id,
            CanvasAnchorUpsertRequest(
                anchor_type=CanvasAnchorType.COMPANY,
                text="Acme",
                primary=True,
            ),
            actor=current_actor,
        )
        await service.create_argument(
            organization_id,
            project_id,
            canvas_id,
            ArgumentCreateRequest(
                sub_problem="Slow onboarding",
                differentiation_pillar="Automation",
                features=["Workflow templates"],
            ),
            actor=current_actor,
        )

    argument = next(item for item in added if isinstance(item, Argument))
    claims = [item for item in added if isinstance(item, Claim)]
    assert canvas.company_anchor == {"text": "Acme", "primary": True}
    assert argument.order == 0
    assert {claim.row for claim in claims} == {
        ClaimRow.SUB_PROBLEM,
        ClaimRow.PILLAR,
        ClaimRow.FEATURE,
    }
    assert all(claim.version == 1 and not claim.approved for claim in claims)


@pytest.mark.asyncio
async def test_anchor_save_requires_at_least_one_primary_anchor() -> None:
    service = CanvasService(AsyncMock())
    canvas = Canvas(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        parent_id=None,
        product_line=None,
        company_anchor={},
        persona_anchor={},
        use_case_anchor={},
        alternative_anchor={},
        category_anchor={},
        problem_summary="",
        differentiation_summary="",
        version=1,
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_canvas_by_id = AsyncMock(return_value=canvas)
    service.get_canvas = AsyncMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
        pytest.raises(BadRequestError, match="must be marked primary"),
    ):
        await service.upsert_anchor(
            canvas.organization_id,
            canvas.project_id,
            canvas.id,
            CanvasAnchorUpsertRequest(
                anchor_type=CanvasAnchorType.COMPANY,
                text="Acme",
                primary=False,
            ),
            actor=actor(),
        )

    assert canvas.company_anchor == {}


@pytest.mark.asyncio
async def test_anchor_save_cannot_remove_the_only_primary_anchor() -> None:
    service = CanvasService(AsyncMock())
    canvas = Canvas(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        parent_id=None,
        product_line=None,
        company_anchor={"text": "Acme", "primary": True},
        persona_anchor={},
        use_case_anchor={},
        alternative_anchor={},
        category_anchor={},
        problem_summary="",
        differentiation_summary="",
        version=1,
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_canvas_by_id = AsyncMock(return_value=canvas)
    service.get_canvas = AsyncMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
        pytest.raises(BadRequestError, match="must be marked primary"),
    ):
        await service.upsert_anchor(
            canvas.organization_id,
            canvas.project_id,
            canvas.id,
            CanvasAnchorUpsertRequest(
                anchor_type=CanvasAnchorType.COMPANY,
                text="Acme",
                primary=False,
            ),
            actor=actor(),
        )

    assert canvas.company_anchor == {"text": "Acme", "primary": True}


@pytest.mark.asyncio
async def test_create_summary_claim_updates_canvas_summary() -> None:
    session = AsyncMock()
    service = CanvasService(session)
    organization_id = uuid4()
    project_id = uuid4()
    canvas_id = uuid4()
    canvas = Canvas(
        id=canvas_id,
        organization_id=organization_id,
        project_id=project_id,
        parent_id=None,
        product_line=None,
        company_anchor={},
        persona_anchor={},
        use_case_anchor={},
        alternative_anchor={},
        category_anchor={},
        problem_summary="",
        differentiation_summary="",
        version=1,
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_canvas_by_id = AsyncMock(return_value=canvas)
    service.repository.get_current_claim_for_cell = AsyncMock(return_value=None)
    service.repository.add = MagicMock()
    service.get_canvas = AsyncMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
    ):
        await service.create_claim(
            organization_id,
            project_id,
            canvas_id,
            CanvasClaimCreateRequest(row="problem_summary", text="Teams lose time to handoffs."),
            actor=actor(),
        )

    created = service.repository.add.call_args.args[0]
    assert isinstance(created, Claim)
    assert created.row == ClaimRow.PROBLEM_SUMMARY
    assert created.version == 1
    assert canvas.problem_summary == "Teams lose time to handoffs."


@pytest.mark.asyncio
async def test_check_claim_edit_only_reads_citation_count() -> None:
    service = CanvasService(AsyncMock())
    current_actor = actor()
    claim = Claim(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        canvas_id=uuid4(),
        row=ClaimRow.PITCH,
        text="Original claim",
        evidence="Evidence",
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_claim_by_id = AsyncMock(return_value=claim)
    service.repository.get_citation_count = AsyncMock(return_value=7)
    service.repository.add = MagicMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
    ):
        result = await service.check_claim_edit(
            claim.organization_id,
            claim.project_id,
            claim.id,
            actor=current_actor,
        )

    assert result.citation_count == 7
    assert result.claim_text == "Original claim"
    service.repository.add.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_claim_edit_creates_new_version_and_job_run() -> None:
    session = AsyncMock()
    service = CanvasService(session)
    current_actor = actor()
    old_claim = Claim(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        canvas_id=uuid4(),
        row=ClaimRow.PITCH,
        text="Original claim",
        evidence="Old evidence",
        approved=True,
        version=4,
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_claim_by_id = AsyncMock(return_value=old_claim)
    added: list[object] = []

    def add(entity: object) -> None:
        added.append(entity)

    service.repository.add = MagicMock(side_effect=add)
    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
    ):
        result = await service.confirm_claim_edit(
            old_claim.organization_id,
            old_claim.project_id,
            old_claim.id,
            "New claim",
            "New evidence",
            current_actor,
        )

    new_claim = next(entity for entity in added if isinstance(entity, Claim))
    job_run = next(entity for entity in added if isinstance(entity, JobRun))
    assert new_claim.text == "New claim"
    assert new_claim.version == 5
    assert old_claim.text == "Original claim"
    assert old_claim.superseded_by == new_claim.id
    assert job_run.prompt_version == "v3.stale-claim-scan.v1"
    assert result.new_claim_id == new_claim.id


@pytest.mark.asyncio
async def test_create_pitch_claim_manual() -> None:
    session = AsyncMock()
    service = CanvasService(session)
    organization_id = uuid4()
    project_id = uuid4()
    canvas_id = uuid4()
    canvas = Canvas(
        id=canvas_id,
        organization_id=organization_id,
        project_id=project_id,
        parent_id=None,
        product_line=None,
        company_anchor={},
        persona_anchor={},
        use_case_anchor={},
        alternative_anchor={},
        category_anchor={},
        problem_summary="",
        differentiation_summary="",
        version=1,
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_canvas_by_id = AsyncMock(return_value=canvas)
    service.repository.get_current_claim_for_cell = AsyncMock(return_value=None)
    added: list[object] = []
    service.repository.add = MagicMock(side_effect=added.append)
    service.get_canvas = AsyncMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
    ):
        await service.create_claim(
            organization_id,
            project_id,
            canvas_id,
            CanvasClaimCreateRequest(
                row="pitch",
                text="Acme is the leading platform for automated workflow operations.",
                evidence="12 discovery calls",
            ),
            actor=actor(),
        )

    claim = next(item for item in added if isinstance(item, Claim))
    assert claim.row == ClaimRow.PITCH
    assert claim.text == "Acme is the leading platform for automated workflow operations."
    assert claim.evidence == "12 discovery calls"
    assert claim.approved is False
    assert claim.version == 1
    assert claim.argument_id is None


@pytest.mark.asyncio
async def test_approve_claim_updates_status_and_audits() -> None:
    session = AsyncMock()
    service = CanvasService(session)
    user_id = uuid4()
    current_actor = actor(user_id=user_id)
    claim = Claim(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        canvas_id=uuid4(),
        argument_id=None,
        row=ClaimRow.PITCH,
        text="The elevator pitch.",
        evidence="Some evidence",
        approved=False,
        version=1,
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_claim_by_id = AsyncMock(return_value=claim)
    service.repository.get_citation_count = AsyncMock(return_value=3)

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
    ):
        result = await service.approve_claim(
            claim.organization_id,
            claim.project_id,
            claim.id,
            actor=current_actor,
        )

    assert claim.approved is True
    assert claim.approved_by == user_id
    assert claim.approved_at is not None
    assert result.approved is True
    assert result.clm_number == "CLM-000"
    assert result.citation_count == 3


@pytest.mark.asyncio
async def test_list_content_cards() -> None:
    session = AsyncMock()
    service = CanvasService(session)
    org_id = uuid4()
    proj_id = uuid4()
    card = ContentCard(
        id=uuid4(),
        organization_id=org_id,
        project_id=proj_id,
        kind="cluster",
        title="Test Page",
        url="https://example.com/page",
        state="live",
        origin="manual",
    )
    service._authorization.require_project = AsyncMock(return_value="viewer")
    service.repository.get_project_content_cards = AsyncMock(return_value=[card])

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
    ):
        result = await service.list_content_cards(org_id, proj_id, actor=actor())

    assert len(result) == 1
    assert result[0].id == card.id
    assert result[0].title == "Test Page"
    assert result[0].state == "live"


@pytest.mark.asyncio
async def test_add_citation_links_content_card_and_increments_count() -> None:
    session = AsyncMock()
    service = CanvasService(session)
    org_id = uuid4()
    proj_id = uuid4()
    claim_id = uuid4()
    card_id = uuid4()

    claim = Claim(
        id=claim_id,
        organization_id=org_id,
        project_id=proj_id,
        canvas_id=uuid4(),
        argument_id=None,
        row=ClaimRow.PITCH,
        text="Pitch text",
        evidence="",
        approved=True,
        version=1,
    )
    card = ContentCard(
        id=card_id,
        organization_id=org_id,
        project_id=proj_id,
        kind="cluster",
        title="Live Page",
        url="https://example.com/live",
        state="live",
        origin="manual",
    )
    service._authorization.require_project = AsyncMock(return_value="editor")
    service.repository.get_claim_by_id = AsyncMock(return_value=claim)
    service.repository.get_content_card_by_id = AsyncMock(return_value=card)
    service.repository.get_content_card_claim = AsyncMock(return_value=None)
    added: list[object] = []
    service.repository.add = MagicMock(side_effect=added.append)
    service.get_claim_drilldown = AsyncMock()

    with (
        patch("app.domains.canvas.service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.service.set_actor_context", AsyncMock()),
    ):
        await service.add_citation(
            org_id,
            proj_id,
            claim_id,
            ClaimCitationCreateRequest(content_card_id=card_id),
            actor=actor(),
        )

    link = next(item for item in added if isinstance(item, ContentCardClaim))
    assert link.content_card_id == card_id
    assert link.claim_id == claim_id
