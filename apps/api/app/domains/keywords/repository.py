"""Keywords domain database repository."""

from datetime import UTC, datetime
from uuid import UUID

from app.domains.keywords.models import (
    ClusteringRun,
    Keyword,
    KeywordCluster,
    KeywordClusterMember,
    KeywordImport,
    KeywordImportRow,
    KeywordStatus,
)
from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class KeywordRepository:
    """Repository managing keywords, imports, clustering runs, and clusters."""

    async def get_by_id(
        self, session: AsyncSession, *, keyword_id: UUID, project_id: UUID
    ) -> Keyword | None:
        stmt = select(Keyword).where(Keyword.id == keyword_id, Keyword.project_id == project_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_normalized(
        self, session: AsyncSession, *, project_id: UUID, normalized_keyword: str
    ) -> Keyword | None:
        stmt = select(Keyword).where(
            Keyword.project_id == project_id,
            Keyword.normalized_keyword == normalized_keyword,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_keyword(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        website_id: UUID | None,
        keyword: str,
        normalized_keyword: str,
        search_volume: int,
        keyword_difficulty: float,
        cpc: float,
        intent: str,
        intent_confidence: float,
        funnel_stage: str,
        business_value_score: float,
        priority_score: float,
        source: str,
        status: str = KeywordStatus.ACTIVE,
        provider_metadata: dict[str, object] | None = None,
    ) -> Keyword:
        kw = Keyword(
            organization_id=organization_id,
            project_id=project_id,
            website_id=website_id,
            keyword=keyword,
            normalized_keyword=normalized_keyword,
            search_volume=search_volume,
            keyword_difficulty=keyword_difficulty,
            cpc=cpc,
            intent=intent,
            intent_confidence=intent_confidence,
            funnel_stage=funnel_stage,
            business_value_score=business_value_score,
            priority_score=priority_score,
            source=source,
            status=status,
            provider_metadata=provider_metadata or {},
        )
        session.add(kw)
        await session.flush()
        return kw

    async def list_keywords(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        search: str | None = None,
        intent: str | None = None,
        status: str | None = None,
        min_volume: int | None = None,
        max_volume: int | None = None,
        min_difficulty: float | None = None,
        max_difficulty: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Keyword], int]:
        stmt = select(Keyword).where(Keyword.project_id == project_id)
        count_stmt = select(func.count(Keyword.id)).where(Keyword.project_id == project_id)

        if search:
            search_term = f"%{search.strip().lower()}%"
            filter_clause = or_(
                Keyword.normalized_keyword.ilike(search_term),
                Keyword.keyword.ilike(search_term),
            )
            stmt = stmt.where(filter_clause)
            count_stmt = count_stmt.where(filter_clause)

        if intent:
            stmt = stmt.where(Keyword.intent == intent)
            count_stmt = count_stmt.where(Keyword.intent == intent)

        if status:
            stmt = stmt.where(Keyword.status == status)
            count_stmt = count_stmt.where(Keyword.status == status)

        if min_volume is not None:
            stmt = stmt.where(Keyword.search_volume >= min_volume)
            count_stmt = count_stmt.where(Keyword.search_volume >= min_volume)

        if max_volume is not None:
            stmt = stmt.where(Keyword.search_volume <= max_volume)
            count_stmt = count_stmt.where(Keyword.search_volume <= max_volume)

        if min_difficulty is not None:
            stmt = stmt.where(Keyword.keyword_difficulty >= min_difficulty)
            count_stmt = count_stmt.where(Keyword.keyword_difficulty >= min_difficulty)

        if max_difficulty is not None:
            stmt = stmt.where(Keyword.keyword_difficulty <= max_difficulty)
            count_stmt = count_stmt.where(Keyword.keyword_difficulty <= max_difficulty)

        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar_one() or 0

        order_clause = (desc(Keyword.priority_score), desc(Keyword.search_volume))
        stmt = stmt.order_by(*order_clause).offset(offset).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total_count

    async def list_all_active_for_project(
        self, session: AsyncSession, *, project_id: UUID
    ) -> list[Keyword]:
        stmt = (
            select(Keyword)
            .where(
                Keyword.project_id == project_id,
                Keyword.status == KeywordStatus.ACTIVE,
            )
            .order_by(desc(Keyword.priority_score))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # --- Imports ---

    async def create_import(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        filename: str,
        source: str,
        created_by_id: UUID | None,
    ) -> KeywordImport:
        job = KeywordImport(
            organization_id=organization_id,
            project_id=project_id,
            filename=filename,
            source=source,
            created_by_id=created_by_id,
            status="processing",
        )
        session.add(job)
        await session.flush()
        return job

    async def add_import_row(
        self,
        session: AsyncSession,
        *,
        import_id: UUID,
        row_number: int,
        raw_data: dict[str, object],
        keyword: str,
        status: str,
        error_message: str | None = None,
        created_keyword_id: UUID | None = None,
    ) -> KeywordImportRow:
        row = KeywordImportRow(
            import_id=import_id,
            row_number=row_number,
            raw_data=raw_data,
            keyword=keyword,
            status=status,
            error_message=error_message,
            created_keyword_id=created_keyword_id,
        )
        session.add(row)
        return row

    async def get_import_by_id(
        self, session: AsyncSession, *, import_id: UUID, project_id: UUID
    ) -> KeywordImport | None:
        stmt = select(KeywordImport).where(
            KeywordImport.id == import_id, KeywordImport.project_id == project_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # --- Clustering Runs & Clusters ---

    async def create_clustering_run(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        status: str,
        algorithm_version: str,
        parameters: dict[str, object],
        created_by_id: UUID | None,
    ) -> ClusteringRun:
        run = ClusteringRun(
            organization_id=organization_id,
            project_id=project_id,
            status=status,
            algorithm_version=algorithm_version,
            parameters=parameters,
            created_by_id=created_by_id,
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        return run

    async def list_clustering_runs(
        self, session: AsyncSession, *, project_id: UUID
    ) -> list[ClusteringRun]:
        stmt = (
            select(ClusteringRun)
            .where(ClusteringRun.project_id == project_id)
            .order_by(desc(ClusteringRun.created_at))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def create_cluster(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID,
        topic_id: UUID | None = None,
        clustering_run_id: UUID | None = None,
        cluster_name: str,
        primary_keyword_id: UUID | None = None,
        intent: str,
        cluster_score: float,
        status: str,
        rationale: str,
    ) -> KeywordCluster:
        cluster = KeywordCluster(
            organization_id=organization_id,
            project_id=project_id,
            topic_id=topic_id,
            clustering_run_id=clustering_run_id,
            cluster_name=cluster_name,
            primary_keyword_id=primary_keyword_id,
            intent=intent,
            cluster_score=cluster_score,
            status=status,
            rationale=rationale,
        )
        session.add(cluster)
        await session.flush()
        return cluster

    async def add_cluster_member(
        self,
        session: AsyncSession,
        *,
        cluster_id: UUID,
        keyword_id: UUID,
        is_primary: bool,
        similarity_score: float,
    ) -> KeywordClusterMember:
        member = KeywordClusterMember(
            cluster_id=cluster_id,
            keyword_id=keyword_id,
            is_primary=is_primary,
            similarity_score=similarity_score,
        )
        session.add(member)
        return member

    async def get_cluster_by_id(
        self, session: AsyncSession, *, cluster_id: UUID, project_id: UUID
    ) -> KeywordCluster | None:
        stmt = select(KeywordCluster).where(
            KeywordCluster.id == cluster_id, KeywordCluster.project_id == project_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_clusters(
        self, session: AsyncSession, *, project_id: UUID, status: str | None = None
    ) -> list[KeywordCluster]:
        stmt = select(KeywordCluster).where(KeywordCluster.project_id == project_id)
        if status:
            stmt = stmt.where(KeywordCluster.status == status)
        stmt = stmt.order_by(desc(KeywordCluster.cluster_score), desc(KeywordCluster.created_at))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_cluster_memberships(
        self, session: AsyncSession, *, cluster_id: UUID
    ) -> list[tuple[KeywordClusterMember, Keyword]]:
        stmt = (
            select(KeywordClusterMember, Keyword)
            .join(Keyword, KeywordClusterMember.keyword_id == Keyword.id)
            .where(KeywordClusterMember.cluster_id == cluster_id)
            .order_by(
                desc(KeywordClusterMember.is_primary),
                desc(Keyword.search_volume),
            )
        )
        result = await session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def delete_cluster_members_for_keywords(
        self, session: AsyncSession, *, keyword_ids: list[UUID]
    ) -> None:
        if not keyword_ids:
            return
        stmt = delete(KeywordClusterMember).where(KeywordClusterMember.keyword_id.in_(keyword_ids))
        await session.execute(stmt)

    async def delete_cluster(self, session: AsyncSession, *, cluster_id: UUID) -> None:
        stmt = delete(KeywordCluster).where(KeywordCluster.id == cluster_id)
        await session.execute(stmt)
