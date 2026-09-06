"""Repository for Content Map nodes, edges, and architecture version history."""

from uuid import UUID

from app.domains.content_map.models import (
    ContentArchitectureVersion,
    ContentMapNode,
)
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession


class ContentMapRepository:
    async def get_node_by_entity(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        node_type: str,
        entity_id: UUID,
    ) -> ContentMapNode | None:
        stmt = select(ContentMapNode).where(
            ContentMapNode.project_id == project_id,
            ContentMapNode.node_type == node_type,
            ContentMapNode.entity_id == entity_id,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_nodes(self, session: AsyncSession, *, project_id: UUID) -> list[ContentMapNode]:
        stmt = select(ContentMapNode).where(ContentMapNode.project_id == project_id)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def upsert_node_position(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        node_type: str,
        entity_id: UUID,
        label: str,
        position_x: float,
        position_y: float,
    ) -> ContentMapNode:
        node = await self.get_node_by_entity(
            session, project_id=project_id, node_type=node_type, entity_id=entity_id
        )
        if node:
            node.position_x = position_x
            node.position_y = position_y
            node.label = label
            node.revision += 1
            await session.flush()
            return node

        new_node = ContentMapNode(
            organization_id=organization_id,
            project_id=project_id,
            node_type=node_type,
            entity_id=entity_id,
            label=label,
            position_x=position_x,
            position_y=position_y,
        )
        session.add(new_node)
        await session.flush()
        return new_node

    async def create_version(
        self, session: AsyncSession, version_obj: ContentArchitectureVersion
    ) -> ContentArchitectureVersion:
        session.add(version_obj)
        await session.flush()
        return version_obj

    async def list_versions(
        self, session: AsyncSession, *, project_id: UUID
    ) -> list[ContentArchitectureVersion]:
        stmt = (
            select(ContentArchitectureVersion)
            .where(ContentArchitectureVersion.project_id == project_id)
            .order_by(desc(ContentArchitectureVersion.version))
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_latest_version(
        self, session: AsyncSession, *, project_id: UUID
    ) -> ContentArchitectureVersion | None:
        stmt = (
            select(ContentArchitectureVersion)
            .where(ContentArchitectureVersion.project_id == project_id)
            .order_by(desc(ContentArchitectureVersion.version))
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()
