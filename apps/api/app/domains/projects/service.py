"""Project application service with assignment and tenant enforcement."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.cursor import decode_cursor, encode_cursor
from app.core.errors import ConflictError, ResourceNotFound
from app.core.pagination import PageResult
from app.core.validators import normalize_slug
from app.db.session import set_actor_context
from app.domains.audit.repository import (
    AuditWriter,
    IdempotencyRepository,
    OutboxWriter,
    request_fingerprint,
)
from app.domains.auth.repository import AuthorizationRepository
from app.domains.projects.models import Project, ProjectStatus
from app.domains.projects.repository import ProjectRepository
from app.domains.projects.schemas import (
    PlanLockState,
    ProjectCreate,
    ProjectDetail,
    ProjectUpdate,
)
from app.security.authorization import AuthorizationService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def is_added_after_plan_lock(card_created_at: datetime, plan_locked_at: datetime | None) -> bool:
    """V3 5.1 "new" chip: a Planned card created after the plan was locked.

    Derived, never stored. Before any lock nothing is "new". Callers apply it to
    cards in the Planned state; the state filter is theirs, not this function's.
    """
    return plan_locked_at is not None and card_created_at > plan_locked_at


class ProjectService:
    def __init__(self) -> None:
        self._projects = ProjectRepository()
        self._access_repository = AuthorizationRepository()
        self._authorization = AuthorizationService(self._access_repository)
        self._audit = AuditWriter()
        self._outbox = OutboxWriter()
        self._idempotency = IdempotencyRepository()

    async def create(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        payload: ProjectCreate,
        idempotency_key: str,
        request_id: str,
    ) -> ProjectDetail:
        slug = normalize_slug(payload.slug or payload.name)
        fingerprint = request_fingerprint(payload.model_dump(mode="json"))
        try:
            async with session.begin():
                await set_actor_context(session, actor.user_id)
                organization_role = await self._authorization.require_organization(
                    session,
                    user_id=actor.user_id,
                    organization_id=payload.organization_id,
                    permission=PermissionCode.PROJECT_CREATE,
                )
                record, created = await self._idempotency.claim(
                    session,
                    organization_id=payload.organization_id,
                    actor_user_id=actor.user_id,
                    route="POST /projects",
                    idempotency_key=idempotency_key,
                    request_hash=fingerprint,
                )
                if not created:
                    return ProjectDetail.model_validate(record.response_data)
                project = Project(
                    organization_id=payload.organization_id,
                    name=payload.name.strip(),
                    slug=slug,
                    description=payload.description.strip(),
                    status=ProjectStatus.ACTIVE,
                    default_locale=payload.default_locale,
                    default_country=payload.default_country,
                    settings={},
                )
                session.add(project)
                await session.flush()
                role_id = await self._access_repository.role_id(session, organization_role)
                await self._access_repository.add_project_member(
                    session,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    user_id=actor.user_id,
                    role_id=role_id,
                )
                detail = ProjectDetail.model_validate(project)
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    action="project.created",
                    resource_type="project",
                    resource_id=project.id,
                    request_id=request_id,
                )
                self._outbox.add(
                    session,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    aggregate_type="project",
                    aggregate_id=project.id,
                    event_type="project.created",
                )
                self._idempotency.complete(record, detail.model_dump(mode="json"), 201)
                return detail
        except IntegrityError as exc:
            raise ConflictError(
                "PROJECT_SLUG_CONFLICT", "An active project already uses this slug."
            ) from exc

    async def list(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> PageResult[ProjectDetail]:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            await self._authorization.require_organization(
                session,
                user_id=actor.user_id,
                organization_id=organization_id,
                permission=PermissionCode.PROJECT_READ,
            )
            rows = await self._projects.list_for_user(
                session,
                user_id=actor.user_id,
                organization_id=organization_id,
                cursor=decode_cursor(cursor),
                limit=limit,
            )
            has_more = len(rows) > limit
            visible = rows[:limit]
            return PageResult(
                items=[ProjectDetail.model_validate(row) for row in visible],
                next_cursor=(
                    encode_cursor(visible[-1].created_at, visible[-1].id)
                    if has_more and visible
                    else None
                ),
                has_more=has_more,
            )

    async def get_model(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        permission: PermissionCode,
    ) -> Project:
        project = await self._projects.get_for_organization_member(
            session, user_id=actor.user_id, project_id=project_id
        )
        if project is None:
            raise ResourceNotFound("project")
        await self._authorization.require_project(
            session,
            user_id=actor.user_id,
            organization_id=project.organization_id,
            project_id=project.id,
            permission=permission,
        )
        return project

    async def get(
        self, session: AsyncSession, *, actor: AuthenticatedUser, project_id: UUID
    ) -> ProjectDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.PROJECT_READ,
            )
            return ProjectDetail.model_validate(project)

    async def update(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: ProjectUpdate,
        request_id: str,
    ) -> ProjectDetail:
        try:
            async with session.begin():
                await set_actor_context(session, actor.user_id)
                project = await self.get_model(
                    session,
                    actor=actor,
                    project_id=project_id,
                    permission=PermissionCode.PROJECT_UPDATE,
                )
                if project.revision != payload.revision:
                    raise ConflictError(
                        "VERSION_CONFLICT",
                        "The project changed; refresh and retry.",
                        details={"current_revision": project.revision},
                    )
                project.name = payload.name.strip()
                project.slug = normalize_slug(payload.slug)
                project.description = payload.description.strip()
                project.status = payload.status
                project.default_locale = payload.default_locale
                project.default_country = payload.default_country
                project.revision += 1
                if payload.status == ProjectStatus.ARCHIVED and project.archived_at is None:
                    project.archived_at = datetime.now(UTC)
                await session.flush()
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    action="project.updated",
                    resource_type="project",
                    resource_id=project.id,
                    request_id=request_id,
                )
                return ProjectDetail.model_validate(project)
        except IntegrityError as exc:
            raise ConflictError(
                "PROJECT_SLUG_CONFLICT", "An active project already uses this slug."
            ) from exc

    async def lock_plan(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        project_id: UUID,
        request_id: str,
    ) -> PlanLockState:
        """Lock the Content Hub plan once (V3 5.1). Safe to repeat; never moves the time."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.PROJECT_UPDATE,
            )
            if project.organization_id != organization_id:
                raise ResourceNotFound("project")
            locked_at, locked_now = await self._projects.lock_plan(
                session, organization_id=organization_id, project_id=project_id
            )
            if locked_at is None:  # the scoped row vanished between the two reads
                raise ResourceNotFound("project")
            if locked_now:
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    action="project.plan_locked",
                    resource_type="project",
                    resource_id=project_id,
                    request_id=request_id,
                )
            return PlanLockState(
                project_id=project_id, plan_locked_at=locked_at, locked_now=locked_now
            )

    async def archive(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        request_id: str,
    ) -> ProjectDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.PROJECT_DELETE,
            )
            project.status = ProjectStatus.ARCHIVED
            project.archived_at = datetime.now(UTC)
            project.revision += 1
            await session.flush()
            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="project.archived",
                resource_type="project",
                resource_id=project.id,
                request_id=request_id,
            )
            return ProjectDetail.model_validate(project)
