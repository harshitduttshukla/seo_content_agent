"""API routes for the Content Harness testing and evaluation environment."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content_harness.schemas import (
    ContentHarnessComparison,
    ContentHarnessComparisonRequest,
    ContentHarnessInput,
    ContentHarnessRunDetail,
    ContentHarnessRunListItem,
    EvaluateContentRequest,
    HarnessScorecard,
    V3DraftHarnessInput,
    V3OutlineHarnessInput,
    V3ProductionHarnessInput,
)
from app.domains.content_harness.service import ContentHarnessService
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/content-harness", tags=["content-harness"])


@router.post(
    "/runs",
    response_model=ApiResponse[ContentHarnessRunDetail],
    status_code=201,
)
async def create_harness_run(
    payload: ContentHarnessInput,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentHarnessRunDetail]:
    """Executes a content harness test run and returns complete findings and score."""
    detail = await ContentHarnessService().run_harness(
        session,
        actor=actor,
        input_data=payload,
    )
    return success(request, detail)


@router.get(
    "/runs",
    response_model=ApiResponse[list[ContentHarnessRunListItem]],
)
async def list_harness_runs(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ApiResponse[list[ContentHarnessRunListItem]]:
    """Lists past harness test runs for a project."""
    runs = await ContentHarnessService().list_runs(
        session,
        actor=actor,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )
    return success(request, runs)


@router.get(
    "/runs/{run_id}",
    response_model=ApiResponse[ContentHarnessRunDetail],
)
async def get_harness_run(
    run_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentHarnessRunDetail]:
    """Retrieves full details of a specific harness run by ID."""
    detail = await ContentHarnessService().get_run(
        session,
        actor=actor,
        project_id=project_id,
        run_id=run_id,
    )
    return success(request, detail)


@router.post(
    "/runs/compare",
    response_model=ApiResponse[ContentHarnessComparison],
)
async def compare_harness_runs(
    payload: ContentHarnessComparisonRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentHarnessComparison]:
    """Compares two harness runs side-by-side to highlight score and finding deltas."""
    comparison = await ContentHarnessService().compare_runs(
        session,
        actor=actor,
        project_id=payload.project_id,
        run_id_a=payload.run_id_a,
        run_id_b=payload.run_id_b,
    )
    return success(request, comparison)


@router.post(
    "/evaluate",
    response_model=ApiResponse[HarnessScorecard],
)
async def evaluate_content_endpoint(
    payload: EvaluateContentRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[HarnessScorecard]:
    """Evaluates content deterministically without triggering AI generation."""
    scorecard = await ContentHarnessService().evaluate_content_direct(
        session,
        actor=actor,
        payload=payload,
    )
    return success(request, scorecard)


@router.get(
    "/golden-cases",
    response_model=ApiResponse[list[dict[str, Any]]],
)
async def list_golden_cases_endpoint(
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[list[dict[str, Any]]]:
    """Lists available pre-defined golden test cases."""
    cases = ContentHarnessService().list_golden_cases()
    return success(request, cases)


@router.post(
    "/golden-cases/{case_id}/run",
    response_model=ApiResponse[ContentHarnessRunDetail],
    status_code=201,
)
async def run_golden_case_endpoint(
    case_id: str,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentHarnessRunDetail]:
    """Executes a pre-defined golden test case for a given project."""
    detail = await ContentHarnessService().run_golden_case(
        session,
        actor=actor,
        project_id=project_id,
        case_id=case_id,
    )
    return success(request, detail)


@router.post(
    "/v3-outline-runs",
    response_model=ApiResponse[ContentHarnessRunDetail],
    status_code=201,
)
async def create_v3_outline_run(
    payload: V3OutlineHarnessInput,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentHarnessRunDetail]:
    """Runs the production V3 outline contract on a ContentCard and scores it."""
    detail = await ContentHarnessService().run_v3_outline(session, actor=actor, input_data=payload)
    return success(request, detail)


@router.post(
    "/v3-draft-runs",
    response_model=ApiResponse[ContentHarnessRunDetail],
    status_code=201,
)
async def create_v3_draft_run(
    payload: V3DraftHarnessInput,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentHarnessRunDetail]:
    """Runs the production V3 draft contract on a ContentCard's saved outline and scores it."""
    detail = await ContentHarnessService().run_v3_draft(session, actor=actor, input_data=payload)
    return success(request, detail)


@router.post(
    "/v3-production-runs",
    response_model=ApiResponse[ContentHarnessRunDetail],
    status_code=201,
)
async def create_v3_production_run(
    payload: V3ProductionHarnessInput,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentHarnessRunDetail]:
    """Runs production QA, repair or section regeneration on a drafted card and scores it."""
    detail = await ContentHarnessService().run_v3_production(
        session, actor=actor, input_data=payload
    )
    return success(request, detail)
