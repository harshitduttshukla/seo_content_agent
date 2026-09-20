"""Application service for idempotent V3 site imports."""

from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID, uuid4

from app.core.errors import ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.content_cards.models import ContentCard, ContentCardKind, ContentCardOrigin
from app.domains.content_cards.repository import ContentCardRepository
from app.domains.content_cards.schemas import SiteImportResponse, SiteImportStatusResponse
from app.domains.job_runs.models import JobRun, JobRunStatus
from app.security.authorization import AuthorizationService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class SiteImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ContentCardRepository(session)
        self._session = session
        from app.domains.auth.repository import AuthorizationRepository
        self._authorization = AuthorizationService(AuthorizationRepository())

    async def run_site_import(
        self,
        organization_id: UUID,
        project_id: UUID,
        url: str,
        actor: AuthenticatedUser,
        *,
        website_id: UUID | None = None,
        force_refresh: bool = False,
    ) -> SiteImportResponse:
        normalized_url = url.rstrip("/") or url
        created_count = 0
        existing_count = 0
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.WEBSITE_UPDATE,
            )
            existing_card = await self.repository.get_by_url(
                organization_id, project_id, normalized_url
            )
            if existing_card is None:
                host = urlparse(normalized_url).hostname or normalized_url
                self.repository.add_content_card(
                    ContentCard(
                        id=uuid4(),
                        organization_id=organization_id,
                        project_id=project_id,
                        kind=ContentCardKind.CLUSTER,
                        title=host,
                        url=normalized_url,
                        origin=ContentCardOrigin.IMPORT,
                    )
                )
                created_count = 1
            else:
                existing_count = 1
            now = datetime.now(UTC)
            job_run = JobRun(
                id=uuid4(),
                organization_id=organization_id,
                project_id=project_id,
                job_type="site_import",
                prompt_version="v3.site-import.v1",
                model="deterministic",
                provider="internal",
                status=JobRunStatus.COMPLETED,
                triggered_by=str(actor.user_id),
                entity_type="website" if website_id is not None else "project",
                entity_id=website_id or project_id,
                input_data={
                    "url": normalized_url,
                    "website_id": str(website_id) if website_id else None,
                    "force_refresh": force_refresh,
                },
                output_data={
                    "created_count": created_count,
                    "existing_count": existing_count,
                },
                started_at=now,
                completed_at=now,
            )
            self.repository.add_job_run(job_run)
            await self._session.flush()
        return SiteImportResponse(
            job_run_id=job_run.id,
            status=job_run.status,
            created_count=created_count,
            existing_count=existing_count,
        )

    async def get_import_status(
        self, organization_id: UUID, project_id: UUID, job_run_id: UUID, *, actor: AuthenticatedUser
    ) -> SiteImportStatusResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            job = await self.repository.get_job_run(organization_id, project_id, job_run_id)
        if job is None:
            raise ResourceNotFound("site_import_job")
        output = job.output_data or {}
        created_count = output.get("created_count")
        existing_count = output.get("existing_count")
        return SiteImportStatusResponse(
            job_run_id=job.id,
            status=job.status,
            created_at=job.created_at,
            completed_at=job.completed_at,
            created_count=created_count if isinstance(created_count, int) else 0,
            existing_count=existing_count if isinstance(existing_count, int) else 0,
            unmapped_count=await self.repository.count_unmapped_cards(organization_id, project_id),
        )
