"""Application Service facade for the AI Orchestrator domain."""

from uuid import UUID

from app.ai.provider import AIProvider
from app.core.errors import ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.content.editor_models import ContentDocument
from app.domains.orchestrator.intent_classifier import IntentClassifier
from app.domains.orchestrator.planner import WorkflowPlanner
from app.domains.orchestrator.schemas import (
    OrchestratorRequest,
    ToolCostDTO,
    ToolDescriptorDTO,
    ToolRateLimitsDTO,
    WorkflowDetail,
    WorkflowStepDetail,
)
from app.domains.orchestrator.tool_registry import ToolRegistry
from app.domains.orchestrator.workflow_service import WorkflowService
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class OrchestratorService:
    def __init__(
        self,
        classifier: IntentClassifier | None = None,
        planner: WorkflowPlanner | None = None,
        workflow_service: WorkflowService | None = None,
        registry: ToolRegistry | None = None,
        ai_provider: AIProvider | None = None,
    ) -> None:
        self._registry = registry or ToolRegistry()
        self._classifier = classifier or IntentClassifier()
        self._planner = planner or WorkflowPlanner(registry=self._registry)
        self._workflows = workflow_service or WorkflowService(
            tool_registry=self._registry,
            ai_provider=ai_provider,
        )
        self._projects = ProjectService()

    async def initiate_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        request: OrchestratorRequest,
    ) -> WorkflowDetail:
        """Entrypoint for creating, planning, and executing an AI workflow."""
        # 1. Initialize workflow record within its own short transaction
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)

            # Fetch document and validate ownership
            doc_stmt = select(ContentDocument).where(ContentDocument.id == request.document_id)
            doc_res = await session.execute(doc_stmt)
            doc = doc_res.scalars().first()
            if not doc:
                raise ResourceNotFound(f"Document {request.document_id} was not found.")

            # Permission check
            await self._projects.get_model(
                session,
                actor=actor,
                project_id=doc.project_id,
                permission=PermissionCode.AI_USE,
            )

            # Intent Detection
            if request.intent:
                intent_res = self._classifier.classify(
                    message=request.message,
                    document_id=doc.id,
                    selected_block_ids=request.selected_block_ids,
                )
                intent_res.intent = request.intent
            else:
                intent_res = self._classifier.classify(
                    message=request.message,
                    document_id=doc.id,
                    selected_block_ids=request.selected_block_ids,
                )

            # Workflow Planning (Advisory Initial Guidance)
            plan_steps = self._planner.create_plan(
                intent_result=intent_res,
                user_message=request.message,
                document_id=doc.id,
                selected_block_ids=request.selected_block_ids,
            )

            # Create Workflow Record
            workflow = await self._workflows.create_workflow(
                session,
                actor=actor,
                organization_id=doc.organization_id,
                project_id=doc.project_id,
                document_id=doc.id,
                intent=intent_res.intent,
                plan_steps=plan_steps,
                user_message=request.message,
                selected_block_ids=request.selected_block_ids,
            )

        # 2. Execute Workflow via Content Agent Loop (outside the creation transaction)
        await self._workflows.run_workflow(
            session,
            actor=actor,
            workflow_id=workflow.id,
            user_message=request.message,
            selected_block_ids=request.selected_block_ids,
        )

        # 3. Return detailed response
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            return await self._workflows.get_workflow_detail(
                session, actor=actor, workflow_id=workflow.id
            )

    async def get_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
    ) -> WorkflowDetail:
        """Retrieves workflow status and results."""
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            return await self._workflows.get_workflow_detail(
                session, actor=actor, workflow_id=workflow_id
            )

    async def approve_step(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
        step_id: UUID,
    ) -> WorkflowDetail:
        """Human approval for a proposed write action."""
        await self._workflows.approve_step(
            session, actor=actor, workflow_id=workflow_id, step_id=step_id
        )
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            return await self._workflows.get_workflow_detail(
                session, actor=actor, workflow_id=workflow_id
            )

    async def reject_step(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
        step_id: UUID,
    ) -> WorkflowDetail:
        """Human rejection of a proposed write action."""
        await self._workflows.reject_step(
            session, actor=actor, workflow_id=workflow_id, step_id=step_id
        )
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            return await self._workflows.get_workflow_detail(
                session, actor=actor, workflow_id=workflow_id
            )

    async def cancel_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
        reason: str = "User cancelled",
    ) -> WorkflowDetail:
        """Cancels a workflow."""
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            await self._workflows.cancel_workflow(
                session, actor=actor, workflow_id=workflow_id, reason=reason
            )
            return await self._workflows.get_workflow_detail(
                session, actor=actor, workflow_id=workflow_id
            )

    async def resume_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
    ) -> WorkflowDetail:
        """Resumes a paused workflow."""
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            await self._workflows.resume_workflow(session, actor=actor, workflow_id=workflow_id)
            return await self._workflows.get_workflow_detail(
                session, actor=actor, workflow_id=workflow_id
            )

    async def list_workflow_steps(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        workflow_id: UUID,
    ) -> list[WorkflowStepDetail]:
        """Lists steps for a workflow."""
        async with transactional_session(session):
            await set_actor_context(session, actor.user_id)
            detail = await self._workflows.get_workflow_detail(
                session, actor=actor, workflow_id=workflow_id
            )
            return detail.steps

    def list_tools(self) -> list[ToolDescriptorDTO]:
        """Lists registered tools and risk descriptors."""
        tools = self._registry.list_tools()
        return [
            ToolDescriptorDTO(
                name=t.name,
                description=t.description,
                input_schema=t.input_schema.model_json_schema(),
                output_schema=t.output_schema.model_json_schema(),
                authentication_requirements=[item.value for item in t.authentication_requirements],
                permissions=[permission.value for permission in t.permissions],
                cost=ToolCostDTO(
                    estimated_usd_per_call=t.cost.estimated_usd_per_call,
                    billing_unit=t.cost.billing_unit,
                ),
                rate_limits=ToolRateLimitsDTO(
                    max_calls_per_workflow=t.rate_limits.max_calls_per_workflow,
                    max_concurrent_calls=t.rate_limits.max_concurrent_calls,
                ),
                availability=t.availability,
                version=t.version,
                risk_level=t.risk_level,
                required_permission=t.required_permission.value,
                enabled=t.enabled and t.availability.value == "AVAILABLE",
            )
            for t in tools
        ]
