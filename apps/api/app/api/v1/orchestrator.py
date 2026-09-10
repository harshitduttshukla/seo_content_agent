"""API routes for AI Orchestrator workflows, steps, approvals, and tools."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.orchestrator.orchestrator_service import OrchestratorService
from app.domains.orchestrator.schemas import (
    OrchestratorRequest,
    ToolDescriptorDTO,
    WorkflowCancelRequest,
    WorkflowDetail,
    WorkflowResumeRequest,
    WorkflowStepDetail,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


@router.post(
    "/workflows",
    response_model=ApiResponse[WorkflowDetail],
    status_code=201,
)
async def create_workflow(
    payload: OrchestratorRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[WorkflowDetail]:
    """Creates, plans, and executes an AI workflow."""
    detail = await OrchestratorService().initiate_workflow(
        session,
        actor=actor,
        request=payload,
    )
    return success(request, detail)


@router.get(
    "/workflows/{workflow_id}",
    response_model=ApiResponse[WorkflowDetail],
)
async def get_workflow(
    workflow_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[WorkflowDetail]:
    """Retrieves workflow status, plan, and accumulated tool results."""
    detail = await OrchestratorService().get_workflow(
        session,
        actor=actor,
        workflow_id=workflow_id,
    )
    return success(request, detail)


@router.post(
    "/workflows/{workflow_id}/cancel",
    response_model=ApiResponse[WorkflowDetail],
)
async def cancel_workflow(
    workflow_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    payload: WorkflowCancelRequest | None = None,
) -> ApiResponse[WorkflowDetail]:
    """Cancels an in-progress or waiting workflow."""
    reason = payload.reason if payload else "User cancelled"
    detail = await OrchestratorService().cancel_workflow(
        session,
        actor=actor,
        workflow_id=workflow_id,
        reason=reason,
    )
    return success(request, detail)


@router.post(
    "/workflows/{workflow_id}/resume",
    response_model=ApiResponse[WorkflowDetail],
)
async def resume_workflow(
    workflow_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    payload: WorkflowResumeRequest | None = None,
) -> ApiResponse[WorkflowDetail]:
    """Resumes a paused or failed workflow."""
    detail = await OrchestratorService().resume_workflow(
        session,
        actor=actor,
        workflow_id=workflow_id,
    )
    return success(request, detail)


@router.get(
    "/workflows/{workflow_id}/steps",
    response_model=ApiResponse[list[WorkflowStepDetail]],
)
async def list_workflow_steps(
    workflow_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[list[WorkflowStepDetail]]:
    """Lists ordered steps and tool execution outputs for a workflow."""
    steps = await OrchestratorService().list_workflow_steps(
        session,
        actor=actor,
        workflow_id=workflow_id,
    )
    return success(request, steps)


@router.get(
    "/tools",
    response_model=ApiResponse[list[ToolDescriptorDTO]],
)
@router.get(
    "/workflows/{workflow_id}/tools",
    response_model=ApiResponse[list[ToolDescriptorDTO]],
)
async def list_tools(
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    workflow_id: UUID | None = None,
) -> ApiResponse[list[ToolDescriptorDTO]]:
    """Lists complete registered tool contracts and execution metadata."""
    tools = OrchestratorService().list_tools()
    return success(request, tools)


@router.post(
    "/workflows/{workflow_id}/steps/{step_id}/approve",
    response_model=ApiResponse[WorkflowDetail],
)
async def approve_workflow_step(
    workflow_id: UUID,
    step_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[WorkflowDetail]:
    """Approves a waiting write action, applies the patch, verifies consistency,
    and resumes workflow.
    """
    detail = await OrchestratorService().approve_step(
        session,
        actor=actor,
        workflow_id=workflow_id,
        step_id=step_id,
    )
    return success(request, detail)


@router.post(
    "/workflows/{workflow_id}/steps/{step_id}/reject",
    response_model=ApiResponse[WorkflowDetail],
)
async def reject_workflow_step(
    workflow_id: UUID,
    step_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[WorkflowDetail]:
    """Rejects a waiting step proposal and terminates the workflow safely."""
    detail = await OrchestratorService().reject_step(
        session,
        actor=actor,
        workflow_id=workflow_id,
        step_id=step_id,
    )
    return success(request, detail)
