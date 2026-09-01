"""Website service with URL normalization and project authorization."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.cursor import decode_cursor, encode_cursor
from app.core.errors import ConflictError, ResourceNotFound
from app.core.pagination import PageResult
from app.core.validators import normalize_website_url
from app.db.session import set_actor_context
from app.domains.audit.repository import (
    AuditWriter,
    IdempotencyRepository,
    OutboxWriter,
    request_fingerprint,
)
from app.domains.projects.service import ProjectService
from app.domains.websites.models import Website, WebsiteStatus
from app.domains.websites.repository import WebsiteRepository
from app.domains.websites.schemas import WebsiteCreate, WebsiteDetail, WebsiteUpdate
from app.security.authorization import AuthorizationService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class WebsiteService:
    def __init__(self) -> None:
        self._websites = WebsiteRepository()
        self._projects = ProjectService()
        self._authorization = AuthorizationService()
        self._audit = AuditWriter()
        self._outbox = OutboxWriter()
        self._idempotency = IdempotencyRepository()

    async def create(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: WebsiteCreate,
        idempotency_key: str,
        request_id: str,
    ) -> WebsiteDetail:
        base_url, host = normalize_website_url(payload.url)
        request_data = payload.model_dump(mode="json") | {"project_id": str(project_id)}
        try:
            async with session.begin():
                await set_actor_context(session, actor.user_id)
                project = await self._projects.get_model(
                    session,
                    actor=actor,
                    project_id=project_id,
                    permission=PermissionCode.WEBSITE_CREATE,
                )
                record, created = await self._idempotency.claim(
                    session,
                    organization_id=project.organization_id,
                    actor_user_id=actor.user_id,
                    route=f"POST /projects/{project_id}/websites",
                    idempotency_key=idempotency_key,
                    request_hash=request_fingerprint(request_data),
                )
                if not created:
                    return WebsiteDetail.model_validate(record.response_data)
                website = Website(
                    organization_id=project.organization_id,
                    project_id=project.id,
                    name=payload.name.strip(),
                    base_url=base_url,
                    normalized_host=host,
                    status=WebsiteStatus.ACTIVE,
                    locale=payload.locale,
                    country=payload.country,
                    verification_status="unverified",
                    settings={},
                )
                session.add(website)
                await session.flush()
                detail = WebsiteDetail.model_validate(website)
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=website.organization_id,
                    project_id=website.project_id,
                    action="website.created",
                    resource_type="website",
                    resource_id=website.id,
                    request_id=request_id,
                )
                self._outbox.add(
                    session,
                    organization_id=website.organization_id,
                    project_id=website.project_id,
                    aggregate_type="website",
                    aggregate_id=website.id,
                    event_type="website.created",
                )
                self._idempotency.complete(record, detail.model_dump(mode="json"), 201)
                return detail
        except IntegrityError as exc:
            raise ConflictError(
                "WEBSITE_EXISTS",
                "An active website with this host and locale already exists in the project.",
            ) from exc

    async def list(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> PageResult[WebsiteDetail]:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            rows = await self._websites.list_for_project(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                cursor=decode_cursor(cursor),
                limit=limit,
            )
            has_more = len(rows) > limit
            visible = rows[:limit]
            return PageResult(
                items=[WebsiteDetail.model_validate(row) for row in visible],
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
        website_id: UUID,
        permission: PermissionCode,
    ) -> Website:
        website = await self._websites.get_for_organization_member(
            session, user_id=actor.user_id, website_id=website_id
        )
        if website is None:
            raise ResourceNotFound("website")
        await self._authorization.require_project(
            session,
            user_id=actor.user_id,
            organization_id=website.organization_id,
            project_id=website.project_id,
            permission=permission,
        )
        return website

    async def get(
        self, session: AsyncSession, *, actor: AuthenticatedUser, website_id: UUID
    ) -> WebsiteDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            website = await self.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            return WebsiteDetail.model_validate(website)

    async def update(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        website_id: UUID,
        payload: WebsiteUpdate,
        request_id: str,
    ) -> WebsiteDetail:
        base_url, host = normalize_website_url(payload.url)
        try:
            async with session.begin():
                await set_actor_context(session, actor.user_id)
                website = await self.get_model(
                    session,
                    actor=actor,
                    website_id=website_id,
                    permission=PermissionCode.WEBSITE_UPDATE,
                )
                if website.revision != payload.revision:
                    raise ConflictError(
                        "VERSION_CONFLICT",
                        "The website changed; refresh and retry.",
                        details={"current_revision": website.revision},
                    )
                website.name = payload.name.strip()
                website.base_url = base_url
                website.normalized_host = host
                website.status = payload.status
                website.locale = payload.locale
                website.country = payload.country
                website.revision += 1
                if payload.status == WebsiteStatus.ARCHIVED and website.archived_at is None:
                    website.archived_at = datetime.now(UTC)
                await session.flush()
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=website.organization_id,
                    project_id=website.project_id,
                    action="website.updated",
                    resource_type="website",
                    resource_id=website.id,
                    request_id=request_id,
                )
                return WebsiteDetail.model_validate(website)
        except IntegrityError as exc:
            raise ConflictError(
                "WEBSITE_EXISTS",
                "An active website with this host and locale already exists in the project.",
            ) from exc

    async def archive(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        website_id: UUID,
        request_id: str,
    ) -> WebsiteDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            website = await self.get_model(
                session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_DELETE,
            )
            website.status = WebsiteStatus.ARCHIVED
            website.archived_at = datetime.now(UTC)
            website.revision += 1
            await session.flush()
            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=website.organization_id,
                project_id=website.project_id,
                action="website.archived",
                resource_type="website",
                resource_id=website.id,
                request_id=request_id,
            )
            return WebsiteDetail.model_validate(website)
