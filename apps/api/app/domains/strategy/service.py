"""Strategy domain application service."""

from uuid import UUID

from app.core.errors import ResourceNotFound
from app.db.session import set_actor_context
from app.domains.audit.repository import AuditWriter, OutboxWriter
from app.domains.projects.service import ProjectService
from app.domains.strategy.models import StrategyStatus
from app.domains.strategy.repository import SEOStrategyRepository
from app.domains.strategy.schemas import (
    StrategyDataSchema,
    StrategyResponse,
    StrategyUpdateRequest,
    StrategyVersionListResponse,
    StrategyVersionResponse,
)
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class SEOStrategyService:
    def __init__(self) -> None:
        self._repository = SEOStrategyRepository()
        self._projects = ProjectService()
        self._audit = AuditWriter()
        self._outbox = OutboxWriter()

    async def get_or_create_strategy(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        request_id: str = "",
    ) -> StrategyResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            strategy = await self._repository.get_by_project_id(session, project_id=project.id)
            if strategy is None:
                strategy = await self._repository.create_strategy(
                    session,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    current_version=1,
                    status=StrategyStatus.ACTIVE,
                )
                default_data = StrategyDataSchema()
                v1 = await self._repository.create_version(
                    session,
                    strategy_id=strategy.id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    version=1,
                    created_by_id=actor.user_id,
                    change_summary="Initial strategy template initialized",
                    strategy_data=default_data.model_dump(mode="json"),
                )
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    action="strategy.created",
                    resource_type="seo_strategy",
                    resource_id=strategy.id,
                    request_id=request_id,
                )
                await session.flush()
                await session.refresh(strategy)
                return StrategyResponse(
                    id=strategy.id,
                    organization_id=strategy.organization_id,
                    project_id=strategy.project_id,
                    current_version=strategy.current_version,
                    status=strategy.status,
                    strategy_data=default_data,
                    change_summary=v1.change_summary,
                    created_at=strategy.created_at,
                    updated_at=strategy.updated_at,
                )

            latest_version = await self._repository.get_latest_version(
                session, strategy_id=strategy.id
            )
            strategy_data = (
                StrategyDataSchema.model_validate(latest_version.strategy_data)
                if latest_version
                else StrategyDataSchema()
            )
            return StrategyResponse(
                id=strategy.id,
                organization_id=strategy.organization_id,
                project_id=strategy.project_id,
                current_version=strategy.current_version,
                status=strategy.status,
                strategy_data=strategy_data,
                change_summary=latest_version.change_summary if latest_version else "",
                created_at=strategy.created_at,
                updated_at=strategy.updated_at,
            )

    async def update_strategy(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: StrategyUpdateRequest,
        request_id: str = "",
    ) -> StrategyResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_WRITE,
            )
            strategy = await self._repository.get_by_project_id(session, project_id=project.id)
            if strategy is None:
                strategy = await self._repository.create_strategy(
                    session,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    current_version=1,
                    status=StrategyStatus.ACTIVE,
                )
                new_version_no = 1
            else:
                new_version_no = strategy.current_version + 1
                strategy.current_version = new_version_no
                strategy.revision += 1

            summary = payload.change_summary.strip() or f"Updated to version {new_version_no}"
            version = await self._repository.create_version(
                session,
                strategy_id=strategy.id,
                organization_id=project.organization_id,
                project_id=project.id,
                version=new_version_no,
                created_by_id=actor.user_id,
                change_summary=summary,
                strategy_data=payload.strategy_data.model_dump(mode="json"),
            )
            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="strategy.updated",
                resource_type="seo_strategy",
                resource_id=strategy.id,
                request_id=request_id,
                metadata={
                    "version": new_version_no,
                    "change_summary": version.change_summary,
                },
            )
            self._outbox.add(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                aggregate_type="seo_strategy",
                aggregate_id=strategy.id,
                event_type="strategy.version_created",
                payload={"version": new_version_no},
            )
            await session.flush()
            await session.refresh(strategy)
            return StrategyResponse(
                id=strategy.id,
                organization_id=strategy.organization_id,
                project_id=strategy.project_id,
                current_version=strategy.current_version,
                status=strategy.status,
                strategy_data=payload.strategy_data,
                change_summary=version.change_summary,
                created_at=strategy.created_at,
                updated_at=strategy.updated_at,
            )

    async def list_versions(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
    ) -> StrategyVersionListResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            strategy = await self._repository.get_by_project_id(session, project_id=project.id)
            if strategy is None:
                return StrategyVersionListResponse(items=[])

            versions = await self._repository.list_versions(session, strategy_id=strategy.id)
            items = [
                StrategyVersionResponse(
                    id=v.id,
                    strategy_id=v.strategy_id,
                    organization_id=v.organization_id,
                    project_id=v.project_id,
                    version=v.version,
                    created_by_id=v.created_by_id,
                    change_summary=v.change_summary,
                    strategy_data=StrategyDataSchema.model_validate(v.strategy_data),
                    created_at=v.created_at,
                )
                for v in versions
            ]
            return StrategyVersionListResponse(items=items)

    async def get_version(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        version: int,
    ) -> StrategyVersionResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            strategy = await self._repository.get_by_project_id(session, project_id=project.id)
            if strategy is None:
                raise ResourceNotFound("seo_strategy")

            v = await self._repository.get_version_by_number(
                session, strategy_id=strategy.id, version=version
            )
            if v is None:
                raise ResourceNotFound("seo_strategy_version")

            return StrategyVersionResponse(
                id=v.id,
                strategy_id=v.strategy_id,
                organization_id=v.organization_id,
                project_id=v.project_id,
                version=v.version,
                created_by_id=v.created_by_id,
                change_summary=v.change_summary,
                strategy_data=StrategyDataSchema.model_validate(v.strategy_data),
                created_at=v.created_at,
            )
