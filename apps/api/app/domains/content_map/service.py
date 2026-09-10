"""Content Map domain application service for graph projections, layout,
validation, and versioning."""

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from app.db.session import set_actor_context
from app.domains.audit.repository import AuditWriter
from app.domains.content.models import (
    PageContentType,
    PageType,
    PlannedContentPage,
    PlannedPageStatus,
)
from app.domains.content.repository import ContentRepository
from app.domains.content_map.models import (
    ContentArchitectureVersion,
    ContentMapNodeType,
)
from app.domains.content_map.repository import ContentMapRepository
from app.domains.content_map.schemas import (
    ContentArchitectureVersionCreate,
    ContentArchitectureVersionDetail,
    ContentArchitectureVersionList,
    ContentMapEdgeDTO,
    ContentMapGraphResponse,
    ContentMapLayoutUpdate,
    ContentMapNodeData,
    ContentMapNodeDTO,
    ContentMapStats,
    ContentMapValidationResponse,
    ValidationIssue,
)
from app.domains.internal_linking.repository import InternalLinkingRepository
from app.domains.keywords.repository import KeywordRepository
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class ContentMapService:
    def __init__(self) -> None:
        self._content = ContentRepository()
        self._keywords = KeywordRepository()
        self._linking = InternalLinkingRepository()
        self._content_map = ContentMapRepository()
        self._projects = ProjectService()
        self._audit = AuditWriter()

    async def get_content_map(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        node_types: list[str] | None = None,
        statuses: list[str] | None = None,
        search: str | None = None,
        view_mode: str = "combined",  # "planned", "actual", "combined"
    ) -> ContentMapGraphResponse:
        """Projects the IA graph (Pillars -> Topics -> Clusters -> Pages) and relationships."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            # Retrieve domain models
            pillars = await self._content.list_pillars(session, project_id=project.id)
            topics = await self._content.list_topics(session, project_id=project.id)
            clusters = await self._keywords.list_clusters(session, project_id=project.id)
            planned_pages = await self._content.list_planned_pages(session, project_id=project.id)
            relationships = await self._linking.list_relationships(session, project_id=project.id)
            saved_nodes = await self._content_map.list_nodes(session, project_id=project.id)

            saved_pos_map: dict[str, dict[str, float]] = {
                f"{n.node_type.lower()}-{n.entity_id}": {"x": n.position_x, "y": n.position_y}
                for n in saved_nodes
            }

            # Pre-calculate inbound and outbound links for pages
            inbound_links_counts: dict[UUID, int] = defaultdict(int)
            outbound_links_counts: dict[UUID, int] = defaultdict(int)
            for rel in relationships:
                outbound_links_counts[rel.source_page_id] += 1
                inbound_links_counts[rel.target_page_id] += 1

            # Detect cannibalization collisions
            primary_kw_counts: dict[str, list[PlannedContentPage]] = defaultdict(list)
            for pg in planned_pages:
                if pg.primary_keyword:
                    norm = pg.primary_keyword.strip().lower()
                    primary_kw_counts[norm].append(pg)

            cannibalized_page_ids = set()
            for _norm_kw, pgs in primary_kw_counts.items():
                if len(pgs) > 1:
                    for p in pgs:
                        cannibalized_page_ids.add(p.id)

            nodes: list[ContentMapNodeDTO] = []
            edges: list[ContentMapEdgeDTO] = []

            # 1. Pillar Nodes
            for p in pillars:
                node_id = f"pillar-{p.id}"
                pos = saved_pos_map.get(node_id)
                nodes.append(
                    ContentMapNodeDTO(
                        id=node_id,
                        type="pillar",
                        position=pos,
                        data=ContentMapNodeData(
                            label=p.name,
                            title=p.name,
                            subtitle=p.business_goal or "Strategic Pillar",
                            status=p.status,
                            entity_id=p.id,
                            node_type="pillar",
                            priority=p.priority,
                            pillar_id=p.id,
                            metrics={"priority": p.priority},
                        ),
                    )
                )

            # 2. Topic Nodes
            for t in topics:
                node_id = f"topic-{t.id}"
                pos = saved_pos_map.get(node_id)
                nodes.append(
                    ContentMapNodeDTO(
                        id=node_id,
                        type="topic",
                        position=pos,
                        data=ContentMapNodeData(
                            label=t.name,
                            title=t.name,
                            subtitle=t.slug,
                            status=t.status,
                            entity_id=t.id,
                            node_type="topic",
                            priority=t.priority,
                            topic_id=t.id,
                            pillar_id=t.pillar_id,
                            metrics={"priority": t.priority},
                        ),
                    )
                )
                if t.pillar_id:
                    edges.append(
                        ContentMapEdgeDTO(
                            id=f"edge-pillar-{t.pillar_id}-topic-{t.id}",
                            source=f"pillar-{t.pillar_id}",
                            target=node_id,
                            type="contains",
                            label="contains",
                        )
                    )

            # 3. Cluster Nodes
            for c in clusters:
                node_id = f"cluster-{c.id}"
                pos = saved_pos_map.get(node_id)
                nodes.append(
                    ContentMapNodeDTO(
                        id=node_id,
                        type="cluster",
                        position=pos,
                        data=ContentMapNodeData(
                            label=c.cluster_name,
                            title=c.cluster_name,
                            subtitle=c.intent,
                            status=c.status,
                            entity_id=c.id,
                            node_type="cluster",
                            intent=c.intent,
                            cluster_id=c.id,
                            topic_id=c.topic_id,
                            metrics={"score": c.cluster_score},
                        ),
                    )
                )
                if c.topic_id:
                    edges.append(
                        ContentMapEdgeDTO(
                            id=f"edge-topic-{c.topic_id}-cluster-{c.id}",
                            source=f"topic-{c.topic_id}",
                            target=node_id,
                            type="contains",
                            label="contains",
                        )
                    )

            # 4. Planned Page Nodes
            orphan_count = 0
            for pg in planned_pages:
                node_id = f"page-{pg.id}"
                pos = saved_pos_map.get(node_id)
                flags: list[str] = []

                inbound_count = inbound_links_counts[pg.id]
                outbound_count = outbound_links_counts[pg.id]

                if inbound_count == 0:
                    flags.append("orphan")
                    orphan_count += 1
                if pg.id in cannibalized_page_ids:
                    flags.append("cannibalization")

                nodes.append(
                    ContentMapNodeDTO(
                        id=node_id,
                        type="page",
                        position=pos,
                        data=ContentMapNodeData(
                            label=pg.title,
                            title=pg.title,
                            subtitle=pg.url or f"/{pg.slug}",
                            status=pg.status,
                            entity_id=pg.id,
                            node_type="page",
                            primary_keyword=pg.primary_keyword,
                            intent=pg.intent,
                            priority=pg.priority,
                            business_value=pg.business_value,
                            url=pg.url or f"/{pg.slug}",
                            page_type=pg.page_type,
                            content_type=pg.content_type,
                            cluster_id=pg.cluster_id,
                            topic_id=pg.topic_id,
                            pillar_id=pg.pillar_id,
                            inbound_links_count=inbound_count,
                            outbound_links_count=outbound_count,
                            flags=flags,
                            metrics={
                                "priority": pg.priority,
                                "business_value": pg.business_value,
                                "inbound_links": inbound_count,
                                "outbound_links": outbound_count,
                            },
                        ),
                    )
                )

                # Connect Cluster -> Page
                if pg.cluster_id:
                    edges.append(
                        ContentMapEdgeDTO(
                            id=f"edge-cluster-{pg.cluster_id}-page-{pg.id}",
                            source=f"cluster-{pg.cluster_id}",
                            target=node_id,
                            type="targets",
                            label="targets",
                        )
                    )

            # 5. Page Relationship Edges
            for rel in relationships:
                edges.append(
                    ContentMapEdgeDTO(
                        id=f"edge-rel-{rel.id}",
                        source=f"page-{rel.source_page_id}",
                        target=f"page-{rel.target_page_id}",
                        type=rel.relationship_type.lower(),
                        label=rel.relationship_type.lower(),
                        data={"anchor_text": rel.anchor_text, "priority": rel.priority},
                    )
                )

            # Filtering if requested
            filtered_nodes = nodes
            if node_types:
                allowed_types = {t.lower() for t in node_types}
                filtered_nodes = [n for n in filtered_nodes if n.type.lower() in allowed_types]

            if statuses:
                allowed_statuses = {s.lower() for s in statuses}
                filtered_nodes = [
                    n for n in filtered_nodes if n.data.status.lower() in allowed_statuses
                ]

            if search:
                term = search.strip().lower()
                filtered_nodes = [
                    n
                    for n in filtered_nodes
                    if term in n.data.label.lower()
                    or term in n.data.primary_keyword.lower()
                    or term in n.data.subtitle.lower()
                ]

            filtered_node_ids = {n.id for n in filtered_nodes}
            filtered_edges = [
                e for e in edges if e.source in filtered_node_ids and e.target in filtered_node_ids
            ]

            stats = ContentMapStats(
                total_pillars=len(pillars),
                total_topics=len(topics),
                total_clusters=len(clusters),
                total_pages=len(planned_pages),
                planned_pages=len([p for p in planned_pages if p.page_type == PageType.PLANNED]),
                existing_pages=len([p for p in planned_pages if p.page_type == PageType.EXISTING]),
                orphan_pages=orphan_count,
                cannibalization_warnings=len(cannibalized_page_ids),
            )

            return ContentMapGraphResponse(
                graph_revision=1,
                nodes=filtered_nodes,
                edges=filtered_edges,
                stats=stats,
            )

    async def generate_initial_map(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        request_id: str = "",
    ) -> ContentMapGraphResponse:
        """Generates initial Content Map planned pages from clusters and opportunities."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            clusters = await self._keywords.list_clusters(session, project_id=project.id)
            planned_pages = await self._content.list_planned_pages(session, project_id=project.id)
            mapped_cluster_ids = {p.cluster_id for p in planned_pages if p.cluster_id}

            created_count = 0
            for c in clusters:
                if c.id not in mapped_cluster_ids:
                    # Look up primary keyword name
                    primary_kw = ""
                    if c.primary_keyword_id:
                        kw = await self._keywords.get_keyword_by_id(
                            session, keyword_id=c.primary_keyword_id
                        )
                        if kw:
                            primary_kw = kw.keyword

                    pillar_id = None
                    if c.topic_id:
                        t = await self._content.get_topic_by_id(session, topic_id=c.topic_id)
                        if t:
                            pillar_id = t.pillar_id

                    title = c.cluster_name
                    from app.core.validators import normalize_slug

                    raw_slug = normalize_slug(title)
                    slug = raw_slug
                    existing = await self._content.get_planned_page_by_slug(
                        session, project_id=project.id, slug=slug
                    )
                    if existing:
                        slug = f"{raw_slug}-{str(c.id)[:6]}"

                    page = PlannedContentPage(
                        organization_id=project.organization_id,
                        project_id=project.id,
                        title=title,
                        slug=slug,
                        url=f"/{slug}",
                        page_type=PageType.PLANNED,
                        content_type=PageContentType.GUIDE,
                        status=PlannedPageStatus.PLANNED,
                        intent=c.intent,
                        primary_keyword=primary_kw,
                        primary_keyword_id=c.primary_keyword_id,
                        cluster_id=c.id,
                        topic_id=c.topic_id,
                        pillar_id=pillar_id,
                        priority=5,
                        business_value=50.0,
                    )
                    await self._content.create_planned_page(session, page)
                    created_count += 1

            self._audit.add(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor.user_id,
                action="content_map.initial_generate",
                resource_type="content_map",
                resource_id=project.id,
                outcome="success",
                request_id=request_id,
                metadata={"pages_created": created_count},
            )

        return await self.get_content_map(session, actor=actor, project_id=project_id)

    async def save_layout(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: ContentMapLayoutUpdate,
        request_id: str = "",
    ) -> None:
        """Saves visual node positions without altering semantic database relationships."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            for pos in payload.positions:
                # Node id format: "<type>-<uuid>"
                parts = pos.node_id.split("-", 1)
                if len(parts) == 2:
                    raw_type, raw_uuid = parts
                    node_type_upper = raw_type.upper()
                    if node_type_upper in ContentMapNodeType:
                        try:
                            entity_id = UUID(raw_uuid)
                            await self._content_map.upsert_node_position(
                                session,
                                organization_id=project.organization_id,
                                project_id=project.id,
                                node_type=node_type_upper,
                                entity_id=entity_id,
                                label="",
                                position_x=pos.position_x,
                                position_y=pos.position_y,
                            )
                        except ValueError:
                            continue

    async def validate_architecture(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
    ) -> ContentMapValidationResponse:
        """Evaluates 8 deterministic architecture validation checks."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            pillars = await self._content.list_pillars(session, project_id=project.id)
            topics = await self._content.list_topics(session, project_id=project.id)
            clusters = await self._keywords.list_clusters(session, project_id=project.id)
            planned_pages = await self._content.list_planned_pages(session, project_id=project.id)
            relationships = await self._linking.list_relationships(session, project_id=project.id)

            issues: list[ValidationIssue] = []

            # 1. Cluster without target page
            mapped_cluster_ids = {p.cluster_id for p in planned_pages if p.cluster_id}
            for c in clusters:
                if c.id not in mapped_cluster_ids:
                    issues.append(
                        ValidationIssue(
                            id=f"val-cluster-no-page-{c.id}",
                            severity="warning",
                            issue_type="UNMAPPED_CLUSTER",
                            entity_type="cluster",
                            entity_id=c.id,
                            entity_label=c.cluster_name,
                            reason=f"Cluster '{c.cluster_name}' has no target content page.",
                            recommended_action=(
                                "Create a planned page targeting this cluster or map to existing."
                            ),
                        )
                    )

            # 2. Page without cluster
            for pg in planned_pages:
                if not pg.cluster_id:
                    issues.append(
                        ValidationIssue(
                            id=f"val-page-no-cluster-{pg.id}",
                            severity="warning",
                            issue_type="PAGE_WITHOUT_CLUSTER",
                            entity_type="page",
                            entity_id=pg.id,
                            entity_label=pg.title,
                            reason=f"Page '{pg.title}' does not belong to any keyword cluster.",
                            recommended_action=(
                                "Assign this page to an appropriate keyword cluster."
                            ),
                        )
                    )

            # 3. Page without primary keyword
            for pg in planned_pages:
                if not pg.primary_keyword or not pg.primary_keyword.strip():
                    issues.append(
                        ValidationIssue(
                            id=f"val-page-no-kw-{pg.id}",
                            severity="error",
                            issue_type="PAGE_WITHOUT_PRIMARY_KEYWORD",
                            entity_type="page",
                            entity_id=pg.id,
                            entity_label=pg.title,
                            reason=f"Page '{pg.title}' does not have a primary target keyword.",
                            recommended_action="Define a primary target keyword for this page.",
                        )
                    )

            # 4. Topic without cluster
            topics_with_clusters = {c.topic_id for c in clusters if c.topic_id}
            for t in topics:
                if t.id not in topics_with_clusters:
                    issues.append(
                        ValidationIssue(
                            id=f"val-topic-no-cluster-{t.id}",
                            severity="info",
                            issue_type="TOPIC_WITHOUT_CLUSTER",
                            entity_type="topic",
                            entity_id=t.id,
                            entity_label=t.name,
                            reason=f"Topic '{t.name}' contains no keyword clusters.",
                            recommended_action=(
                                "Run keyword clustering or assign clusters to this topic."
                            ),
                        )
                    )

            # 5. Pillar without topic
            pillars_with_topics = {t.pillar_id for t in topics if t.pillar_id}
            for p in pillars:
                if p.id not in pillars_with_topics:
                    issues.append(
                        ValidationIssue(
                            id=f"val-pillar-no-topic-{p.id}",
                            severity="warning",
                            issue_type="PILLAR_WITHOUT_TOPIC",
                            entity_type="pillar",
                            entity_id=p.id,
                            entity_label=p.name,
                            reason=f"Pillar '{p.name}' contains no sub-topics.",
                            recommended_action="Create topics under this content pillar.",
                        )
                    )

            # 6. Multiple pages targeting same primary keyword (cannibalization)
            kw_page_map: dict[str, list[PlannedContentPage]] = defaultdict(list)
            for pg in planned_pages:
                if pg.primary_keyword:
                    norm = pg.primary_keyword.strip().lower()
                    kw_page_map[norm].append(pg)

            for norm_kw, pgs in kw_page_map.items():
                if len(pgs) > 1:
                    titles = ", ".join(f"'{p.title}'" for p in pgs)
                    for p in pgs:
                        issues.append(
                            ValidationIssue(
                                id=f"val-cannibalization-{p.id}",
                                severity="error",
                                issue_type="KEYWORD_CANNIBALIZATION",
                                entity_type="page",
                                entity_id=p.id,
                                entity_label=p.title,
                                reason=(
                                    f"Primary keyword '{norm_kw}' is targeted by "
                                    f"multiple pages: {titles}."
                                ),
                                recommended_action=(
                                    "Differentiate keywords, merge pages, or change targeting."
                                ),
                            )
                        )

            # 7. Orphan pages (0 inbound internal links)
            inbound_links_counts: dict[UUID, int] = defaultdict(int)
            for rel in relationships:
                inbound_links_counts[rel.target_page_id] += 1

            for pg in planned_pages:
                if inbound_links_counts[pg.id] == 0:
                    issues.append(
                        ValidationIssue(
                            id=f"val-orphan-{pg.id}",
                            severity="warning",
                            issue_type="ORPHAN_PAGE",
                            entity_type="page",
                            entity_id=pg.id,
                            entity_label=pg.title,
                            reason=f"Page '{pg.title}' has no inbound internal link relationships.",
                            recommended_action=(
                                "Create supporting or parent-child link relationships to this page."
                            ),
                        )
                    )

            # 8. Broken relationships
            page_ids = {p.id for p in planned_pages}
            for rel in relationships:
                if rel.source_page_id not in page_ids or rel.target_page_id not in page_ids:
                    issues.append(
                        ValidationIssue(
                            id=f"val-broken-rel-{rel.id}",
                            severity="error",
                            issue_type="BROKEN_RELATIONSHIP",
                            entity_type="relationship",
                            entity_id=rel.id,
                            entity_label=f"{rel.relationship_type} Link",
                            reason="Relationship points to a page that no longer exists.",
                            recommended_action="Remove or reassign this link relationship.",
                        )
                    )

            return ContentMapValidationResponse(
                is_valid=len([i for i in issues if i.severity == "error"]) == 0,
                total_issues=len(issues),
                issues=issues,
            )

    async def create_version(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: ContentArchitectureVersionCreate,
        request_id: str = "",
    ) -> ContentArchitectureVersionDetail:
        """Creates an immutable snapshot version of the project's content architecture."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            latest = await self._content_map.get_latest_version(session, project_id=project.id)
            next_version = (latest.version + 1) if latest else 1

            pillars = await self._content.list_pillars(session, project_id=project.id)
            topics = await self._content.list_topics(session, project_id=project.id)
            clusters = await self._keywords.list_clusters(session, project_id=project.id)
            pages = await self._content.list_planned_pages(session, project_id=project.id)
            relationships = await self._linking.list_relationships(session, project_id=project.id)

            snapshot = {
                "version": next_version,
                "project_id": str(project.id),
                "created_at": datetime.now(UTC).isoformat(),
                "pillars": [{"id": str(p.id), "name": p.name, "slug": p.slug} for p in pillars],
                "topics": [
                    {
                        "id": str(t.id),
                        "name": t.name,
                        "pillar_id": str(t.pillar_id) if t.pillar_id else None,
                    }
                    for t in topics
                ],
                "clusters": [
                    {"id": str(c.id), "name": c.cluster_name, "intent": c.intent} for c in clusters
                ],
                "pages": [
                    {
                        "id": str(pg.id),
                        "title": pg.title,
                        "slug": pg.slug,
                        "primary_keyword": pg.primary_keyword,
                        "cluster_id": str(pg.cluster_id) if pg.cluster_id else None,
                        "status": pg.status,
                    }
                    for pg in pages
                ],
                "relationships": [
                    {
                        "source": str(r.source_page_id),
                        "target": str(r.target_page_id),
                        "type": r.relationship_type,
                    }
                    for r in relationships
                ],
            }

            v_obj = ContentArchitectureVersion(
                organization_id=project.organization_id,
                project_id=project.id,
                version=next_version,
                snapshot_data=snapshot,
                change_summary=payload.change_summary,
                created_by_id=actor.user_id,
            )
            created = await self._content_map.create_version(session, v_obj)

            self._audit.add(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor.user_id,
                action="content_architecture.version_create",
                resource_type="content_architecture_version",
                resource_id=created.id,
                outcome="success",
                request_id=request_id,
                metadata={"version": next_version, "summary": payload.change_summary},
            )

            return ContentArchitectureVersionDetail.model_validate(created)

    async def list_versions(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
    ) -> ContentArchitectureVersionList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            versions = await self._content_map.list_versions(session, project_id=project.id)
            items = [ContentArchitectureVersionDetail.model_validate(v) for v in versions]
            return ContentArchitectureVersionList(items=items)
