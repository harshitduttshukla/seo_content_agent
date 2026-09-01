"""Repository operations for crawl jobs, URLs, and events."""

from datetime import UTC, datetime
from uuid import UUID

from app.domains.crawling.models import CrawlEvent, CrawlJob, CrawlJobStatus, CrawlUrl
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession


class CrawlRepository:
    async def create_job(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        website_id: UUID,
        requested_by_id: UUID,
        configuration: dict[str, object],
    ) -> CrawlJob:
        job = CrawlJob(
            organization_id=organization_id,
            project_id=project_id,
            website_id=website_id,
            status=CrawlJobStatus.QUEUED,
            configuration=configuration,
            requested_by_id=requested_by_id,
        )
        session.add(job)
        await session.flush()
        return job

    async def get_job(
        self, session: AsyncSession, *, crawl_job_id: UUID, organization_id: UUID | None = None
    ) -> CrawlJob | None:
        stmt = select(CrawlJob).where(CrawlJob.id == crawl_job_id)
        if organization_id is not None:
            stmt = stmt.where(CrawlJob.organization_id == organization_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_active_job_for_website(
        self, session: AsyncSession, *, website_id: UUID
    ) -> CrawlJob | None:
        stmt = (
            select(CrawlJob)
            .where(
                CrawlJob.website_id == website_id,
                CrawlJob.status.in_([CrawlJobStatus.QUEUED, CrawlJobStatus.RUNNING]),
            )
            .order_by(desc(CrawlJob.created_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    async def list_jobs_for_website(
        self, session: AsyncSession, *, website_id: UUID, limit: int = 50
    ) -> list[CrawlJob]:
        stmt = (
            select(CrawlJob)
            .where(CrawlJob.website_id == website_id)
            .order_by(desc(CrawlJob.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def add_url(
        self,
        session: AsyncSession,
        *,
        crawl_job_id: UUID,
        website_id: UUID,
        url: str,
        normalized_url: str,
        depth: int,
        source: str,
        status: str,
    ) -> CrawlUrl:
        crawl_url = CrawlUrl(
            crawl_job_id=crawl_job_id,
            website_id=website_id,
            url=url,
            normalized_url=normalized_url,
            depth=depth,
            source=source,
            status=status,
            discovered_at=datetime.now(UTC),
        )
        session.add(crawl_url)
        await session.flush()
        return crawl_url

    async def add_event(
        self,
        session: AsyncSession,
        *,
        crawl_job_id: UUID,
        event_type: str,
        message: str,
        url: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> CrawlEvent:
        event = CrawlEvent(
            crawl_job_id=crawl_job_id,
            event_type=event_type,
            url=url,
            message=message,
            metadata_=metadata or {},
            occurred_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()
        return event
