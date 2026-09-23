"""Application service for V3 demand review queues."""

from uuid import UUID, uuid4

from app.core.errors import BadRequestError, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.demand.models import DemandNode, DemandNodeStatus
from app.domains.demand.repository import DemandRepository
from app.domains.demand.schemas import (
    BulkActionRequest,
    BulkUpdateResponse,
    DemandImportRequest,
    DemandImportResponse,
    DemandNodeListResponse,
    DemandNodeResponse,
    DemandSummaryCounts,
    PageMetadata,
)
from app.domains.job_runs.models import JobRun, JobRunStatus
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
