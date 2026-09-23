"""Tenant-scoped demand-node persistence."""

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from app.domains.canvas.models import Area, Argument
from app.domains.demand.models import DemandNode, DemandNodeStatus
from app.domains.job_runs.models import JobRun
from sqlalchemy import case, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession


class DemandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_demand_nodes(
        self,
        organization_id: UUID,
        project_id: UUID,
        *,
        status: str | None = None,
        origin: str | None = None,
        area_id: UUID | None = None,
        argument_id: UUID | None = None,
        node_type: str | None = None,
        funnel: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Sequence[DemandNode]:
        query = select(DemandNode).where(
            DemandNode.organization_id == organization_id,
            DemandNode.project_id == project_id,
        )
        if status is not None:
            query = query.where(DemandNode.status == status)
        for column, value in (
            (DemandNode.origin, origin),
            (DemandNode.area_id, area_id),
            (DemandNode.argument_id, argument_id),
            (DemandNode.type, node_type),
            (DemandNode.funnel, funnel),
        ):
            if value is not None:
                query = query.where(column == value)
        result = await self._session.execute(
            query.order_by(DemandNode.confidence.asc().nulls_last(), DemandNode.text)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return result.scalars().all()

    async def get_by_identity(
        self,
        organization_id: UUID,
        project_id: UUID,
        *,
        node_type: str,
        text: str,
        country: str | None,
    ) -> DemandNode | None:
        result = await self._session.execute(
            select(DemandNode).where(
                DemandNode.organization_id == organization_id,
                DemandNode.project_id == project_id,
                DemandNode.type == node_type,
                DemandNode.text == text,
                DemandNode.country == country,
            )
        )
        return result.scalar_one_or_none()

    async def get_area_by_id(
        self, organization_id: UUID, project_id: UUID, area_id: UUID
    ) -> Area | None:
        result = await self._session.execute(
            select(Area).where(
                Area.organization_id == organization_id,
                Area.project_id == project_id,
                Area.id == area_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_nodes_by_ids(
        self, organization_id: UUID, project_id: UUID, node_ids: Sequence[UUID]
    ) -> Sequence[DemandNode]:
        """Load the selected nodes; ids from another project simply do not match."""
        result = await self._session.execute(
            select(DemandNode).where(
                DemandNode.organization_id == organization_id,
                DemandNode.project_id == project_id,
                DemandNode.id.in_(node_ids),
            )
        )
        return result.scalars().all()

    async def get_areas_by_ids(
        self, organization_id: UUID, project_id: UUID, area_ids: Sequence[UUID]
    ) -> Sequence[Area]:
        result = await self._session.execute(
            select(Area).where(
                Area.organization_id == organization_id,
                Area.project_id == project_id,
                Area.id.in_(area_ids),
            )
        )
        return result.scalars().all()

    async def get_areas_by_name(
        self, organization_id: UUID, project_id: UUID, name: str
    ) -> Sequence[Area]:
        result = await self._session.execute(
            select(Area).where(
                Area.organization_id == organization_id,
                Area.project_id == project_id,
                Area.name == name,
            )
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

    async def get_summary(
        self, organization_id: UUID, project_id: UUID
    ) -> tuple[int, int, int, int]:
        result = await self._session.execute(
            select(
                func.count(DemandNode.id),
                func.sum(case((DemandNode.status == DemandNodeStatus.DISCARDED, 1), else_=0)),
                func.sum(case((DemandNode.status == DemandNodeStatus.KEPT, 1), else_=0)),
                func.sum(case((DemandNode.origin == "gsc_striking_distance", 1), else_=0)),
            ).where(
                DemandNode.organization_id == organization_id,
                DemandNode.project_id == project_id,
            )
        )
        total, discarded, kept, gsc = result.one()
        return int(total or 0), int(discarded or 0), int(kept or 0), int(gsc or 0)

    async def bulk_update_status(
        self,
        organization_id: UUID,
        project_id: UUID,
        node_ids: list[UUID],
        new_status: DemandNodeStatus,
    ) -> int:
        result = await self._session.execute(
            update(DemandNode)
            .where(
                DemandNode.organization_id == organization_id,
                DemandNode.project_id == project_id,
                DemandNode.id.in_(node_ids),
            )
            .values(status=new_status)
        )
        return int(cast(CursorResult[object], result).rowcount or 0)

    async def bulk_reassign_area(
        self,
        organization_id: UUID,
        project_id: UUID,
        node_ids: list[UUID],
        area_id: UUID,
    ) -> int:
        result = await self._session.execute(
            update(DemandNode)
            .where(
                DemandNode.organization_id == organization_id,
                DemandNode.project_id == project_id,
                DemandNode.id.in_(node_ids),
            )
            .values(area_id=area_id)
        )
        return int(cast(CursorResult[object], result).rowcount or 0)

    async def bulk_set_argument(
        self, organization_id: UUID, project_id: UUID, node_ids: list[UUID], argument_id: UUID
    ) -> int:
        result = await self._session.execute(
            update(DemandNode)
            .where(
                DemandNode.organization_id == organization_id,
                DemandNode.project_id == project_id,
                DemandNode.id.in_(node_ids),
            )
            .values(argument_id=argument_id)
        )
        return int(cast(CursorResult[object], result).rowcount or 0)

    def add_job_run(self, job_run: JobRun) -> None:
        self._session.add(job_run)

    def add_node(self, node: DemandNode) -> None:
        self._session.add(node)
