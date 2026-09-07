"""Unified execution engine for governed AI tools.

Enforces:
1. Tool existence & enabled status
2. RBAC permission verification
3. Tenant & project isolation
4. Input schema validation
5. Monitored execution & retry policies
6. Output schema validation
7. Database execution record persistence (`tool_executions`)
8. Audit event recording
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.errors import PermissionDenied, ResourceNotFound
from app.domains.audit.repository import AuditWriter
from app.domains.content.editor_models import ContentDocument
from app.domains.orchestrator.exceptions import (
    ToolExecutionError,
    ToolNotFoundError,
    ToolPermissionDeniedError,
)
from app.domains.orchestrator.models import ToolExecutionRecord, ToolExecutionStatus
from app.domains.orchestrator.schemas import ToolExecutionResult
from app.domains.orchestrator.tool_registry import ToolExecutionContext, ToolRegistry
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._registry = registry or ToolRegistry()
        self._projects = ProjectService()
        self._audit = AuditWriter()
        self._timeout_seconds = timeout_seconds

    async def execute(
        self,
        session: AsyncSession,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        actor: AuthenticatedUser,
        workflow_id: UUID,
        step_id: UUID,
        organization_id: UUID,
        project_id: UUID,
        document_id: UUID,
        retry_count: int = 0,
    ) -> ToolExecutionResult:
        """Executes a registered tool following the strict governed pipeline."""
        started_at = datetime.now(UTC)

        # 1. Registry Lookup
        try:
            tool = self._registry.get(tool_name)
        except ToolNotFoundError:
            # Unknown or disabled tool
            await self._record_execution(
                session,
                workflow_id=workflow_id,
                step_id=step_id,
                tool_name=tool_name,
                status=ToolExecutionStatus.REJECTED,
                input_data=arguments,
                output_data={},
                error_data={"error": f"Tool '{tool_name}' does not exist or is disabled."},
                retry_count=retry_count,
                started_at=started_at,
            )
            raise

        # 2. Permission Check via ProjectService / RBAC
        try:
            await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=tool.required_permission,
            )
        except (PermissionDenied, ResourceNotFound) as exc:
            await self._record_execution(
                session,
                workflow_id=workflow_id,
                step_id=step_id,
                tool_name=tool_name,
                status=ToolExecutionStatus.REJECTED,
                input_data=arguments,
                output_data={},
                error_data={
                    "error": f"Permission denied for tool '{tool_name}'.",
                    "required_permission": tool.required_permission.value,
                },
                retry_count=retry_count,
                started_at=started_at,
            )
            raise ToolPermissionDeniedError(
                tool_name=tool_name,
                required_permission=tool.required_permission.value,
            ) from exc

        # 3. Tenant & Document Validation
        doc_stmt = select(ContentDocument).where(ContentDocument.id == document_id)
        doc_res = await session.execute(doc_stmt)
        document = doc_res.scalars().first()
        if (
            not document
            or document.project_id != project_id
            or document.organization_id != organization_id
        ):
            err_msg = (
                f"Document {document_id} does not belong to project {project_id} "
                f"or tenant {organization_id}."
            )
            await self._record_execution(
                session,
                workflow_id=workflow_id,
                step_id=step_id,
                tool_name=tool_name,
                status=ToolExecutionStatus.REJECTED,
                input_data=arguments,
                output_data={},
                error_data={"error": err_msg},
                retry_count=retry_count,
                started_at=started_at,
            )
            raise ResourceNotFound(err_msg)

        # 4. Input Schema Validation
        try:
            # Auto-inject document_id and project_id if missing from arguments
            clean_args = dict(arguments)
            if "document_id" not in clean_args:
                clean_args["document_id"] = document_id
            if "project_id" not in clean_args:
                clean_args["project_id"] = project_id

            validated_input = tool.input_schema.model_validate(clean_args)
            input_dict = validated_input.model_dump()
        except ValidationError as exc:
            await self._record_execution(
                session,
                workflow_id=workflow_id,
                step_id=step_id,
                tool_name=tool_name,
                status=ToolExecutionStatus.REJECTED,
                input_data=arguments,
                output_data={},
                error_data={"error": "Input validation failed", "details": exc.errors()},
                retry_count=retry_count,
                started_at=started_at,
            )
            raise ToolExecutionError(
                tool_name=tool_name,
                reason=f"Input validation error: {exc.errors()}",
            ) from exc

        # 5. Execute Handler with Timeout
        context = ToolExecutionContext(
            session=session,
            actor=actor,
            workflow_id=workflow_id,
            step_id=step_id,
            organization_id=organization_id,
            project_id=project_id,
            document_id=document_id,
        )

        try:
            raw_output = await asyncio.wait_for(
                tool.handler(context, input_dict),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            await self._record_execution(
                session,
                workflow_id=workflow_id,
                step_id=step_id,
                tool_name=tool_name,
                status=ToolExecutionStatus.TIMEOUT,
                input_data=input_dict,
                output_data={},
                error_data={"error": f"Tool execution timed out after {self._timeout_seconds}s"},
                retry_count=retry_count,
                started_at=started_at,
            )
            raise ToolExecutionError(
                tool_name=tool_name,
                reason=f"Timed out after {self._timeout_seconds}s",
            ) from exc
        except Exception as exc:
            await self._record_execution(
                session,
                workflow_id=workflow_id,
                step_id=step_id,
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                input_data=input_dict,
                output_data={},
                error_data={"error": str(exc)},
                retry_count=retry_count,
                started_at=started_at,
            )
            raise ToolExecutionError(
                tool_name=tool_name,
                reason=str(exc),
            ) from exc

        # 6. Output Schema Validation
        try:
            validated_output = tool.output_schema.model_validate(raw_output)
            output_dict = validated_output.model_dump()
        except ValidationError as exc:
            await self._record_execution(
                session,
                workflow_id=workflow_id,
                step_id=step_id,
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                input_data=input_dict,
                output_data=raw_output,
                error_data={"error": "Output schema validation failed", "details": exc.errors()},
                retry_count=retry_count,
                started_at=started_at,
            )
            raise ToolExecutionError(
                tool_name=tool_name,
                reason=f"Output validation failed: {exc.errors()}",
            ) from exc

        # 7. Record Tool Execution
        await self._record_execution(
            session,
            workflow_id=workflow_id,
            step_id=step_id,
            tool_name=tool_name,
            status=ToolExecutionStatus.SUCCESS,
            input_data=input_dict,
            output_data=output_dict,
            error_data=None,
            retry_count=retry_count,
            started_at=started_at,
        )

        # 8. Record Audit Log
        await self._audit.log_event(
            session=session,
            actor_user_id=actor.user_id,
            action="tool.executed",
            resource_type="tool_execution",
            resource_id=workflow_id,
            organization_id=organization_id,
            project_id=project_id,
            outcome="success",
            metadata={
                "tool_name": tool_name,
                "step_id": str(step_id),
                "risk_level": tool.risk_level.value,
            },
        )

        return ToolExecutionResult(
            tool_name=tool_name,
            status=ToolExecutionStatus.SUCCESS,
            result=output_dict,
            metadata={
                "workflow_id": str(workflow_id),
                "step_id": str(step_id),
                "risk_level": tool.risk_level.value,
                "duration_ms": int((datetime.now(UTC) - started_at).total_seconds() * 1000),
            },
        )

    async def _record_execution(
        self,
        session: AsyncSession,
        *,
        workflow_id: UUID,
        step_id: UUID,
        tool_name: str,
        status: ToolExecutionStatus,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        error_data: dict[str, Any] | None,
        retry_count: int,
        started_at: datetime,
    ) -> None:
        rec = ToolExecutionRecord(
            workflow_id=workflow_id,
            step_id=step_id,
            tool_name=tool_name,
            status=status.value,
            input=input_data,
            output=output_data,
            error=error_data,
            retry_count=retry_count,
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )
        session.add(rec)
        await session.flush()
