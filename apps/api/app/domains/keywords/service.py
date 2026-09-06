"""Keywords domain application service."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import DomainError, ResourceNotFound
from app.db.session import set_actor_context
from app.domains.audit.repository import AuditWriter, OutboxWriter
from app.domains.keywords.clustering import (
    KeywordClusteringInput,
    cluster_keywords,
)
from app.domains.keywords.importer import parse_csv_keywords
from app.domains.keywords.intent import (
    calculate_business_value,
    calculate_priority_score,
    classify_intent_and_funnel,
)
from app.domains.keywords.models import (
    ClusteringRunStatus,
    ClusterStatus,
    FunnelStage,
    KeywordCluster,
    KeywordSource,
    SearchIntent,
)
from app.domains.keywords.normalizer import normalize_keyword
from app.domains.keywords.repository import KeywordRepository
from app.domains.keywords.schemas import (
    ClusteringRunRequest,
    ClusteringRunResponse,
    ClusterMergeRequest,
    ClusterUpdateRequest,
    KeywordClusterDeleteResponse,
    KeywordClusterDetail,
    KeywordClusterList,
    KeywordClusterMemberDetail,
    KeywordCreate,
    KeywordDeleteResponse,
    KeywordDetail,
    KeywordImportResponse,
    KeywordList,
    KeywordUpdate,
    MoveKeywordsRequest,
)
from app.domains.projects.service import ProjectService
from app.domains.strategy.repository import SEOStrategyRepository
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class KeywordService:
    def __init__(self) -> None:
        self._repository = KeywordRepository()
        self._projects = ProjectService()
        self._strategy_repo = SEOStrategyRepository()
        self._audit = AuditWriter()
        self._outbox = OutboxWriter()

    async def _get_strategy_terms(self, session: AsyncSession, *, project_id: UUID) -> list[str]:
        """Fetch strategic product/service/topic keywords for business relevance scoring."""
        strategy = await self._strategy_repo.get_by_project_id(session, project_id=project_id)
        if not strategy:
            return []
        version = await self._strategy_repo.get_latest_version(session, strategy_id=strategy.id)
        if not version or not version.strategy_data:
            return []
        data = version.strategy_data
        terms: list[str] = []
        products = data.get("products")
        if isinstance(products, list):
            for p in products:
                if isinstance(p, dict) and p.get("name"):
                    terms.append(str(p["name"]))
        services = data.get("services")
        if isinstance(services, list):
            for s in services:
                if isinstance(s, dict) and s.get("name"):
                    terms.append(str(s["name"]))
        topics = data.get("priority_topics")
        if isinstance(topics, list):
            for t in topics:
                if isinstance(t, str):
                    terms.append(t)
        return terms

    async def create_keyword(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: KeywordCreate,
        request_id: str = "",
    ) -> KeywordDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            raw_kw = payload.keyword.strip()
            norm_kw = normalize_keyword(raw_kw)
            if not norm_kw:
                raise DomainError(
                    "INVALID_KEYWORD",
                    "Keyword cannot be empty after normalization.",
                )

            existing = await self._repository.get_by_normalized(
                session, project_id=project.id, normalized_keyword=norm_kw
            )
            if existing:
                raise DomainError(
                    "KEYWORD_DUPLICATE",
                    f"Keyword '{raw_kw}' already exists in this project.",
                )

            if not payload.intent or str(payload.intent).upper() == "UNKNOWN":
                intent_res = classify_intent_and_funnel(raw_kw)
                intent_val = intent_res.intent
                confidence = intent_res.confidence
                funnel_val = intent_res.funnel_stage
            else:
                intent_str = str(payload.intent).upper()
                intent_val = (
                    SearchIntent(intent_str)
                    if intent_str in SearchIntent.__members__
                    else SearchIntent.INFORMATIONAL
                )
                confidence = 1.0
                funnel_str = str(payload.funnel_stage).upper()
                funnel_val = (
                    FunnelStage(funnel_str)
                    if funnel_str in FunnelStage.__members__
                    else FunnelStage.TOFU
                )

            strategy_terms = await self._get_strategy_terms(session, project_id=project.id)
            bv_score = calculate_business_value(
                intent_val,
                cpc=payload.cpc,
                keyword=raw_kw,
                strategy_terms=strategy_terms,
            )
            p_score = calculate_priority_score(
                search_volume=payload.search_volume,
                keyword_difficulty=payload.keyword_difficulty,
                business_value_score=bv_score,
                intent=intent_val,
            )

            kw = await self._repository.create_keyword(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                website_id=payload.website_id,
                keyword=raw_kw,
                normalized_keyword=norm_kw,
                search_volume=payload.search_volume,
                keyword_difficulty=payload.keyword_difficulty,
                cpc=payload.cpc,
                intent=str(intent_val),
                intent_confidence=confidence,
                funnel_stage=str(funnel_val),
                business_value_score=bv_score,
                priority_score=p_score,
                source=str(payload.source),
            )

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="keyword.created",
                resource_type="keyword",
                resource_id=kw.id,
                request_id=request_id,
                metadata={
                    "keyword": raw_kw,
                    "intent": str(intent_val),
                    "priority": p_score,
                },
            )

            return KeywordDetail.model_validate(kw)

    async def get_keyword(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        keyword_id: UUID,
    ) -> KeywordDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            kw = await self._repository.get_by_id(
                session, keyword_id=keyword_id, project_id=project.id
            )
            if not kw:
                raise ResourceNotFound("keyword")
            return KeywordDetail.model_validate(kw)

    async def update_keyword(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        keyword_id: UUID,
        payload: KeywordUpdate,
        request_id: str = "",
    ) -> KeywordDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            kw = await self._repository.get_by_id(
                session, keyword_id=keyword_id, project_id=project.id
            )
            if not kw:
                raise ResourceNotFound("keyword")

            old_keyword = kw.keyword
            if payload.keyword is not None:
                raw_keyword = payload.keyword.strip()
                normalized_keyword = normalize_keyword(raw_keyword)
                if not normalized_keyword:
                    raise DomainError(
                        "INVALID_KEYWORD",
                        "Keyword cannot be empty after normalization.",
                    )
                if normalized_keyword != kw.normalized_keyword:
                    existing = await self._repository.get_by_normalized(
                        session,
                        project_id=project.id,
                        normalized_keyword=normalized_keyword,
                    )
                    if existing and existing.id != kw.id:
                        raise DomainError(
                            "KEYWORD_DUPLICATE",
                            f"Keyword '{raw_keyword}' already exists in this project.",
                        )
                kw.keyword = raw_keyword
                kw.normalized_keyword = normalized_keyword

            if payload.search_volume is not None:
                kw.search_volume = payload.search_volume
            if payload.keyword_difficulty is not None:
                kw.keyword_difficulty = payload.keyword_difficulty
            if payload.cpc is not None:
                kw.cpc = payload.cpc
            if payload.intent is not None:
                kw.intent = str(payload.intent).upper()
                kw.intent_confidence = 1.0
            if payload.funnel_stage is not None:
                kw.funnel_stage = str(payload.funnel_stage).upper()
            if payload.business_value_score is not None:
                kw.business_value_score = payload.business_value_score
            elif (
                payload.keyword is not None or payload.cpc is not None or payload.intent is not None
            ):
                strategy_terms = await self._get_strategy_terms(session, project_id=project.id)
                kw.business_value_score = calculate_business_value(
                    kw.intent,
                    cpc=kw.cpc,
                    keyword=kw.keyword,
                    strategy_terms=strategy_terms,
                )
            if payload.priority_score is not None:
                kw.priority_score = payload.priority_score
            else:
                kw.priority_score = calculate_priority_score(
                    kw.search_volume,
                    kw.keyword_difficulty,
                    kw.business_value_score,
                    kw.intent,
                )
            if payload.status is not None:
                kw.status = str(payload.status).lower()

            kw.revision += 1
            await session.flush()
            # ``updated_at`` is generated by SQLAlchemy's ``onupdate`` expression.
            # A flush expires that attribute, so explicitly reload the row before
            # Pydantic accesses it instead of triggering implicit async I/O.
            await session.refresh(kw)

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="keyword.updated",
                resource_type="keyword",
                resource_id=kw.id,
                request_id=request_id,
                metadata={"old_keyword": old_keyword, "keyword": kw.keyword},
            )
            return KeywordDetail.model_validate(kw)

    async def delete_keyword(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        keyword_id: UUID,
        request_id: str = "",
    ) -> KeywordDeleteResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            keyword = await self._repository.get_by_id(
                session,
                keyword_id=keyword_id,
                project_id=project.id,
            )
            if not keyword:
                raise ResourceNotFound("keyword")

            keyword_text = keyword.keyword
            await self._repository.delete_keyword(
                session,
                keyword_id=keyword.id,
                project_id=project.id,
            )

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="keyword.deleted",
                resource_type="keyword",
                resource_id=keyword.id,
                request_id=request_id,
                metadata={"keyword": keyword_text},
            )

            return KeywordDeleteResponse(
                keyword_id=keyword.id,
                keyword=keyword_text,
                message="Keyword deleted with its dependent assignments and mappings.",
            )

    async def list_keywords(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
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
    ) -> KeywordList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            kws, total_count = await self._repository.list_keywords(
                session,
                project_id=project.id,
                search=search,
                intent=intent,
                status=status,
                min_volume=min_volume,
                max_volume=max_volume,
                min_difficulty=min_difficulty,
                max_difficulty=max_difficulty,
                limit=limit,
                offset=offset,
            )
            return KeywordList(
                items=[KeywordDetail.model_validate(k) for k in kws],
                total_count=total_count,
            )

    async def import_csv(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        file_content: bytes,
        filename: str = "keywords.csv",
        request_id: str = "",
    ) -> KeywordImportResponse:
        parsed_rows = parse_csv_keywords(file_content, filename)
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            import_job = await self._repository.create_import(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                filename=filename,
                source=KeywordSource.CSV,
                created_by_id=actor.user_id,
            )

            strategy_terms = await self._get_strategy_terms(session, project_id=project.id)

            total_rows = len(parsed_rows)
            valid_rows = 0
            invalid_rows = 0
            duplicate_rows = 0
            created_rows = 0
            updated_rows = 0

            for r in parsed_rows:
                raw_kw = r["keyword"]
                norm_kw = normalize_keyword(raw_kw)
                if not norm_kw:
                    invalid_rows += 1
                    await self._repository.add_import_row(
                        session,
                        import_id=import_job.id,
                        row_number=r["row_number"],
                        raw_data=r["raw"],
                        keyword=raw_kw,
                        status="invalid",
                        error_message="Keyword is empty or invalid",
                    )
                    continue

                valid_rows += 1
                existing = await self._repository.get_by_normalized(
                    session, project_id=project.id, normalized_keyword=norm_kw
                )

                if r["intent"] and r["intent"] in SearchIntent.__members__:
                    intent_val = SearchIntent(r["intent"])
                    confidence = 1.0
                    funnel_val = FunnelStage.TOFU
                else:
                    intent_res = classify_intent_and_funnel(raw_kw)
                    intent_val = intent_res.intent
                    confidence = intent_res.confidence
                    funnel_val = intent_res.funnel_stage

                bv_score = calculate_business_value(
                    intent_val,
                    cpc=r["cpc"],
                    keyword=raw_kw,
                    strategy_terms=strategy_terms,
                )
                p_score = calculate_priority_score(
                    search_volume=r["volume"],
                    keyword_difficulty=r["difficulty"],
                    business_value_score=bv_score,
                    intent=intent_val,
                )

                if existing:
                    duplicate_rows += 1
                    updated_rows += 1
                    existing.search_volume = r["volume"] or existing.search_volume
                    existing.keyword_difficulty = r["difficulty"] or existing.keyword_difficulty
                    existing.cpc = r["cpc"] or existing.cpc
                    existing.business_value_score = bv_score
                    existing.priority_score = p_score
                    existing.revision += 1
                    await self._repository.add_import_row(
                        session,
                        import_id=import_job.id,
                        row_number=r["row_number"],
                        raw_data=r["raw"],
                        keyword=raw_kw,
                        status="duplicate",
                        created_keyword_id=existing.id,
                    )
                else:
                    created_rows += 1
                    kw = await self._repository.create_keyword(
                        session,
                        organization_id=project.organization_id,
                        project_id=project.id,
                        website_id=None,
                        keyword=raw_kw,
                        normalized_keyword=norm_kw,
                        search_volume=r["volume"],
                        keyword_difficulty=r["difficulty"],
                        cpc=r["cpc"],
                        intent=str(intent_val),
                        intent_confidence=confidence,
                        funnel_stage=str(funnel_val),
                        business_value_score=bv_score,
                        priority_score=p_score,
                        source=KeywordSource.CSV,
                    )
                    await self._repository.add_import_row(
                        session,
                        import_id=import_job.id,
                        row_number=r["row_number"],
                        raw_data=r["raw"],
                        keyword=raw_kw,
                        status="success",
                        created_keyword_id=kw.id,
                    )

            import_job.total_rows = total_rows
            import_job.valid_rows = valid_rows
            import_job.invalid_rows = invalid_rows
            import_job.duplicate_rows = duplicate_rows
            import_job.created_rows = created_rows
            import_job.updated_rows = updated_rows
            import_job.status = "completed"
            import_job.completed_at = datetime.now(UTC)
            await session.flush()

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="keyword.imported",
                resource_type="keyword_import",
                resource_id=import_job.id,
                request_id=request_id,
                metadata={
                    "filename": filename,
                    "created": created_rows,
                    "updated": updated_rows,
                    "total": total_rows,
                },
            )

            return KeywordImportResponse.model_validate(import_job)

    async def get_import(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        import_id: UUID,
    ) -> KeywordImportResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            job = await self._repository.get_import_by_id(
                session, import_id=import_id, project_id=project.id
            )
            if not job:
                raise ResourceNotFound("keyword_import")
            return KeywordImportResponse.model_validate(job)

    # --- Clustering ---

    async def run_clustering(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: ClusteringRunRequest,
        request_id: str = "",
    ) -> ClusteringRunResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )

            run = await self._repository.create_clustering_run(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                status=ClusteringRunStatus.RUNNING,
                algorithm_version="keyword_cluster_v1",
                parameters=payload.model_dump(mode="json"),
                created_by_id=actor.user_id,
            )

            keywords = await self._repository.list_all_active_for_project(
                session, project_id=project.id
            )
            if not keywords:
                run.status = ClusteringRunStatus.COMPLETED
                run.keyword_count = 0
                run.cluster_count = 0
                run.completed_at = datetime.now(UTC)
                await session.flush()
                return ClusteringRunResponse.model_validate(run)

            clustering_inputs = [
                KeywordClusteringInput(
                    id=k.id,
                    keyword=k.keyword,
                    normalized_keyword=k.normalized_keyword,
                    search_volume=k.search_volume,
                    keyword_difficulty=k.keyword_difficulty,
                    cpc=k.cpc,
                    intent=k.intent,
                    priority_score=k.priority_score,
                    business_value_score=k.business_value_score,
                )
                for k in keywords
            ]

            cluster_candidates = cluster_keywords(
                clustering_inputs,
                similarity_threshold=payload.similarity_threshold,
            )

            for cand in cluster_candidates:
                cluster = await self._repository.create_cluster(
                    session,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    topic_id=None,
                    clustering_run_id=run.id,
                    cluster_name=cand.cluster_name,
                    primary_keyword_id=cand.primary_keyword_id,
                    intent=cand.intent,
                    cluster_score=cand.cluster_score,
                    status=ClusterStatus.PROPOSED,
                    rationale=cand.rationale,
                )

                for kw_id in cand.member_keyword_ids:
                    is_primary = kw_id == cand.primary_keyword_id
                    sim = cand.similarities.get(kw_id, 1.0)
                    await self._repository.add_cluster_member(
                        session,
                        cluster_id=cluster.id,
                        keyword_id=kw_id,
                        is_primary=is_primary,
                        similarity_score=sim,
                    )

            run.status = ClusteringRunStatus.COMPLETED
            run.keyword_count = len(keywords)
            run.cluster_count = len(cluster_candidates)
            run.completed_at = datetime.now(UTC)
            await session.flush()

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="cluster.generated",
                resource_type="clustering_run",
                resource_id=run.id,
                request_id=request_id,
                metadata={
                    "keywords": len(keywords),
                    "clusters": len(cluster_candidates),
                },
            )

            return ClusteringRunResponse.model_validate(run)

    async def list_clusters(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        status: str | None = None,
    ) -> KeywordClusterList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            clusters = await self._repository.list_clusters(
                session, project_id=project.id, status=status
            )
            items: list[KeywordClusterDetail] = []
            for c in clusters:
                memberships = await self._repository.get_cluster_memberships(
                    session, cluster_id=c.id
                )
                primary_kw = None
                members: list[KeywordClusterMemberDetail] = []
                for m, kw in memberships:
                    if m.is_primary:
                        primary_kw = kw.keyword
                    members.append(
                        KeywordClusterMemberDetail(
                            id=m.id,
                            keyword_id=kw.id,
                            keyword=kw.keyword,
                            search_volume=kw.search_volume,
                            keyword_difficulty=kw.keyword_difficulty,
                            cpc=kw.cpc,
                            intent=kw.intent,
                            priority_score=kw.priority_score,
                            business_value_score=kw.business_value_score,
                            is_primary=m.is_primary,
                            similarity_score=m.similarity_score,
                        )
                    )
                items.append(
                    KeywordClusterDetail(
                        id=c.id,
                        organization_id=c.organization_id,
                        project_id=c.project_id,
                        topic_id=c.topic_id,
                        clustering_run_id=c.clustering_run_id,
                        cluster_name=c.cluster_name,
                        primary_keyword_id=c.primary_keyword_id,
                        primary_keyword=primary_kw,
                        intent=c.intent,
                        cluster_score=c.cluster_score,
                        status=c.status,
                        rationale=c.rationale,
                        member_count=len(members),
                        members=members,
                        created_at=c.created_at,
                        updated_at=c.updated_at,
                    )
                )
            return KeywordClusterList(items=items)

    async def get_cluster(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        cluster_id: UUID,
    ) -> KeywordClusterDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            c = await self._repository.get_cluster_by_id(
                session, cluster_id=cluster_id, project_id=project.id
            )
            if not c:
                raise ResourceNotFound("keyword_cluster")

            memberships = await self._repository.get_cluster_memberships(session, cluster_id=c.id)
            primary_kw = None
            members: list[KeywordClusterMemberDetail] = []
            for m, kw in memberships:
                if m.is_primary:
                    primary_kw = kw.keyword
                members.append(
                    KeywordClusterMemberDetail(
                        id=m.id,
                        keyword_id=kw.id,
                        keyword=kw.keyword,
                        search_volume=kw.search_volume,
                        keyword_difficulty=kw.keyword_difficulty,
                        cpc=kw.cpc,
                        intent=kw.intent,
                        priority_score=kw.priority_score,
                        business_value_score=kw.business_value_score,
                        is_primary=m.is_primary,
                        similarity_score=m.similarity_score,
                    )
                )
            return KeywordClusterDetail(
                id=c.id,
                organization_id=c.organization_id,
                project_id=c.project_id,
                topic_id=c.topic_id,
                clustering_run_id=c.clustering_run_id,
                cluster_name=c.cluster_name,
                primary_keyword_id=c.primary_keyword_id,
                primary_keyword=primary_kw,
                intent=c.intent,
                cluster_score=c.cluster_score,
                status=c.status,
                rationale=c.rationale,
                member_count=len(members),
                members=members,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )

    async def update_cluster(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        cluster_id: UUID,
        payload: ClusterUpdateRequest,
        request_id: str = "",
    ) -> KeywordClusterDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            c = await self._repository.get_cluster_by_id(
                session, cluster_id=cluster_id, project_id=project.id
            )
            if not c:
                raise ResourceNotFound("keyword_cluster")

            if payload.cluster_name is not None:
                c.cluster_name = payload.cluster_name.strip()
            if payload.primary_keyword_id is not None:
                c.primary_keyword_id = payload.primary_keyword_id
                memberships = await self._repository.get_cluster_memberships(
                    session, cluster_id=c.id
                )
                for m, kw in memberships:
                    m.is_primary = kw.id == payload.primary_keyword_id
            if payload.topic_id is not None:
                c.topic_id = payload.topic_id
            if payload.status is not None:
                c.status = str(payload.status).lower()
            if payload.rationale is not None:
                c.rationale = payload.rationale

            c.revision += 1
            await session.flush()

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="cluster.updated",
                resource_type="keyword_cluster",
                resource_id=c.id,
                request_id=request_id,
            )

            return await self.get_cluster(
                session,
                actor=actor,
                project_id=project_id,
                cluster_id=cluster_id,
            )

    async def delete_cluster(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        cluster_id: UUID,
        request_id: str = "",
    ) -> KeywordClusterDeleteResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            cluster = await self._repository.get_cluster_by_id(
                session,
                cluster_id=cluster_id,
                project_id=project.id,
            )
            if not cluster:
                raise ResourceNotFound("keyword_cluster")

            cluster_name = cluster.cluster_name
            await self._repository.delete_cluster(
                session,
                cluster_id=cluster.id,
                project_id=project.id,
            )

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="cluster.deleted",
                resource_type="keyword_cluster",
                resource_id=cluster.id,
                request_id=request_id,
                metadata={"cluster_name": cluster_name},
            )

            return KeywordClusterDeleteResponse(
                cluster_id=cluster.id,
                cluster_name=cluster_name,
                message="Cluster deleted. Its underlying keywords were retained.",
            )

    async def merge_clusters(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: ClusterMergeRequest,
        request_id: str = "",
    ) -> KeywordClusterDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            clusters: list[KeywordCluster] = []
            for cid in payload.source_cluster_ids:
                c = await self._repository.get_cluster_by_id(
                    session, cluster_id=cid, project_id=project.id
                )
                if not c:
                    raise ResourceNotFound(f"keyword_cluster {cid}")
                clusters.append(c)

            all_members: list[tuple[UUID, float]] = []
            for c in clusters:
                memberships = await self._repository.get_cluster_memberships(
                    session, cluster_id=c.id
                )
                for m, kw in memberships:
                    all_members.append((kw.id, m.similarity_score))

            cluster_names = ", ".join(c.cluster_name for c in clusters)
            merged = await self._repository.create_cluster(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                topic_id=clusters[0].topic_id,
                cluster_name=payload.target_cluster_name.strip(),
                primary_keyword_id=payload.primary_keyword_id or clusters[0].primary_keyword_id,
                intent=clusters[0].intent,
                cluster_score=sum(c.cluster_score for c in clusters) / len(clusters),
                status=ClusterStatus.APPROVED,
                rationale=f"Manually merged from {len(clusters)} clusters ({cluster_names})",
            )

            seen_kws = set()
            for kw_id, sim in all_members:
                if kw_id in seen_kws:
                    continue
                seen_kws.add(kw_id)
                await self._repository.add_cluster_member(
                    session,
                    cluster_id=merged.id,
                    keyword_id=kw_id,
                    is_primary=(kw_id == merged.primary_keyword_id),
                    similarity_score=sim,
                )

            for c in clusters:
                await self._repository.delete_cluster(
                    session,
                    cluster_id=c.id,
                    project_id=project.id,
                )

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="cluster.merged",
                resource_type="keyword_cluster",
                resource_id=merged.id,
                request_id=request_id,
            )

            return await self.get_cluster(
                session,
                actor=actor,
                project_id=project_id,
                cluster_id=merged.id,
            )

    async def move_keywords(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: MoveKeywordsRequest,
        request_id: str = "",
    ) -> KeywordClusterDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            target = await self._repository.get_cluster_by_id(
                session, cluster_id=payload.target_cluster_id, project_id=project.id
            )
            if not target:
                raise ResourceNotFound("keyword_cluster")

            await self._repository.delete_cluster_members_for_keywords(
                session, keyword_ids=payload.keyword_ids
            )

            for kw_id in payload.keyword_ids:
                await self._repository.add_cluster_member(
                    session,
                    cluster_id=target.id,
                    keyword_id=kw_id,
                    is_primary=False,
                    similarity_score=1.0,
                )

            target.revision += 1
            await session.flush()

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="cluster.keywords_moved",
                resource_type="keyword_cluster",
                resource_id=target.id,
                request_id=request_id,
                metadata={"count": len(payload.keyword_ids)},
            )

            return await self.get_cluster(
                session,
                actor=actor,
                project_id=project_id,
                cluster_id=target.id,
            )
