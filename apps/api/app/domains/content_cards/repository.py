"""Tenant-scoped persistence for V3 content cards and site-import jobs."""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.domains.canvas.models import Area, Argument
from app.domains.content_cards.models import ContentCard, ContentCardOrigin
from app.domains.content_cards.schemas import BoardFilters
from app.domains.demand.models import DemandNode
from app.domains.job_runs.models import JobRun
from app.domains.users.models import User
from sqlalchemy import desc, func, or_, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased


@dataclass(frozen=True, slots=True)
class BoardRow:
    """One card plus the names and demand facts its face shows, from one query."""

    card: ContentCard
    area_name: str | None
    argument_name: str | None
    owner_name: str | None
    demand_text: str | None
    demand_volume: int | None
    demand_score: float | None
    prompt_text: str | None
    prompt_score: float | None
    prompt_citation_gap: float | None
    prompt_platforms: list[str] | None


@dataclass(frozen=True, slots=True)
class BoardFacet:
    """Distinct filterable values across a project's cards (unfiltered)."""

    area_id: UUID | None
    area_name: str | None
    argument_id: UUID | None
    argument_name: str | None
    owner_id: UUID | None
    owner_name: str | None
    kind: str
    market: dict[str, object]


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

    async def list_board_rows(
        self,
        organization_id: UUID,
        project_id: UUID,
        filters: BoardFilters,
        *,
        card_id: UUID | None = None,
    ) -> list[BoardRow]:
        """Every card on the board with its face data: one query, outer joins only.

        Each joined table is also constrained to the same tenant, so a dangling or
        foreign reference renders as missing rather than leaking another row.
        """
        demand = aliased(DemandNode)
        prompt = aliased(DemandNode)
        scope = (
            ContentCard.organization_id == organization_id,
            ContentCard.project_id == project_id,
        )
        statement = (
            select(
                ContentCard,
                Area.name,
                Argument.differentiation_pillar,
                User.display_name,
                demand.text,
                demand.volume,
                demand.score,
                prompt.text,
                prompt.score,
                prompt.citation_gap,
                prompt.platforms,
            )
            .outerjoin(
                Area,
                (Area.id == ContentCard.area_id)
                & (Area.organization_id == organization_id)
                & (Area.project_id == project_id),
            )
            .outerjoin(
                Argument,
                (Argument.id == ContentCard.argument_id)
                & (Argument.organization_id == organization_id)
                & (Argument.project_id == project_id),
            )
            .outerjoin(User, User.id == ContentCard.owner)
            .outerjoin(
                demand,
                (demand.id == ContentCard.primary_demand_id)
                & (demand.organization_id == organization_id)
                & (demand.project_id == project_id),
            )
            .outerjoin(
                prompt,
                (prompt.id == ContentCard.primary_prompt_id)
                & (prompt.organization_id == organization_id)
                & (prompt.project_id == project_id),
            )
            .where(*scope)
            .order_by(
                ContentCard.priority,
                ContentCard.planned_at.asc().nulls_last(),
                ContentCard.created_at,
                ContentCard.id,
            )
        )
        if card_id is not None:
            statement = statement.where(ContentCard.id == card_id)
        if filters.area_id is not None:
            statement = statement.where(ContentCard.area_id == filters.area_id)
        if filters.kind is not None:
            statement = statement.where(ContentCard.kind == filters.kind)
        if filters.owner_id is not None:
            statement = statement.where(ContentCard.owner == filters.owner_id)
        if filters.argument_id is not None:
            statement = statement.where(ContentCard.argument_id == filters.argument_id)
        if filters.market is not None:
            lang, country = filters.market.split("-", 1)
            statement = statement.where(
                ContentCard.market["lang"].astext == lang,
                ContentCard.market["country"].astext == country,
            )
        result = await self._session.execute(statement)
        return [BoardRow(*row) for row in result.tuples().all()]

    async def list_board_facets(self, organization_id: UUID, project_id: UUID) -> list[BoardFacet]:
        """Distinct (area, argument, owner, kind, market) combinations, one query."""
        statement = (
            select(
                ContentCard.area_id,
                Area.name,
                ContentCard.argument_id,
                Argument.differentiation_pillar,
                ContentCard.owner,
                User.display_name,
                ContentCard.kind,
                ContentCard.market,
            )
            .distinct()
            .outerjoin(
                Area,
                (Area.id == ContentCard.area_id)
                & (Area.organization_id == organization_id)
                & (Area.project_id == project_id),
            )
            .outerjoin(
                Argument,
                (Argument.id == ContentCard.argument_id)
                & (Argument.organization_id == organization_id)
                & (Argument.project_id == project_id),
            )
            .outerjoin(User, User.id == ContentCard.owner)
            .where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
            )
        )
        result = await self._session.execute(statement)
        return [BoardFacet(*row) for row in result.tuples().all()]

    async def get_for_update(
        self, organization_id: UUID, project_id: UUID, card_id: UUID
    ) -> ContentCard | None:
        result = await self._session.execute(
            select(ContentCard)
            .where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
                ContentCard.id == card_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_in_states_for_update(
        self, organization_id: UUID, project_id: UUID, states: Sequence[str]
    ) -> list[ContentCard]:
        """Lock a project's cards in these states, in id order to avoid deadlocks."""
        result = await self._session.execute(
            select(ContentCard)
            .where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
                ContentCard.state.in_(states),
            )
            .order_by(ContentCard.id)
            .with_for_update()
        )
        return list(result.scalars().all())

    async def max_priority_in_states(
        self, organization_id: UUID, project_id: UUID, states: Sequence[str]
    ) -> int | None:
        result = await self._session.execute(
            select(func.max(ContentCard.priority)).where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
                ContentCard.state.in_(states),
            )
        )
        value = result.scalar_one_or_none()
        return int(value) if value is not None else None
