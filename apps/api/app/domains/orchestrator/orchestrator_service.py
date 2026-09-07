"""Application Service facade for the AI Orchestrator domain."""

from uuid import UUID

from app.core.errors import ResourceNotFound
from app.db.session import set_actor_context
from app.domains.content.editor_models import ContentDocument
from app.domains.orchestrator.intent_classifier import IntentClassifier
from app.domains.orchestrator.planner import WorkflowPlanner
from app.domains.orchestrator.schemas import (
    OrchestratorRequest,
    ToolDescriptorDTO,
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
    ) -> None:
        self._registry = registry or ToolRegistry()
        self._classifier = classifier or IntentClassifier()
        self._planner = planner or WorkflowPlanner(registry=self._registry)
        self._workflows = workflow_service or WorkflowService(tool_registry=self._registry)
        self._projects = ProjectService()

    async def initiate_workflow(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        request: OrchestratorRequest,
    ) -> WorkflowDetail:
        """Entrypoint for creating, planning, and executing an AI workflow."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            # 1. Fetch document and validate ownership
            doc_stmt = select(ContentDocument).where(ContentDocument.id == request.document_id)
            doc_res = await session.execute(doc_stmt)
            doc = doc_res.scalars().first()
            if not doc:
                raise ResourceNotFound(f"Document {request.document_id} was not found.")

            # 2. Permission check
            await self._projects.get_model(
                session,
                actor=actor,
                project_id=doc.project_id,
                permission=PermissionCode.AI_USE,
            )

            # 3. Intent Detection
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

            # 4. Workflow Planning
            plan_steps = self._planner.create_plan(
                intent_result=intent_res,
                user_message=request.message,
                document_id=doc.id,
                selected_block_ids=request.selected_block_ids,
            )

            # 5. Create Workflow Record
            workflow = await self._workflows.create_workflow(
                session,
                actor=actor,
                organization_id=doc.organization_id,
                project_id=doc.project_id,
                document_id=doc.id,
                intent=intent_res.intent,
                plan_steps=plan_steps,
            )

            # 6. Execute Workflow until completion or approval gate
            await self._workflows.run_workflow(session, actor=actor, workflow_id=workflow.id)

            # 7. Return detailed response
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
        async with session.begin():
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
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            await self._workflows.approve_step(
                session, actor=actor, workflow_id=workflow_id, step_id=step_id
            )
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
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            await self._workflows.reject_step(
                session, actor=actor, workflow_id=workflow_id, step_id=step_id
            )
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
        async with session.begin():
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
        async with session.begin():
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
        async with session.begin():
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
                risk_level=t.risk_level,
                required_permission=t.required_permission.value,
                enabled=t.enabled,
            )
            for t in tools
        ]
