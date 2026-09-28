"""Application service for V3 demand review queues."""

from uuid import UUID, uuid4

from app.core.errors import BadRequestError, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.canvas.schemas import WorkspaceConfig
from app.domains.content_cards.models import ContentCard, ContentCardOrigin, ContentCardState
from app.domains.content_cards.repository import ContentCardRepository
from app.domains.demand.models import DemandNode, DemandNodeStatus
from app.domains.demand.planning import Plan, build_plan, card_market, primary_fields
from app.domains.demand.repository import DemandRepository
from app.domains.demand.schemas import (
    BulkActionRequest,
    BulkUpdateResponse,
    DemandCsvMappingResponse,
    DemandImportRequest,
    DemandImportResponse,
    DemandNodeListResponse,
    DemandNodeResponse,
    DemandSummaryCounts,
    PageMetadata,
    PlanCardPreview,
    PlanGroupPreview,
    PlanKindCounts,
    PlanPreviewResponse,
    PlanResultResponse,
    PlanSecondaryDemand,
    PlanSkippedNode,
)
from app.domains.job_runs.models import JobRun, JobRunStatus
from app.domains.projects.models import Project
from app.domains.projects.repository import ProjectRepository
from app.security.authorization import AuthorizationService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class DemandService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = DemandRepository(session)
        self._session = session
        from app.domains.auth.repository import AuthorizationRepository

        self._authorization = AuthorizationService(AuthorizationRepository())

    async def _require_scoped_destination(
        self,
        organization_id: UUID,
        project_id: UUID,
        *,
        area_id: UUID | None = None,
        argument_id: UUID | None = None,
    ) -> None:
        if area_id is not None:
            area = await self.repository.get_area_by_id(organization_id, project_id, area_id)
            if area is None:
                raise ResourceNotFound("area")
        if argument_id is not None:
            argument = await self.repository.get_argument_by_id(
                organization_id, project_id, argument_id
            )
            if argument is None:
                raise ResourceNotFound("argument")

    async def _resolve_import_area(
        self,
        organization_id: UUID,
        project_id: UUID,
        area_reference: str | None,
    ) -> UUID | None:
        if area_reference is None or not area_reference.strip():
            return None

        reference = area_reference.strip()
        try:
            area_id = UUID(reference)
        except ValueError:
            matches = await self.repository.get_areas_by_name(
                organization_id, project_id, reference
            )
            if len(matches) == 1:
                return matches[0].id
            if not matches:
                raise BadRequestError(
                    f"CSV area '{reference}' does not exist in this project.", field="area"
                ) from None
            raise BadRequestError(
                f"CSV area '{reference}' is ambiguous in this project; use its UUID instead.",
                field="area",
            ) from None

        area = await self.repository.get_area_by_id(organization_id, project_id, area_id)
        if area is None:
            raise BadRequestError("CSV area does not exist in this project.", field="area")
        return area.id

    async def list_nodes(
        self,
        organization_id: UUID,
        project_id: UUID,
        *,
        status: str | None,
        origin: str | None = None,
        area_id: UUID | None = None,
        argument_id: UUID | None = None,
        node_type: str | None = None,
        funnel: str | None = None,
        page: int,
        page_size: int,
        actor: AuthenticatedUser,
    ) -> DemandNodeListResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            nodes = await self.repository.get_demand_nodes(
                organization_id,
                project_id,
                status=status,
                origin=origin,
                area_id=area_id,
                argument_id=argument_id,
                node_type=node_type,
                funnel=funnel,
                page=page,
                page_size=page_size,
            )
            total, discarded, kept, gsc = await self.repository.get_summary(
                organization_id, project_id
            )
        return DemandNodeListResponse(
            items=[DemandNodeResponse.model_validate(node) for node in nodes],
            summary=DemandSummaryCounts(
                total_discarded=discarded,
                below_065_confidence=0,
                total_kept=kept,
                gsc_striking_distance_count=gsc,
            ),
            meta=PageMetadata(total_count=total, page=page, page_size=page_size),
        )

    async def bulk_set_pending_classify(
        self,
        organization_id: UUID,
        project_id: UUID,
        node_ids: list[UUID],
        actor: AuthenticatedUser,
    ) -> BulkUpdateResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            updated = await self.repository.bulk_update_status(
                organization_id, project_id, node_ids, DemandNodeStatus.PENDING_CLASSIFY
            )
            job_run = self._job_run(
                organization_id,
                project_id,
                actor.user_id,
                "demand_pending_classify",
                node_ids,
            )
            self.repository.add_job_run(job_run)
            await self._session.flush()
        return BulkUpdateResponse(updated_count=updated, job_run_id=job_run.id)

    async def import_nodes(
        self,
        organization_id: UUID,
        project_id: UUID,
        payload: DemandImportRequest,
        actor: AuthenticatedUser,
    ) -> DemandImportResponse:
        created_count = 0
        existing_count = 0
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            for item in payload.items:
                area_id = await self._resolve_import_area(organization_id, project_id, item.area)
                existing = await self.repository.get_by_identity(
                    organization_id,
                    project_id,
                    node_type=item.type,
                    text=item.text.strip(),
                    country=item.country,
                )
                if existing is not None:
                    existing_count += 1
                    continue
                self.repository.add_node(
                    DemandNode(
                        id=uuid4(),
                        organization_id=organization_id,
                        project_id=project_id,
                        type=item.type,
                        text=item.text.strip(),
                        volume=item.volume,
                        country=item.country,
                        area_id=area_id,
                        funnel=item.funnel,
                        origin=item.origin,
                        status=item.status,
                        score=item.score,
                        confidence=item.confidence,
                        competitor_names=[item.competitor] if item.competitor else [],
                    )
                )
                created_count += 1
            if payload.column_mapping is not None:
                await self._save_csv_mapping(
                    organization_id, project_id, payload.column_mapping, actor
                )
            job_run = JobRun(
                id=uuid4(),
                organization_id=organization_id,
                project_id=project_id,
                job_type="demand_csv_import",
                prompt_version="v3.demand-csv-import.v1",
                model="deterministic",
                provider="internal",
                status=JobRunStatus.COMPLETED,
                triggered_by=str(actor.user_id),
                entity_type="project",
                entity_id=project_id,
                input_data={"row_count": len(payload.items)},
                output_data={
                    "created_count": created_count,
                    "existing_count": existing_count,
                },
            )
            self.repository.add_job_run(job_run)
            await self._session.flush()
        return DemandImportResponse(
            created_count=created_count,
            existing_count=existing_count,
            job_run_id=job_run.id,
        )

    async def bulk_reassign_area(
        self,
        organization_id: UUID,
        project_id: UUID,
        node_ids: list[UUID],
        area_id: UUID,
        actor: AuthenticatedUser,
    ) -> BulkUpdateResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            await self._require_scoped_destination(organization_id, project_id, area_id=area_id)
            updated = await self.repository.bulk_reassign_area(
                organization_id, project_id, node_ids, area_id
            )
            job_run = self._job_run(
                organization_id,
                project_id,
                actor.user_id,
                "demand_reassign_area",
                node_ids,
                area_id=area_id,
            )
            self.repository.add_job_run(job_run)
            await self._session.flush()
        return BulkUpdateResponse(updated_count=updated, job_run_id=job_run.id)

    async def bulk_action(
        self,
        organization_id: UUID,
        project_id: UUID,
        payload: BulkActionRequest,
        actor: AuthenticatedUser,
    ) -> BulkUpdateResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_WRITE,
            )
            if payload.action == "keep":
                updated = await self.repository.bulk_update_status(
                    organization_id, project_id, payload.ids, DemandNodeStatus.KEPT
                )
            elif payload.action == "discard":
                updated = await self.repository.bulk_update_status(
                    organization_id, project_id, payload.ids, DemandNodeStatus.DISCARDED
                )
            elif payload.action == "reassign_area" and payload.area_id is not None:
                await self._require_scoped_destination(
                    organization_id, project_id, area_id=payload.area_id
                )
                updated = await self.repository.bulk_reassign_area(
                    organization_id, project_id, payload.ids, payload.area_id
                )
            elif payload.action == "set_argument" and payload.argument_id is not None:
                await self._require_scoped_destination(
                    organization_id, project_id, argument_id=payload.argument_id
                )
                updated = await self.repository.bulk_set_argument(
                    organization_id, project_id, payload.ids, payload.argument_id
                )
            else:
                from app.core.errors import BadRequestError

                raise BadRequestError("A destination ID is required for this bulk action.")
            job_run = self._job_run(
                organization_id,
                project_id,
                actor.user_id,
                f"demand_{payload.action}",
                payload.ids,
                area_id=payload.area_id,
            )
            self.repository.add_job_run(job_run)
            await self._session.flush()
        return BulkUpdateResponse(updated_count=updated, job_run_id=job_run.id)

    # ── Plan (V3 §4.5) ───────────────────────────────────────────────

    async def preview_plan(
        self,
        organization_id: UUID,
        project_id: UUID,
        node_ids: list[UUID],
        actor: AuthenticatedUser,
    ) -> PlanPreviewResponse:
        """Show what Plan would create. Reads only; writes nothing."""
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            plan, _config = await self._build_plan(organization_id, project_id, node_ids, actor)
            area_names = await self._area_names(organization_id, project_id, plan)
        return self._preview(plan, area_names)

    async def confirm_plan(
        self,
        organization_id: UUID,
        project_id: UUID,
        node_ids: list[UUID],
        actor: AuthenticatedUser,
    ) -> PlanResultResponse:
        """Create the planned cards and one action-level JobRun in one transaction.

        The plan is rebuilt from current rows rather than trusted from the client,
        so a node carded since the preview is skipped, never duplicated. Any
        failure rolls the whole transaction back: zero cards, no JobRun.
        """
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            for permission in (PermissionCode.KEYWORD_WRITE, PermissionCode.CONTENT_WRITE):
                await self._authorization.require_project(
                    self._session,
                    user_id=actor.user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    permission=permission,
                )
            plan, config = await self._build_plan(organization_id, project_id, node_ids, actor)
            area_names = await self._area_names(organization_id, project_id, plan)

            cards = ContentCardRepository(self._session)
            created: list[UUID] = []
            for group in plan.groups:
                for planned in group.cards:
                    card = ContentCard(
                        id=uuid4(),
                        organization_id=organization_id,
                        project_id=project_id,
                        kind=planned.kind,
                        area_id=group.area_id,
                        argument_id=planned.node.argument_id,
                        market=card_market(group.country, config),
                        secondary_demand_ids=[str(node.id) for node in planned.secondary_nodes],
                        state=ContentCardState.PLANNED,
                        origin=ContentCardOrigin.PLAN,
                        title=planned.node.text,
                        word_budget=planned.word_budget,
                        **primary_fields(planned.node),
                    )
                    cards.add_content_card(card)
                    created.append(card.id)

            preview = self._preview(plan, area_names)
            job_run = JobRun(
                id=uuid4(),
                organization_id=organization_id,
                project_id=project_id,
                job_type="demand_plan",
                prompt_version="v3.demand_plan.v1",
                model="deterministic",
                provider="internal",
                status=JobRunStatus.COMPLETED,
                triggered_by="ui",
                entity_type="project",
                entity_id=project_id,
                input_data={
                    "node_ids": [str(node_id) for node_id in node_ids],
                    "actor_user_id": str(actor.user_id),
                },
                output_data={
                    "created_card_ids": [str(card_id) for card_id in created],
                    "skipped_count": preview.skipped_count,
                    **preview.totals.model_dump(),
                },
            )
            cards.add_job_run(job_run)
            await self._session.flush()
        return PlanResultResponse(
            **preview.model_dump(),
            created_count=len(created),
            created_card_ids=created,
            job_run_id=job_run.id,
        )

    async def get_csv_mapping(
        self, organization_id: UUID, project_id: UUID, actor: AuthenticatedUser
    ) -> DemandCsvMappingResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.KEYWORD_READ,
            )
            project = await self._project(organization_id, project_id, actor)
            config = WorkspaceConfig.model_validate(project.workspace_config or {})
        return DemandCsvMappingResponse(column_mapping=config.demand_csv_mapping)

    async def _project(
        self, organization_id: UUID, project_id: UUID, actor: AuthenticatedUser
    ) -> Project:
        project = await ProjectRepository().get_for_organization_member(
            self._session, user_id=actor.user_id, project_id=project_id
        )
        if project is None or project.organization_id != organization_id:
            raise ResourceNotFound("project")
        return project

    async def _save_csv_mapping(
        self,
        organization_id: UUID,
        project_id: UUID,
        mapping: dict[str, str],
        actor: AuthenticatedUser,
    ) -> None:
        project = await self._project(organization_id, project_id, actor)
        # A new dict so SQLAlchemy sees the JSONB change.
        project.workspace_config = {
            **(project.workspace_config or {}),
            "demand_csv_mapping": mapping,
        }

    async def _build_plan(
        self,
        organization_id: UUID,
        project_id: UUID,
        node_ids: list[UUID],
        actor: AuthenticatedUser,
    ) -> tuple[Plan, WorkspaceConfig]:
        project = await ProjectRepository().get_for_organization_member(
            self._session, user_id=actor.user_id, project_id=project_id
        )
        if project is None or project.organization_id != organization_id:
            raise ResourceNotFound("project")
        config = WorkspaceConfig.model_validate(project.workspace_config or {})
        nodes = await self.repository.get_nodes_by_ids(organization_id, project_id, node_ids)
        carded = await ContentCardRepository(self._session).get_carded_demand_ids(
            organization_id, project_id, node_ids
        )
        return build_plan(node_ids, nodes, carded, config), config

    async def _area_names(
        self, organization_id: UUID, project_id: UUID, plan: Plan
    ) -> dict[UUID, str]:
        area_ids = [group.area_id for group in plan.groups]
        if not area_ids:
            return {}
        areas = await self.repository.get_areas_by_ids(organization_id, project_id, area_ids)
        return {area.id: area.name for area in areas}

    @staticmethod
    def _preview(plan: Plan, area_names: dict[UUID, str]) -> PlanPreviewResponse:
        totals = PlanKindCounts()
        groups: list[PlanGroupPreview] = []
        for group in plan.groups:
            counts = PlanKindCounts()
            cards: list[PlanCardPreview] = []
            for planned in group.cards:
                setattr(counts, planned.kind, getattr(counts, planned.kind) + 1)
                counts.secondary_demands += len(planned.secondary_nodes)
                cards.append(
                    PlanCardPreview(
                        kind=planned.kind,
                        primary_node_id=planned.node.id,
                        primary_text=planned.node.text,
                        primary_type=planned.node.type,
                        score=planned.node.score,
                        volume=planned.node.volume,
                        word_budget=planned.word_budget,
                        secondary_demands=[
                            PlanSecondaryDemand(node_id=node.id, text=node.text)
                            for node in planned.secondary_nodes
                        ],
                    )
                )
            for name in ("pillar", "cluster", "compare", "refresh", "secondary_demands"):
                setattr(totals, name, getattr(totals, name) + getattr(counts, name))
            groups.append(
                PlanGroupPreview(
                    area_id=group.area_id,
                    area_name=area_names.get(group.area_id, ""),
                    market_country=group.country,
                    counts=counts,
                    cards=cards,
                )
            )
        return PlanPreviewResponse(
            selected_count=plan.selected_count,
            eligible_count=plan.eligible_count,
            skipped_count=len(plan.skipped),
            totals=totals,
            groups=groups,
            skipped=[
                PlanSkippedNode(
                    node_id=skip.node_id,
                    text=skip.node.text if skip.node else None,
                    reason=skip.reason,
                )
                for skip in plan.skipped
            ],
            deferred=list(plan.deferred),
        )

    @staticmethod
    def _job_run(
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
        job_type: str,
        node_ids: list[UUID],
        *,
        area_id: UUID | None = None,
    ) -> JobRun:
        input_data: dict[str, object] = {"node_ids": [str(node_id) for node_id in node_ids]}
        if area_id is not None:
            input_data["area_id"] = str(area_id)
        return JobRun(
            id=uuid4(),
            organization_id=organization_id,
            project_id=project_id,
            job_type=job_type,
            prompt_version=f"v3.{job_type}.v1",
            model="deterministic",
            provider="internal",
            status=JobRunStatus.COMPLETED,
            triggered_by=str(user_id),
            entity_type="demand_node",
            input_data=input_data,
            output_data={"updated_count": len(node_ids)},
        )
