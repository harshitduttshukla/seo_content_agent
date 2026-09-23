"""Repository for Content Harness run persistence and retrieval."""

from uuid import UUID

from app.domains.content_harness.models import ContentHarnessRun
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class ContentHarnessRepository:
    """Encapsulates tenant-isolated queries for content harness runs."""

    async def create(
        self,
        session: AsyncSession,
        run: ContentHarnessRun,
    ) -> ContentHarnessRun:
        session.add(run)
        await session.flush()
        return run

    async def get_by_id(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        organization_id: UUID,
        project_id: UUID,
    ) -> ContentHarnessRun | None:
        stmt = select(ContentHarnessRun).where(
            ContentHarnessRun.id == run_id,
            ContentHarnessRun.organization_id == organization_id,
            ContentHarnessRun.project_id == project_id,
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    async def list_by_project(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ContentHarnessRun]:
        stmt = (
            select(ContentHarnessRun)
            .where(
                ContentHarnessRun.organization_id == organization_id,
                ContentHarnessRun.project_id == project_id,
            )
            .order_by(ContentHarnessRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def count_by_project(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
    ) -> int:
        stmt = select(func.count(ContentHarnessRun.id)).where(
            ContentHarnessRun.organization_id == organization_id,
            ContentHarnessRun.project_id == project_id,
        )
        res = await session.execute(stmt)
        return int(res.scalar_one_or_none() or 0)
