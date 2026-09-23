"""Tenant-scoped persistence for V3 content cards and site-import jobs."""

from collections.abc import Sequence
from uuid import UUID

from app.domains.content_cards.models import ContentCard, ContentCardOrigin
from app.domains.job_runs.models import JobRun
from sqlalchemy import desc, func, or_, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession


class ContentCardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add_content_card(self, entity: ContentCard) -> None:
        self._session.add(entity)

    def add_job_run(self, entity: JobRun) -> None:
        self._session.add(entity)

    async def get_carded_demand_ids(
        self, organization_id: UUID, project_id: UUID, node_ids: Sequence[UUID]
    ) -> set[UUID]:
        """Which of these demand nodes a card in this project already references.

        A node counts as carded when it is any card's primary demand, primary
        prompt, or one of its secondary demands, in any state.
        """
        wanted = {str(node_id) for node_id in node_ids}
        result = await self._session.execute(
            select(
                ContentCard.primary_demand_id,
                ContentCard.primary_prompt_id,
                ContentCard.secondary_demand_ids,
            ).where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
                or_(
                    ContentCard.primary_demand_id.in_(node_ids),
                    ContentCard.primary_prompt_id.in_(node_ids),
                    ContentCard.secondary_demand_ids.op("?|")(array(sorted(wanted))),
                ),
            )
        )
        carded: set[UUID] = set()
        for primary, prompt, secondaries in result.all():
            referenced = {str(primary), str(prompt), *(str(item) for item in secondaries)}
            carded.update(UUID(value) for value in referenced & wanted)
        return carded

    async def get_by_url(
        self, organization_id: UUID, project_id: UUID, url: str
    ) -> ContentCard | None:
        result = await self._session.execute(
            select(ContentCard).where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
                ContentCard.url == url,
            )
        )
        return result.scalar_one_or_none()

    async def count_unmapped_cards(self, organization_id: UUID, project_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count(ContentCard.id)).where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
                ContentCard.origin == ContentCardOrigin.IMPORT,
                ContentCard.argument_id.is_(None),
            )
        )
        return int(result.scalar_one())

    async def get_job_run(
        self, organization_id: UUID, project_id: UUID, job_run_id: UUID
    ) -> JobRun | None:
        result = await self._session.execute(
            select(JobRun).where(
                JobRun.organization_id == organization_id,
                JobRun.project_id == project_id,
                JobRun.id == job_run_id,
                JobRun.job_type == "site_import",
            )
        )
        return result.scalar_one_or_none()

    async def get_last_import_job(self, organization_id: UUID, project_id: UUID) -> JobRun | None:
        result = await self._session.execute(
            select(JobRun)
            .where(
                JobRun.organization_id == organization_id,
                JobRun.project_id == project_id,
                JobRun.job_type == "site_import",
            )
            .order_by(desc(JobRun.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
