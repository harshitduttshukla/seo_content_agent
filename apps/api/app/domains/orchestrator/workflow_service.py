"""Workflow Service managing the state machine, execution loop, approval gates,

retries, idempotency, and audit logging.
"""

import contextlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.ai.provider import AIProvider
from app.core.errors import BadRequestError, ConflictError, PermissionDenied, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.ai.context_builder import ContentAgentContextBuilder
from app.domains.audit.repository import AuditWriter
from app.domains.content.editor_models import (
    AIEditProposal,
    ContentDocument,
    ProposalStatus,
)
from app.domains.content.patch_service import DocumentPatchService
from app.domains.orchestrator.agent_loop import AgentLoop
from app.domains.orchestrator.exceptions import (
    WorkflowStateError,
)
from app.domains.orchestrator.models import (
    AIWorkflow,
    AIWorkflowStep,
    StepStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.schemas import (
    ToolObservation,
    WorkflowDetail,
    WorkflowPlanStep,
    WorkflowStepDetail,
)
from app.domains.orchestrator.tool_executor import ToolExecutor
from app.domains.orchestrator.tool_registry import ToolRegistry
from app.domains.orchestrator.verification_service import VerificationService
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser, PermissionCode
from pydantic_core import to_jsonable_python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class WorkflowService:
    def __init__(
        self,
        tool_executor: ToolExecutor | None = None,
        tool_registry: ToolRegistry | None = None,
        patch_service: DocumentPatchService | None = None,
        verification_service: VerificationService | None = None,
        ai_provider: AIProvider | None = None,
        context_builder: ContentAgentContextBuilder | None = None,
        agent_loop: AgentLoop | None = None,
    ) -> None:
        self._registry = tool_registry or ToolRegistry()
        self._executor = tool_executor or ToolExecutor(registry=self._registry)
        self._patches = patch_service or DocumentPatchService()
        self._verifier = verification_service or VerificationService()
        self._audit = AuditWriter()
        self._projects = ProjectService()
        self._loop = agent_loop or AgentLoop(
            provider=ai_provider,
            registry=self._registry,
            executor=self._executor,
            context_builder=context_builder,
            verifier=self._verifier,
            audit=self._audit,
        )

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
        user_message: str = "",
        selected_block_ids: list[str] | None = None,
    ) -> AIWorkflow:
        """Initializes a workflow record and its associated ordered steps."""
        async with transactional_session(session):
            # Validate project permissions
            await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.AI_USE,
            )

            initial_result: dict[str, object] = {}
            if user_message:
                initial_result["user_message"] = user_message
            if selected_block_ids:
                initial_result["selected_block_ids"] = selected_block_ids

            wf_id = uuid4()
            workflow = AIWorkflow(
                id=wf_id,
                organization_id=organization_id,
                project_id=project_id,
                document_id=document_id,
                created_by_id=actor.user_id,
                intent=intent.value,
                status=WorkflowStatus.PENDING.value,
                current_step=0,
                plan=[to_jsonable_python(s.model_dump(mode="json")) for s in plan_steps],
                result=initial_result,
                token_usage={"total_tokens": 0},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(workflow)
            await session.flush()

            for s in plan_steps:
                step_record = AIWorkflowStep(
                    id=uuid4(),
                    workflow_id=wf_id,
                    step_index=s.step_index,
                    step_type="tool_call",
                    tool_name=s.tool_name,
                    status=StepStatus.PENDING.value,
                    input=to_jsonable_python(s.input_arguments),
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
        user_message: str | None = None,
        selected_block_ids: list[str] | None = None,
    ) -> AIWorkflow:
        """Runs the bounded orchestration loop until completion or an approval gate."""
        workflow = await self._get_workflow_for_update(session, workflow_id)

        if workflow.status in (
            WorkflowStatus.COMPLETED.value,
            WorkflowStatus.CANCELLED.value,
        ):
            return workflow

        # Retrieve stored message and context metadata
        stored_result = workflow.result if isinstance(workflow.result, dict) else {}
        msg = user_message or str(
            stored_result.get("user_message") or f"Execute task for intent: {workflow.intent}"
        )
        blocks = selected_block_ids or stored_result.get("selected_block_ids") or []

        # Parse initial advisory plan
        initial_plan: list[WorkflowPlanStep] = []
        if isinstance(workflow.plan, list):
            for step_data in workflow.plan:
                if isinstance(step_data, dict):
                    with contextlib.suppress(Exception):
                        initial_plan.append(WorkflowPlanStep.model_validate(step_data))

        # Collect existing observations from previously completed steps
        step_stmt = (
            select(AIWorkflowStep)
            .where(AIWorkflowStep.workflow_id == workflow.id)
            .order_by(AIWorkflowStep.step_index.asc())
        )
        step_res = await session.execute(step_stmt)
        completed_steps = [
            s for s in step_res.scalars().all() if s.status == StepStatus.COMPLETED.value
        ]
        existing_observations: list[ToolObservation] = []
        for s in completed_steps:
            existing_observations.append(
                ToolObservation(
                    execution_id=str(s.id),
                    tool_name=s.tool_name,
                    status="SUCCESS",
                    input_summary=s.input if isinstance(s.input, dict) else {},
                    output=s.output if isinstance(s.output, dict) else {},
                    iteration=s.step_index,
                )
            )

        # Delegate execution to Content AgentLoop
        await self._loop.run(
            session,
            actor=actor,
            workflow=workflow,
            user_message=msg,
            selected_block_ids=blocks if isinstance(blocks, list) else [],
            initial_plan=initial_plan,
            existing_observations=existing_observations,
        )

        # Refresh and return updated workflow
        return await self._get_workflow_for_update(session, workflow_id)

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
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            workflow = await self._authorize_workflow(
                session,
                actor=actor,
                workflow_id=workflow_id,
                permission=PermissionCode.CONTENT_WRITE,
                for_update=True,
            )

            step_stmt = (
                select(AIWorkflowStep)
                .where(
                    AIWorkflowStep.id == step_id,
                    AIWorkflowStep.workflow_id == workflow.id,
                )
                .with_for_update()
            )
            step_res = await session.execute(step_stmt)
            step = step_res.scalars().first()
            if not step:
                raise ResourceNotFound("workflow step")

            # Extract proposal ID
            proposal_id_str = (step.output or {}).get("proposal_id")
            if not proposal_id_str:
                raise BadRequestError("No proposal ID associated with step approval.")

            proposal_id = UUID(str(proposal_id_str))

            # 1. Fetch proposal with row lock
            prop_stmt = (
                select(AIEditProposal).where(AIEditProposal.id == proposal_id).with_for_update()
            )
            prop_res = await session.execute(prop_stmt)
            proposal = prop_res.scalars().first()
            if not proposal:
                raise ResourceNotFound(f"Proposal {proposal_id} not found.")

            # Idempotency check (P2-4): if step was already approved and proposal applied
            if (
                step.status == StepStatus.COMPLETED.value
                and proposal.status == ProposalStatus.APPLIED.value
            ):
                already_approved = True
            else:
                already_approved = False
                if workflow.status != WorkflowStatus.WAITING_FOR_APPROVAL.value:
                    raise WorkflowStateError(workflow.status, "approve_step")

                if step.status != StepStatus.WAITING_FOR_APPROVAL.value:
                    raise ConflictError("Step is not waiting for approval.")

            if not already_approved:
                # 2. Fetch document pre-apply to track version
                doc_stmt = (
                    select(ContentDocument)
                    .where(ContentDocument.id == workflow.document_id)
                    .with_for_update()
                )
                doc_res = await session.execute(doc_stmt)
                doc = doc_res.scalars().first()
                if not doc:
                    raise ResourceNotFound("Content document not found")

                # Handle out-of-band applied proposal (P1-3) vs normal apply
                if proposal.status == ProposalStatus.APPLIED.value:
                    expected_version = proposal.applied_version or doc.current_version
                else:
                    expected_version = doc.current_version + 1
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

                # 5. Mark Step Completed and set workflow to RUNNING before commit (P0-1)
                step.status = StepStatus.COMPLETED.value
                step.completed_at = datetime.now(UTC)
                workflow.current_step = step.step_index + 1
                workflow.status = WorkflowStatus.RUNNING.value
                workflow.updated_at = datetime.now(UTC)
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

        # 6. Resume workflow for remaining steps (committed approval persists independently)
        return await self.run_workflow(session, actor=actor, workflow_id=workflow_id)

    async def reject_step(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
        step_id: UUID,
    ) -> AIWorkflow:
        """Rejects a waiting step proposal and completes the workflow."""
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            workflow = await self._authorize_workflow(
                session,
                actor=actor,
                workflow_id=workflow_id,
                permission=PermissionCode.CONTENT_WRITE,
                for_update=True,
            )
            if workflow.status != WorkflowStatus.WAITING_FOR_APPROVAL.value:
                raise WorkflowStateError(workflow.status, "reject_step")

            step_stmt = (
                select(AIWorkflowStep)
                .where(
                    AIWorkflowStep.id == step_id,
                    AIWorkflowStep.workflow_id == workflow.id,
                )
                .with_for_update()
            )
            step_res = await session.execute(step_stmt)
            step = step_res.scalars().first()
            if not step:
                raise ResourceNotFound("workflow step")

            if step.status != StepStatus.WAITING_FOR_APPROVAL.value:
                raise ConflictError("Step is not waiting for approval.")

            proposal_id_str = (step.output or {}).get("proposal_id")
            if proposal_id_str:
                proposal_id = UUID(str(proposal_id_str))
                prop_stmt = (
                    select(AIEditProposal).where(AIEditProposal.id == proposal_id).with_for_update()
                )
                prop_res = await session.execute(prop_stmt)
                proposal = prop_res.scalars().first()
                if proposal:
                    if proposal.status == ProposalStatus.APPLIED.value:
                        raise ConflictError("Cannot reject proposal that has already been applied.")
                    if (
                        proposal.status != ProposalStatus.PROPOSED.value
                        and proposal.status != ProposalStatus.REJECTED.value
                    ):
                        raise ConflictError(
                            f"Cannot reject proposal in status '{proposal.status}'."
                        )

                await self._patches.reject_proposal(
                    session,
                    actor=actor,
                    proposal_id=proposal_id,
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
        """Cancels a workflow in progress or waiting for approval.

        Authorization is enforced BEFORE any state mutation to prevent
        cross-tenant cancellation (P0-2).
        """
        async with transactional_session(session):
            # Authorize BEFORE lock/mutation — prevents cross-tenant cancel
            workflow = await self._authorize_workflow(
                session,
                actor=actor,
                workflow_id=workflow_id,
                permission=PermissionCode.AI_USE,
                for_update=True,
            )

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
        """Resumes a paused or recoverable workflow from the last incomplete step.

        Authorization is enforced BEFORE any state validation or mutation
        to prevent cross-tenant resume (P0-1). An unauthorized actor causes
        no durable change to the workflow.
        """
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            # Authorize BEFORE state check — prevents cross-tenant resume
            workflow = await self._authorize_workflow(
                session,
                actor=actor,
                workflow_id=workflow_id,
                permission=PermissionCode.AI_USE,
                for_update=True,
            )
            if workflow.status == WorkflowStatus.WAITING_FOR_APPROVAL.value:
                # Check if there are active steps actually waiting for approval
                waiting_steps_stmt = select(AIWorkflowStep).where(
                    AIWorkflowStep.workflow_id == workflow.id,
                    AIWorkflowStep.status == StepStatus.WAITING_FOR_APPROVAL.value,
                )
                waiting_res = await session.execute(waiting_steps_stmt)
                if waiting_res.scalars().first():
                    raise WorkflowStateError(workflow.status, "resume_workflow")
                # Post-approval crash recovery: step was approved/completed; advance to RUNNING
                workflow.status = WorkflowStatus.RUNNING.value
                workflow.updated_at = datetime.now(UTC)
                await session.flush()
            elif workflow.status not in (
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
        """Retrieves full workflow detail with all step records and permission checks.

        Uses _authorize_workflow to prevent information leakage — unauthorized
        and nonexistent workflows produce the same ResourceNotFound.
        """
        wf = await self._authorize_workflow(
            session,
            actor=actor,
            workflow_id=workflow_id,
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

        plan = (
            [item for item in wf.plan if isinstance(item, dict)]
            if isinstance(wf.plan, list)
            else []
        )
        return WorkflowDetail(
            id=wf.id,
            organization_id=wf.organization_id,
            project_id=wf.project_id,
            document_id=wf.document_id,
            created_by_id=wf.created_by_id,
            intent=wf.intent,
            status=WorkflowStatus(wf.status),
            current_step=wf.current_step,
            plan=plan,
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _authorize_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
        permission: PermissionCode,
        for_update: bool = False,
    ) -> AIWorkflow:
        """Load a workflow and verify the actor has *permission* on its project.

        Authorization happens BEFORE any mutation. Both nonexistent and
        unauthorized workflows raise the same ``ResourceNotFound('workflow')``
        to prevent cross-tenant resource existence leakage.
        """
        stmt = select(AIWorkflow).where(AIWorkflow.id == workflow_id)
        if for_update and session.in_transaction():
            stmt = stmt.with_for_update()
        res = await session.execute(stmt)
        workflow = res.scalars().first()
        if not workflow:
            raise ResourceNotFound("workflow")

        # Verify actor has the required permission on the workflow's project.
        # get_model raises ResourceNotFound("project") on missing membership —
        # we catch and re-raise as ResourceNotFound("workflow") to avoid leaking
        # that the workflow exists but belongs to another tenant.
        try:
            await self._projects.get_model(
                session,
                actor=actor,
                project_id=workflow.project_id,
                permission=permission,
            )
        except (ResourceNotFound, PermissionDenied):
            raise ResourceNotFound("workflow") from None

        return workflow

    async def _get_workflow_for_update(
        self,
        session: AsyncSession,
        workflow_id: UUID,
    ) -> AIWorkflow:
        """Load workflow with FOR UPDATE lock.  No authorization — use
        ``_authorize_workflow`` for operations exposed to external callers.
        """
        stmt = select(AIWorkflow).where(AIWorkflow.id == workflow_id)
        if session.in_transaction():
            stmt = stmt.with_for_update()
        res = await session.execute(stmt)
        workflow = res.scalars().first()
        if not workflow:
            raise ResourceNotFound("workflow")
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
            id=uuid4(),
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
            base_version=doc.current_version if doc else 1,
            created_at=datetime.now(UTC),
        )
        session.add(proposal)
        await session.flush()
        return proposal
