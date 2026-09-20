"""Application service for V3 Canvas reads and immutable claim edits."""

from uuid import UUID, uuid4

from app.core.errors import ConflictError, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.canvas.models import Claim
from app.domains.canvas.repository import CanvasRepository
from app.domains.canvas.schemas import (
    ArgumentResponse,
    CanvasAnchor,
    CanvasFullResponse,
    CanvasListItem,
    CanvasListResponse,
    ClaimEditCheckResponse,
    ClaimEditConfirmResponse,
    ClaimResponse,
    ContentCardStub,
    DemandNodeStub,
    DrilldownResponse,
)
from app.domains.job_runs.models import JobRun, JobRunStatus
from app.security.authorization import AuthorizationService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class CanvasService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = CanvasRepository(session)
        self._session = session
        from app.domains.auth.repository import AuthorizationRepository
        self._authorization = AuthorizationService(AuthorizationRepository())

    @staticmethod
    def _claim_response(claim: Claim) -> ClaimResponse:
        return ClaimResponse.model_validate(claim).model_copy(
            update={
                "clm_number": f"CLM-{str(claim.id).split('-')[0].upper()}",
                "inherited": False,
            }
        )

    async def list_canvases(
        self, organization_id: UUID, project_id: UUID, *, actor: AuthenticatedUser
    ) -> CanvasListResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            canvases = await self.repository.get_canvases_for_project(organization_id, project_id)
            counts = await self.repository.get_argument_counts(organization_id, project_id)
        items = [
            CanvasListItem(
                id=canvas.id,
                product_line=canvas.product_line,
                name=canvas.product_line or "Company canvas",
                argument_count=counts.get(canvas.id, 0),
            )
            for canvas in canvases
        ]
        return CanvasListResponse(
            company_canvas=next((item for item in items if item.product_line is None), None),
            product_lines=[item for item in items if item.product_line is not None],
        )

    async def get_canvas(
        self, organization_id: UUID, project_id: UUID, canvas_id: UUID, *, actor: AuthenticatedUser
    ) -> CanvasFullResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            canvas = await self.repository.get_canvas_by_id(organization_id, project_id, canvas_id)
        if canvas is None:
            raise ResourceNotFound("canvas")
        arguments = await self.repository.get_arguments_for_canvas(
            organization_id, project_id, canvas_id
        )
        claims = await self.repository.get_claims_for_canvas(organization_id, project_id, canvas_id)
        claims_by_argument: dict[UUID, list[ClaimResponse]] = {}
        pitch_claim: ClaimResponse | None = None
        for claim in claims:
            response = self._claim_response(claim)
            if claim.row == "pitch":
                pitch_claim = response
            if claim.argument_id is not None:
                claims_by_argument.setdefault(claim.argument_id, []).append(response)
        anchors = [
            CanvasAnchor.model_validate(anchor)
            for anchor in (
                canvas.company_anchor,
                canvas.persona_anchor,
                canvas.use_case_anchor,
                canvas.alternative_anchor,
                canvas.category_anchor,
            )
            if anchor
        ]
        return CanvasFullResponse(
            id=canvas.id,
            product_line=canvas.product_line,
            name=canvas.product_line or "Company canvas",
            anchors=anchors,
            problem_summary=canvas.problem_summary,
            differentiation_summary=canvas.differentiation_summary,
            version=canvas.version,
            arguments=[
                ArgumentResponse(
                    id=argument.id,
                    order=argument.order,
                    sub_problem=argument.sub_problem,
                    differentiation_pillar=argument.differentiation_pillar,
                    capability=argument.capability,
                    features=argument.features,
                    benefit=argument.benefit,
                    claims=claims_by_argument.get(argument.id, []),
                    inherited=argument.inherited_from is not None,
                    override=argument.override,
                )
                for argument in arguments
            ],
            pitch_claim=pitch_claim,
        )

    async def check_claim_edit(
        self, organization_id: UUID, project_id: UUID, claim_id: UUID, *, actor: AuthenticatedUser
    ) -> ClaimEditCheckResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_WRITE,
            )
            claim = await self.repository.get_claim_by_id(organization_id, project_id, claim_id)
        if claim is None:
            raise ResourceNotFound("claim")
        citation_count = await self.repository.get_citation_count(
            organization_id, project_id, claim_id
        )
        return ClaimEditCheckResponse(
            citation_count=citation_count,
            claim_text=claim.text,
            claim_id=claim.id,
        )

    async def confirm_claim_edit(
        self,
        organization_id: UUID,
        project_id: UUID,
        claim_id: UUID,
        text: str,
        evidence: str,
        actor: AuthenticatedUser,
    ) -> ClaimEditConfirmResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_WRITE,
            )
            old_claim = await self.repository.get_claim_by_id(organization_id, project_id, claim_id)
            if old_claim is None:
                raise ResourceNotFound("claim")
            if old_claim.superseded_by is not None:
                raise ConflictError(
                    "CLAIM_ALREADY_SUPERSEDED",
                    "This claim already has a newer version.",
                )
            new_claim = Claim(
                id=uuid4(),
                organization_id=old_claim.organization_id,
                project_id=old_claim.project_id,
                canvas_id=old_claim.canvas_id,
                argument_id=old_claim.argument_id,
                row=old_claim.row,
                text=text,
                evidence=evidence,
                approved=False,
                version=old_claim.version + 1,
                market_overrides=old_claim.market_overrides,
            )
            self.repository.add(new_claim)
            await self._session.flush()
            old_claim.superseded_by = new_claim.id
            job_run = JobRun(
                id=uuid4(),
                organization_id=organization_id,
                project_id=project_id,
                job_type="stale_claim_scan",
                prompt_version="v3.stale-claim-scan.v1",
                model="deterministic",
                provider="internal",
                status=JobRunStatus.PENDING,
                triggered_by=str(actor.user_id),
                entity_type="claim",
                entity_id=new_claim.id,
                input_data={"old_claim_id": str(old_claim.id)},
            )
            self.repository.add(job_run)
            await self._session.flush()
        return ClaimEditConfirmResponse(
            old_claim_id=old_claim.id,
            new_claim_id=new_claim.id,
            new_version=new_claim.version,
            job_run_id=job_run.id,
        )

    async def get_claim_drilldown(
        self, organization_id: UUID, project_id: UUID, claim_id: UUID, *, actor: AuthenticatedUser
    ) -> DrilldownResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            claim = await self.repository.get_claim_by_id(organization_id, project_id, claim_id)
        if claim is None:
            raise ResourceNotFound("claim")
        chain = await self.repository.get_argument_chain(organization_id, project_id, claim_id)
        demand = await self.repository.get_demand_for_claim(organization_id, project_id, claim_id)
        cards = await self.repository.get_cards_for_claim(organization_id, project_id, claim_id)
        return DrilldownResponse(
            argument_chain=[self._claim_response(item) for item in chain],
            demand_nodes=[
                DemandNodeStub.model_validate(item, from_attributes=True) for item in demand
            ],
            content_cards=[
                ContentCardStub.model_validate(item, from_attributes=True) for item in cards
            ],
        )
