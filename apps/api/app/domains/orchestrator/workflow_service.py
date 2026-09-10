"""Workflow Service managing the state machine, execution loop, approval gates,

retries, idempotency, and audit logging.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.errors import BadRequestError, ConflictError, ResourceNotFound
from app.domains.audit.repository import AuditWriter
from app.domains.content.editor_models import (
    AIEditProposal,
    ContentDocument,
    ProposalStatus,
)
from app.domains.content.patch_service import DocumentPatchService
from app.domains.orchestrator.exceptions import (
    ToolExecutionError,
    WorkflowStateError,
)
from app.domains.orchestrator.models import (
    AIWorkflow,
    AIWorkflowStep,
    StepStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.policies import (
    DEFAULT_MAX_RETRIES,
    is_error_retryable,
    requires_human_approval,
)
from app.domains.orchestrator.schemas import (
    WorkflowDetail,
    WorkflowPlanStep,
    WorkflowStepDetail,
)
from app.domains.orchestrator.tool_executor import ToolExecutor
from app.domains.orchestrator.tool_registry import ToolRegistry
from app.domains.orchestrator.verification_service import VerificationService
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class WorkflowService:
    def __init__(
        self,
        tool_executor: ToolExecutor | None = None,
        tool_registry: ToolRegistry | None = None,
        patch_service: DocumentPatchService | None = None,
        verification_service: VerificationService | None = None,
    ) -> None:
        self._registry = tool_registry or ToolRegistry()
        self._executor = tool_executor or ToolExecutor(registry=self._registry)
        self._patches = patch_service or DocumentPatchService()
        self._verifier = verification_service or VerificationService()
        self._audit = AuditWriter()
        self._projects = ProjectService()

    async def create_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        project_id: UUID,
        document_id: UUID,
        intent: WorkflowIntent,
        plan_steps: list[WorkflowPlanStep],
    ) -> AIWorkflow:
        """Initializes a workflow record and its associated ordered steps."""
        # Validate project permissions
        await self._projects.get_model(
            session,
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.AI_USE,
        )

        workflow = AIWorkflow(
            organization_id=organization_id,
            project_id=project_id,
            document_id=document_id,
            created_by_id=actor.user_id,
            intent=intent.value,
            status=WorkflowStatus.PENDING.value,
            current_step=0,
            plan=[s.model_dump() for s in plan_steps],
            result={},
            token_usage={"total_tokens": 0},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(workflow)
        await session.flush()

        for s in plan_steps:
            step_record = AIWorkflowStep(
                workflow_id=workflow.id,
                step_index=s.step_index,
                step_type="tool_call",
                tool_name=s.tool_name,
                status=StepStatus.PENDING.value,
                input=s.input_arguments,
                output={},
            )
            session.add(step_record)

        await session.flush()

        await self._audit.log_event(
            session=session,
            actor_user_id=actor.user_id,
            action="workflow.created",
            resource_type="ai_workflow",
            resource_id=workflow.id,
            organization_id=organization_id,
            project_id=project_id,
            metadata={"intent": intent.value, "steps_count": len(plan_steps)},
        )

        return workflow

    async def run_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
    ) -> AIWorkflow:
        """Runs the bounded orchestration loop until completion or an approval gate."""
        workflow = await self._get_workflow_for_update(session, workflow_id)

        if workflow.status in (
            WorkflowStatus.COMPLETED.value,
            WorkflowStatus.CANCELLED.value,
        ):
            return workflow

        workflow.status = WorkflowStatus.RUNNING.value
        if not workflow.started_at:
            workflow.started_at = datetime.now(UTC)
        workflow.updated_at = datetime.now(UTC)
        await session.flush()

        await self._audit.log_event(
            session=session,
            actor_user_id=actor.user_id,
            action="workflow.started",
            resource_type="ai_workflow",
            resource_id=workflow.id,
            organization_id=workflow.organization_id,
            project_id=workflow.project_id,
            metadata={"current_step": workflow.current_step},
        )

        # Retrieve steps
        step_stmt = (
            select(AIWorkflowStep)
            .where(AIWorkflowStep.workflow_id == workflow.id)
            .order_by(AIWorkflowStep.step_index.asc())
        )
        step_res = await session.execute(step_stmt)
        steps = list(step_res.scalars().all())

        accumulated_results: dict[str, Any] = dict(workflow.result or {})

        for step in steps[workflow.current_step :]:
            if step.status == StepStatus.COMPLETED.value:
                continue

            tool = self._registry.get(step.tool_name)

            # Check Approval Gate for Write / Destructive actions
            if requires_human_approval(tool.risk_level):
                # Formulate and create AIEditProposal for human review
                proposal = await self._create_proposal_for_step(
                    session,
                    actor=actor,
                    workflow=workflow,
                    step=step,
                )

                step.status = StepStatus.WAITING_FOR_APPROVAL.value
                step.output = {
                    "proposal_id": str(proposal.id),
                    "operation_type": proposal.operation_type,
                    "target_block_ids": proposal.target_block_ids,
                    "proposed_content": proposal.proposed_content,
                    "reason": proposal.reason,
                }
                workflow.status = WorkflowStatus.WAITING_FOR_APPROVAL.value
                workflow.current_step = step.step_index
                workflow.updated_at = datetime.now(UTC)
                await session.flush()

                await self._audit.log_event(
                    session=session,
                    actor_user_id=actor.user_id,
                    action="approval.requested",
                    resource_type="ai_workflow",
                    resource_id=workflow.id,
                    organization_id=workflow.organization_id,
                    project_id=workflow.project_id,
                    metadata={
                        "step_id": str(step.id),
                        "proposal_id": str(proposal.id),
                        "tool_name": step.tool_name,
                    },
                )
                # Halt execution loop at approval gate
                return workflow

            # Step does not require approval -> Execute directly with bounded retry
            step.status = StepStatus.RUNNING.value
            step.started_at = datetime.now(UTC)
            await session.flush()

            step_input = dict(step.input or {})
            success = False
            last_err_msg = ""

            for attempt in range(DEFAULT_MAX_RETRIES):
                try:
                    tool_result = await self._executor.execute(
                        session,
                        tool_name=step.tool_name,
                        arguments=step_input,
                        actor=actor,
                        workflow_id=workflow.id,
                        step_id=step.id,
                        organization_id=workflow.organization_id,
                        project_id=workflow.project_id,
                        document_id=workflow.document_id,
                        retry_count=attempt,
                    )
                    step.status = StepStatus.COMPLETED.value
                    step.output = tool_result.result
                    step.completed_at = datetime.now(UTC)
                    accumulated_results[step.tool_name] = tool_result.result
                    success = True
                    break
                except ToolExecutionError as exc:
                    last_err_msg = str(exc)
                    should_retry = is_error_retryable("TOOL_EXECUTION_FAILED")
                    if not should_retry or attempt == DEFAULT_MAX_RETRIES - 1:
                        break
                except Exception as exc:
                    last_err_msg = str(exc)
                    break

            if not success:
                step.status = StepStatus.FAILED.value
                step.error = {"error": last_err_msg}
                step.completed_at = datetime.now(UTC)

                workflow.status = WorkflowStatus.FAILED.value
                workflow.error = {"failed_step": step.step_index, "error": last_err_msg}
                workflow.completed_at = datetime.now(UTC)
                workflow.updated_at = datetime.now(UTC)
                await session.flush()

                await self._audit.log_event(
                    session=session,
                    actor_user_id=actor.user_id,
                    action="workflow.failed",
                    resource_type="ai_workflow",
                    resource_id=workflow.id,
                    organization_id=workflow.organization_id,
                    project_id=workflow.project_id,
                    outcome="failed",
                    metadata={"step_id": str(step.id), "error": last_err_msg},
                )
                return workflow

            workflow.current_step = step.step_index + 1
            workflow.result = accumulated_results
            workflow.updated_at = datetime.now(UTC)
            await session.flush()

        # All steps completed successfully
        workflow.status = WorkflowStatus.COMPLETED.value
        workflow.completed_at = datetime.now(UTC)
        workflow.updated_at = datetime.now(UTC)
        await session.flush()

        await self._audit.log_event(
            session=session,
            actor_user_id=actor.user_id,
            action="workflow.completed",
            resource_type="ai_workflow",
            resource_id=workflow.id,
            organization_id=workflow.organization_id,
            project_id=workflow.project_id,
            outcome="success",
            metadata={"steps_completed": len(steps)},
        )

        return workflow

    async def approve_step(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
        step_id: UUID,
    ) -> AIWorkflow:
        """Approves a waiting step, applies the patch, verifies consistency,
        and resumes workflow.
        """
        workflow = await self._get_workflow_for_update(session, workflow_id)
        if workflow.status != WorkflowStatus.WAITING_FOR_APPROVAL.value:
            raise WorkflowStateError(workflow.status, "approve_step")

        step_stmt = select(AIWorkflowStep).where(AIWorkflowStep.id == step_id)
        step_res = await session.execute(step_stmt)
        step = step_res.scalars().first()
        if not step or step.workflow_id != workflow.id:
            raise ResourceNotFound(f"Step {step_id} not found in workflow {workflow_id}")

        if step.status != StepStatus.WAITING_FOR_APPROVAL.value:
            raise ConflictError("Step is not waiting for approval.")

        # Extract proposal ID
        proposal_id_str = (step.output or {}).get("proposal_id")
        if not proposal_id_str:
            raise BadRequestError("No proposal ID associated with step approval.")

        proposal_id = UUID(str(proposal_id_str))

        # 1. Fetch document pre-apply to track version
        doc_stmt = select(ContentDocument).where(ContentDocument.id == workflow.document_id)
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalars().first()
        expected_version = (doc.current_version if doc else 1) + 1

        # 2. Fetch proposal
        prop_stmt = select(AIEditProposal).where(AIEditProposal.id == proposal_id)
        prop_res = await session.execute(prop_stmt)
        proposal = prop_res.scalars().first()
        if not proposal:
            raise ResourceNotFound(f"Proposal {proposal_id} not found.")

        # 3. Apply proposal via DocumentPatchService
        await self._patches.apply_proposal(
            session,
            actor=actor,
            proposal_id=proposal_id,
        )

        # 4. Verify Patch Application
        await self._verifier.verify_patch_applied(
            session,
            document_id=workflow.document_id,
            proposal=proposal,
            expected_version=expected_version,
        )

        # 5. Mark Step Completed
        step.status = StepStatus.COMPLETED.value
        step.completed_at = datetime.now(UTC)
        workflow.current_step = step.step_index + 1
        await session.flush()

        await self._audit.log_event(
            session=session,
            actor_user_id=actor.user_id,
            action="approval.approved",
            resource_type="ai_workflow",
            resource_id=workflow.id,
            organization_id=workflow.organization_id,
            project_id=workflow.project_id,
            metadata={"step_id": str(step.id), "proposal_id": str(proposal.id)},
        )

        # 6. Resume workflow for remaining steps
        return await self.run_workflow(session, actor=actor, workflow_id=workflow.id)

    async def reject_step(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
        step_id: UUID,
    ) -> AIWorkflow:
        """Rejects a waiting step proposal and completes the workflow."""
        workflow = await self._get_workflow_for_update(session, workflow_id)
        if workflow.status != WorkflowStatus.WAITING_FOR_APPROVAL.value:
            raise WorkflowStateError(workflow.status, "reject_step")

        step_stmt = select(AIWorkflowStep).where(AIWorkflowStep.id == step_id)
        step_res = await session.execute(step_stmt)
        step = step_res.scalars().first()
        if not step or step.workflow_id != workflow.id:
            raise ResourceNotFound(f"Step {step_id} not found in workflow {workflow_id}")

        proposal_id_str = (step.output or {}).get("proposal_id")
        if proposal_id_str:
            await self._patches.reject_proposal(
                session,
                actor=actor,
                proposal_id=UUID(str(proposal_id_str)),
            )

        step.status = StepStatus.SKIPPED.value
        step.completed_at = datetime.now(UTC)

        workflow.status = WorkflowStatus.COMPLETED.value
        workflow.completed_at = datetime.now(UTC)
        workflow.updated_at = datetime.now(UTC)
        await session.flush()

        await self._audit.log_event(
            session=session,
            actor_user_id=actor.user_id,
            action="approval.rejected",
            resource_type="ai_workflow",
            resource_id=workflow.id,
            organization_id=workflow.organization_id,
            project_id=workflow.project_id,
            metadata={"step_id": str(step.id)},
        )

        return workflow

    async def cancel_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
        reason: str = "User cancelled",
    ) -> AIWorkflow:
        """Cancels a workflow in progress or waiting for approval."""
        workflow = await self._get_workflow_for_update(session, workflow_id)

        if workflow.status in (
            WorkflowStatus.COMPLETED.value,
            WorkflowStatus.CANCELLED.value,
        ):
            return workflow

        workflow.status = WorkflowStatus.CANCELLED.value
        workflow.error = {"cancellation_reason": reason}
        workflow.completed_at = datetime.now(UTC)
        workflow.updated_at = datetime.now(UTC)

        # Mark all pending or waiting steps as SKIPPED
        step_stmt = select(AIWorkflowStep).where(
            AIWorkflowStep.workflow_id == workflow.id,
            AIWorkflowStep.status.in_(
                [
                    StepStatus.PENDING.value,
                    StepStatus.WAITING_FOR_APPROVAL.value,
                ]
            ),
        )
        step_res = await session.execute(step_stmt)
        for s in step_res.scalars().all():
            s.status = StepStatus.SKIPPED.value
            s.completed_at = datetime.now(UTC)

        await session.flush()

        await self._audit.log_event(
            session=session,
            actor_user_id=actor.user_id,
            action="workflow.cancelled",
            resource_type="ai_workflow",
            resource_id=workflow.id,
            organization_id=workflow.organization_id,
            project_id=workflow.project_id,
            metadata={"reason": reason},
        )

        return workflow

    async def resume_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
    ) -> AIWorkflow:
        """Resumes a paused or recoverable workflow from the last incomplete step."""
        workflow = await self._get_workflow_for_update(session, workflow_id)

        if workflow.status not in (
            WorkflowStatus.RUNNING.value,
            WorkflowStatus.PENDING.value,
            WorkflowStatus.FAILED.value,
        ):
            raise WorkflowStateError(workflow.status, "resume_workflow")

        return await self.run_workflow(session, actor=actor, workflow_id=workflow.id)

    async def get_workflow_detail(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
    ) -> WorkflowDetail:
        """Retrieves full workflow detail with all step records and permission checks."""
        stmt = select(AIWorkflow).where(AIWorkflow.id == workflow_id)
        res = await session.execute(stmt)
        wf = res.scalars().first()
        if not wf:
            raise ResourceNotFound(f"Workflow {workflow_id} not found.")

        await self._projects.get_model(
            session,
            actor=actor,
            project_id=wf.project_id,
            permission=PermissionCode.AI_USE,
        )

        step_stmt = (
            select(AIWorkflowStep)
            .where(AIWorkflowStep.workflow_id == wf.id)
            .order_by(AIWorkflowStep.step_index.asc())
        )
        step_res = await session.execute(step_stmt)
        steps = [WorkflowStepDetail.model_validate(s) for s in step_res.scalars().all()]

        # Check for pending proposal
        pending_proposal_id = None
        for s in steps:
            if s.status == StepStatus.WAITING_FOR_APPROVAL and s.output.get("proposal_id"):
                pending_proposal_id = UUID(str(s.output["proposal_id"]))
                break

        return WorkflowDetail(
            id=wf.id,
            organization_id=wf.organization_id,
            project_id=wf.project_id,
            document_id=wf.document_id,
            created_by_id=wf.created_by_id,
            intent=wf.intent,
            status=WorkflowStatus(wf.status),
            current_step=wf.current_step,
            plan=wf.plan if isinstance(wf.plan, list) else [],
            result=wf.result or {},
            error=wf.error,
            token_usage=wf.token_usage or {},
            steps=steps,
            pending_proposal_id=pending_proposal_id,
            started_at=wf.started_at,
            completed_at=wf.completed_at,
            created_at=wf.created_at,
            updated_at=wf.updated_at,
        )

    async def _get_workflow_for_update(
        self,
        session: AsyncSession,
        workflow_id: UUID,
    ) -> AIWorkflow:
        stmt = select(AIWorkflow).where(AIWorkflow.id == workflow_id).with_for_update()
        res = await session.execute(stmt)
        workflow = res.scalars().first()
        if not workflow:
            raise ResourceNotFound(f"Workflow {workflow_id} not found.")
        return workflow

    async def _create_proposal_for_step(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow: AIWorkflow,
        step: AIWorkflowStep,
    ) -> AIEditProposal:
        """Creates an AIEditProposal record representing proposed write changes."""
        doc_stmt = select(ContentDocument).where(ContentDocument.id == workflow.document_id)
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalars().first()
        if not doc:
            raise ResourceNotFound(f"Document {workflow.document_id} not found.")

        step_input = step.input or {}
        target_block = str(step_input.get("block_id") or "block_001")
        blocks = doc.content_blocks or []
        current_block = next((b for b in blocks if b.get("id") == target_block), None)
        old_text = str(current_block.get("text", "") if current_block else "")

        if step.tool_name == "insert_internal_link":
            op_type = "insert_link"
            url = str(step_input.get("url", "/technical-seo-guide"))
            anchor = str(step_input.get("anchor_text", "technical SEO guide"))
            proposed_content = {"url": url, "anchor_text": anchor}
            reason = str(step_input.get("reason", "Connect topical cluster link"))
            diff_summary = {"url": url, "anchor": anchor}
        elif step.tool_name == "expand_section":
            op_type = "replace_block"
            new_text = (
                f"{old_text} Specifically, establishing governed verification ensures "
                "production readiness and reliable search indexing."
            )
            proposed_content = {"text": new_text}
            reason = "Expanded section with supporting technical architecture details."
            diff_summary = {"old": old_text, "new": new_text}
        elif step.tool_name == "shorten_section":
            op_type = "replace_block"
            new_text = f"{old_text[:120]}..." if len(old_text) > 120 else old_text
            proposed_content = {"text": new_text}
            reason = "Tightened phrasing and eliminated filler words."
            diff_summary = {"old": old_text, "new": new_text}
        else:
            # Default rewrite_section
            op_type = "replace_block"
            new_text = f"Optimized: {old_text}" if old_text else "Refined section content."
            proposed_content = {"text": new_text}
            reason = "Polished phrasing according to active brand guidelines and SEO rules."
            diff_summary = {"old": old_text, "new": new_text}

        proposal = AIEditProposal(
            document_id=workflow.document_id,
            chat_message_id=None,
            status=ProposalStatus.PROPOSED.value,
            operation_type=op_type,
            target_block_ids=[target_block],
            old_content={"text": old_text},
            proposed_content=proposed_content,
            diff_summary=diff_summary,
            reason=reason,
            ai_provider="orchestrator",
            model="orchestrator-planner-v1",
            created_at=datetime.now(UTC),
        )
        session.add(proposal)
        await session.flush()
        return proposal
