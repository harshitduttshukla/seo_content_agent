"""Tenant-scoped persistence for V3 canvases and claims."""

from collections.abc import Sequence
from uuid import UUID

from app.domains.canvas.models import Area, Argument, Canvas, Claim
from app.domains.content_cards.models import ContentCard, ContentCardClaim
from app.domains.demand.models import DemandNode
from app.domains.job_runs.models import JobRun
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class CanvasRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_canvas_by_id(
        self, organization_id: UUID, project_id: UUID, canvas_id: UUID
    ) -> Canvas | None:
        result = await self._session.execute(
            select(Canvas).where(
                Canvas.organization_id == organization_id,
                Canvas.project_id == project_id,
                Canvas.id == canvas_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_company_canvas(self, organization_id: UUID, project_id: UUID) -> Canvas | None:
        result = await self._session.execute(
            select(Canvas).where(
                Canvas.organization_id == organization_id,
                Canvas.project_id == project_id,
                Canvas.parent_id.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_canvases_for_project(
        self, organization_id: UUID, project_id: UUID
    ) -> Sequence[Canvas]:
        result = await self._session.execute(
            select(Canvas)
            .where(
                Canvas.organization_id == organization_id,
                Canvas.project_id == project_id,
            )
            .order_by(Canvas.parent_id.nulls_first(), Canvas.product_line)
        )
        return result.scalars().all()

    async def get_argument_counts(self, organization_id: UUID, project_id: UUID) -> dict[UUID, int]:
        result = await self._session.execute(
            select(Argument.canvas_id, func.count(Argument.id))
            .where(
                Argument.organization_id == organization_id,
                Argument.project_id == project_id,
            )
            .group_by(Argument.canvas_id)
        )
        return {canvas_id: count for canvas_id, count in result.all()}

    async def get_arguments_for_canvas(
        self, organization_id: UUID, project_id: UUID, canvas_id: UUID
    ) -> Sequence[Argument]:
        result = await self._session.execute(
            select(Argument)
            .where(
                Argument.organization_id == organization_id,
                Argument.project_id == project_id,
                Argument.canvas_id == canvas_id,
            )
            .order_by(Argument.order)
        )
        return result.scalars().all()

    async def get_areas_for_project(
        self, organization_id: UUID, project_id: UUID, *, canvas_id: UUID | None = None
    ) -> Sequence[Area]:
        query = select(Area).where(
            Area.organization_id == organization_id,
            Area.project_id == project_id,
        )
        if canvas_id is not None:
            query = query.where(Area.canvas_id == canvas_id)
        result = await self._session.execute(
            query.order_by(Area.canvas_id, Area.parent_id.nulls_first(), Area.name)
        )
        return result.scalars().all()

    async def get_argument_by_id(
        self, organization_id: UUID, project_id: UUID, argument_id: UUID
    ) -> Argument | None:
        result = await self._session.execute(
            select(Argument).where(
                Argument.organization_id == organization_id,
                Argument.project_id == project_id,
                Argument.id == argument_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_next_argument_order(
        self, organization_id: UUID, project_id: UUID, canvas_id: UUID
    ) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(Argument.order) + 1, 0)).where(
                Argument.organization_id == organization_id,
                Argument.project_id == project_id,
                Argument.canvas_id == canvas_id,
            )
        )
        return int(result.scalar_one())

    async def get_claims_for_canvas(
        self, organization_id: UUID, project_id: UUID, canvas_id: UUID
    ) -> Sequence[Claim]:
        result = await self._session.execute(
            select(Claim)
            .where(
                Claim.organization_id == organization_id,
                Claim.project_id == project_id,
                Claim.canvas_id == canvas_id,
                Claim.superseded_by.is_(None),
            )
            .order_by(Claim.argument_id.nulls_first(), Claim.row, Claim.version.desc())
        )
        return result.scalars().all()

    async def get_claim_by_id(
        self, organization_id: UUID, project_id: UUID, claim_id: UUID
    ) -> Claim | None:
        result = await self._session.execute(
            select(Claim).where(
                Claim.organization_id == organization_id,
                Claim.project_id == project_id,
                Claim.id == claim_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_current_claim_for_cell(
        self,
        organization_id: UUID,
        project_id: UUID,
        canvas_id: UUID,
        argument_id: UUID | None,
        row: str,
    ) -> Claim | None:
        statement = select(Claim).where(
            Claim.organization_id == organization_id,
            Claim.project_id == project_id,
            Claim.canvas_id == canvas_id,
            Claim.row == row,
            Claim.superseded_by.is_(None),
        )
        if argument_id is None:
            statement = statement.where(Claim.argument_id.is_(None))
        else:
            statement = statement.where(Claim.argument_id == argument_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_citation_counts_for_claims(
        self, organization_id: UUID, project_id: UUID, claim_ids: Sequence[UUID]
    ) -> dict[UUID, int]:
        if not claim_ids:
            return {}
        result = await self._session.execute(
            select(ContentCardClaim.claim_id, func.count(ContentCardClaim.id))
            .where(
                ContentCardClaim.organization_id == organization_id,
                ContentCardClaim.project_id == project_id,
                ContentCardClaim.claim_id.in_(claim_ids),
            )
            .group_by(ContentCardClaim.claim_id)
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def get_citation_count(
        self, organization_id: UUID, project_id: UUID, claim_id: UUID
    ) -> int:
        result = await self._session.execute(
            select(func.count(ContentCardClaim.id)).where(
                ContentCardClaim.organization_id == organization_id,
                ContentCardClaim.project_id == project_id,
                ContentCardClaim.claim_id == claim_id,
            )
        )
        return int(result.scalar_one())

    async def get_argument_chain(
        self, organization_id: UUID, project_id: UUID, claim_id: UUID
    ) -> list[Claim]:
        claim = await self.get_claim_by_id(organization_id, project_id, claim_id)
        if claim is None:
            return []
        query = select(Claim).where(
            Claim.organization_id == organization_id,
            Claim.project_id == project_id,
            Claim.canvas_id == claim.canvas_id,
            Claim.superseded_by.is_(None),
        )
        if claim.argument_id is None:
            query = query.where(Claim.argument_id.is_(None))
        else:
            query = query.where(Claim.argument_id == claim.argument_id)
        result = await self._session.execute(query.order_by(Claim.row))
        return list(result.scalars().all())

    async def get_demand_for_claim(
        self, organization_id: UUID, project_id: UUID, claim_id: UUID
    ) -> list[DemandNode]:
        claim = await self.get_claim_by_id(organization_id, project_id, claim_id)
        if claim is None or claim.argument_id is None:
            return []
        result = await self._session.execute(
            select(DemandNode)
            .where(
                DemandNode.organization_id == organization_id,
                DemandNode.project_id == project_id,
                DemandNode.argument_id == claim.argument_id,
            )
            .order_by(DemandNode.score.desc().nulls_last(), DemandNode.text)
            .limit(50)
        )
        return list(result.scalars().all())

    async def get_cards_for_claim(
        self, organization_id: UUID, project_id: UUID, claim_id: UUID
    ) -> list[ContentCard]:
        result = await self._session.execute(
            select(ContentCard)
            .join(ContentCardClaim, ContentCardClaim.content_card_id == ContentCard.id)
            .where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
                ContentCardClaim.organization_id == organization_id,
                ContentCardClaim.project_id == project_id,
                ContentCardClaim.claim_id == claim_id,
            )
            .order_by(ContentCard.title)
        )
        return list(result.scalars().all())

    async def get_project_content_cards(
        self, organization_id: UUID, project_id: UUID
    ) -> list[ContentCard]:
        result = await self._session.execute(
            select(ContentCard)
            .where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
            )
            .order_by(ContentCard.title)
        )
        return list(result.scalars().all())

    async def get_content_card_by_id(
        self, organization_id: UUID, project_id: UUID, card_id: UUID
    ) -> ContentCard | None:
        result = await self._session.execute(
            select(ContentCard).where(
                ContentCard.organization_id == organization_id,
                ContentCard.project_id == project_id,
                ContentCard.id == card_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_content_card_claim(
        self, organization_id: UUID, project_id: UUID, card_id: UUID, claim_id: UUID
    ) -> ContentCardClaim | None:
        result = await self._session.execute(
            select(ContentCardClaim).where(
                ContentCardClaim.organization_id == organization_id,
                ContentCardClaim.project_id == project_id,
                ContentCardClaim.content_card_id == card_id,
                ContentCardClaim.claim_id == claim_id,
            )
        )
        return result.scalar_one_or_none()

    def add(
        self, entity: Canvas | Argument | Claim | JobRun | ContentCard | ContentCardClaim
    ) -> None:
        self._session.add(entity)
