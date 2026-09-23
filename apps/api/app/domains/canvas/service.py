"""Application service for V3 Canvas reads and immutable claim edits."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.errors import BadRequestError, ConflictError, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.canvas.models import Argument, Canvas, Claim, ClaimRow
from app.domains.canvas.repository import CanvasRepository
from app.domains.canvas.schemas import (
    AreaResponse,
    ArgumentCreateRequest,
    ArgumentResponse,
    CanvasAnchor,
    CanvasAnchorType,
    CanvasAnchorUpsertRequest,
    CanvasClaimCreateRequest,
    CanvasFullResponse,
    CanvasListItem,
    CanvasListResponse,
    ClaimCitationCreateRequest,
    ClaimEditCheckResponse,
    ClaimEditConfirmResponse,
    ClaimResponse,
    ContentCardStub,
    DemandNodeStub,
    DrilldownResponse,
)
from app.domains.content_cards.models import ContentCard, ContentCardClaim
from app.domains.job_runs.models import JobRun, JobRunStatus
from app.security.authorization import AuthorizationService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class CanvasService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = CanvasRepository(session)
        self._session = session
        from app.domains.auth.repository import AuthorizationRepository

        self._authorization = AuthorizationService(AuthorizationRepository())

    @staticmethod
    def _claim_response(claim: Claim, citation_count: int = 0) -> ClaimResponse:
        if claim.row == ClaimRow.PITCH:
            clm_number = "CLM-000"
        else:
            clm_number = f"CLM-{str(claim.id).split('-')[0].upper()}"
        overrides = claim.market_overrides if claim.market_overrides is not None else {}
        return ClaimResponse.model_validate(
            claim,
            from_attributes=True,
        ).model_copy(
            update={
                "clm_number": clm_number,
                "inherited": False,
                "citation_count": citation_count,
                "market_overrides": overrides,
            }
        )

    @staticmethod
    def _has_primary_anchor(
        canvas: Canvas, replacement: tuple[CanvasAnchorType, dict[str, object]]
    ) -> bool:
        replacement_type, replacement_value = replacement
        anchors = (
            (CanvasAnchorType.COMPANY, canvas.company_anchor),
            (CanvasAnchorType.PERSONA, canvas.persona_anchor),
            (CanvasAnchorType.USE_CASE, canvas.use_case_anchor),
            (CanvasAnchorType.ALTERNATIVE, canvas.alternative_anchor),
            (CanvasAnchorType.CATEGORY, canvas.category_anchor),
        )
        return any(
            bool((replacement_value if anchor_type == replacement_type else value).get("primary"))
            for anchor_type, value in anchors
        )

    @staticmethod
    def _empty_canvas_response(canvas: Canvas) -> CanvasFullResponse:
        anchors = [
            CanvasAnchor(anchor_type=anchor_type, **anchor)
            for anchor_type, anchor in (
                (CanvasAnchorType.COMPANY, canvas.company_anchor),
                (CanvasAnchorType.PERSONA, canvas.persona_anchor),
                (CanvasAnchorType.USE_CASE, canvas.use_case_anchor),
                (CanvasAnchorType.ALTERNATIVE, canvas.alternative_anchor),
                (CanvasAnchorType.CATEGORY, canvas.category_anchor),
            )
            if anchor
        ]
        return CanvasFullResponse(
            id=canvas.id,
            product_line=canvas.product_line,
            name="Company canvas",
            anchors=anchors,
            problem_summary=canvas.problem_summary,
            differentiation_summary=canvas.differentiation_summary,
            version=canvas.version,
            arguments=[],
            problem_summary_claim=None,
            differentiation_summary_claim=None,
            pitch_claim=None,
        )

    @staticmethod
    def _canvas_response(
        canvas: Canvas,
        arguments: list[Argument],
        claims: list[Claim],
        citation_counts: dict[UUID, int] | None = None,
    ) -> CanvasFullResponse:
        counts = citation_counts or {}
        claims_by_argument: dict[UUID, list[ClaimResponse]] = {}
        summary_claims: dict[str, ClaimResponse] = {}
        pitch_claim: ClaimResponse | None = None
        for claim in claims:
            response = CanvasService._claim_response(claim, citation_count=counts.get(claim.id, 0))
            if claim.row == ClaimRow.PITCH:
                pitch_claim = response
            elif claim.row in (ClaimRow.PROBLEM_SUMMARY, ClaimRow.DIFFERENTIATION_SUMMARY):
                summary_claims[claim.row] = response
            elif claim.argument_id is not None:
                claims_by_argument.setdefault(claim.argument_id, []).append(response)
        anchors = [
            CanvasAnchor(anchor_type=anchor_type, **anchor)
            for anchor_type, anchor in (
                (CanvasAnchorType.COMPANY, canvas.company_anchor),
                (CanvasAnchorType.PERSONA, canvas.persona_anchor),
                (CanvasAnchorType.USE_CASE, canvas.use_case_anchor),
                (CanvasAnchorType.ALTERNATIVE, canvas.alternative_anchor),
                (CanvasAnchorType.CATEGORY, canvas.category_anchor),
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
            problem_summary_claim=summary_claims.get(ClaimRow.PROBLEM_SUMMARY),
            differentiation_summary_claim=summary_claims.get(ClaimRow.DIFFERENTIATION_SUMMARY),
            pitch_claim=pitch_claim,
        )

    async def create_company_canvas(
        self, organization_id: UUID, project_id: UUID, *, actor: AuthenticatedUser
    ) -> CanvasFullResponse:
        try:
            async with transactional_session(self._session):
                await set_actor_context(self._session, actor.user_id)
                await self._authorization.require_project(
                    self._session,
                    user_id=actor.user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    permission=PermissionCode.STRATEGY_WRITE,
                )
                existing = await self.repository.get_company_canvas(organization_id, project_id)
                if existing is not None:
                    raise ConflictError(
                        "COMPANY_CANVAS_EXISTS",
                        "This project already has a company canvas.",
                    )
                canvas = Canvas(
                    id=uuid4(),
                    organization_id=organization_id,
                    project_id=project_id,
                    parent_id=None,
                    product_line=None,
                    company_anchor={},
                    persona_anchor={},
                    use_case_anchor={},
                    alternative_anchor={},
                    category_anchor={},
                    problem_summary="",
                    differentiation_summary="",
                    version=1,
                )
                self.repository.add(canvas)
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "COMPANY_CANVAS_EXISTS",
                "This project already has a company canvas.",
            ) from exc
        return self._empty_canvas_response(canvas)

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

    async def list_areas(
        self,
        organization_id: UUID,
        project_id: UUID,
        *,
        canvas_id: UUID | None,
        actor: AuthenticatedUser,
    ) -> list[AreaResponse]:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            if canvas_id is not None:
                canvas = await self.repository.get_canvas_by_id(
                    organization_id, project_id, canvas_id
                )
                if canvas is None:
                    raise ResourceNotFound("canvas")
            areas = await self.repository.get_areas_for_project(
                organization_id, project_id, canvas_id=canvas_id
            )
        return [AreaResponse.model_validate(area) for area in areas]

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
            arguments = list(
                await self.repository.get_arguments_for_canvas(
                    organization_id, project_id, canvas_id
                )
            )
            claims = list(
                await self.repository.get_claims_for_canvas(organization_id, project_id, canvas_id)
            )
            citation_counts = await self.repository.get_citation_counts_for_claims(
                organization_id, project_id, [c.id for c in claims]
            )
        return self._canvas_response(canvas, arguments, claims, citation_counts)

    async def upsert_anchor(
        self,
        organization_id: UUID,
        project_id: UUID,
        canvas_id: UUID,
        payload: CanvasAnchorUpsertRequest,
        *,
        actor: AuthenticatedUser,
    ) -> CanvasFullResponse:
        attribute = f"{payload.anchor_type.value}_anchor"
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_WRITE,
            )
            canvas = await self.repository.get_canvas_by_id(organization_id, project_id, canvas_id)
            if canvas is None:
                raise ResourceNotFound("canvas")
            anchor_value = {"text": payload.text.strip(), "primary": payload.primary}
            if not self._has_primary_anchor(canvas, (payload.anchor_type, anchor_value)):
                raise BadRequestError(
                    "At least one canvas anchor must be marked primary.", field="primary"
                )
            setattr(canvas, attribute, anchor_value)
            await self._session.flush()
        return await self.get_canvas(organization_id, project_id, canvas_id, actor=actor)

    async def create_argument(
        self,
        organization_id: UUID,
        project_id: UUID,
        canvas_id: UUID,
        payload: ArgumentCreateRequest,
        *,
        actor: AuthenticatedUser,
    ) -> CanvasFullResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_WRITE,
            )
            canvas = await self.repository.get_canvas_by_id(organization_id, project_id, canvas_id)
            if canvas is None:
                raise ResourceNotFound("canvas")
            argument = Argument(
                id=uuid4(),
                organization_id=organization_id,
                project_id=project_id,
                canvas_id=canvas_id,
                order=await self.repository.get_next_argument_order(
                    organization_id, project_id, canvas_id
                ),
                sub_problem=payload.sub_problem.strip(),
                differentiation_pillar=payload.differentiation_pillar.strip(),
                capability=payload.capability.strip(),
                features=[feature.strip() for feature in payload.features if feature.strip()],
                benefit=payload.benefit.strip(),
            )
            self.repository.add(argument)
            await self._session.flush()
            for row, text in (
                (ClaimRow.SUB_PROBLEM, argument.sub_problem),
                (ClaimRow.PILLAR, argument.differentiation_pillar),
                (ClaimRow.CAPABILITY, argument.capability),
                (ClaimRow.FEATURE, " · ".join(argument.features)),
                (ClaimRow.BENEFIT, argument.benefit),
            ):
                if text:
                    self.repository.add(
                        Claim(
                            id=uuid4(),
                            organization_id=organization_id,
                            project_id=project_id,
                            canvas_id=canvas_id,
                            argument_id=argument.id,
                            row=row,
                            text=text,
                            evidence="",
                            approved=False,
                            version=1,
                            market_overrides={},
                        )
                    )
            await self._session.flush()
        return await self.get_canvas(organization_id, project_id, canvas_id, actor=actor)

    async def create_claim(
        self,
        organization_id: UUID,
        project_id: UUID,
        canvas_id: UUID,
        payload: CanvasClaimCreateRequest,
        *,
        actor: AuthenticatedUser,
    ) -> CanvasFullResponse:
        row = ClaimRow(payload.row.value)
        canvas_rows = {
            ClaimRow.PROBLEM_SUMMARY,
            ClaimRow.DIFFERENTIATION_SUMMARY,
            ClaimRow.PITCH,
        }
        argument_rows = {
            ClaimRow.SUB_PROBLEM,
            ClaimRow.PILLAR,
            ClaimRow.CAPABILITY,
            ClaimRow.FEATURE,
            ClaimRow.BENEFIT,
        }
        if row in canvas_rows and payload.argument_id is not None:
            raise BadRequestError("Canvas-level claims cannot belong to an argument.")
        if row in argument_rows and payload.argument_id is None:
            raise BadRequestError("Argument claims require an argument ID.")
        if row not in canvas_rows | argument_rows:
            raise BadRequestError("This claim row cannot be created from the canvas.")
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_WRITE,
            )
            canvas = await self.repository.get_canvas_by_id(organization_id, project_id, canvas_id)
            if canvas is None:
                raise ResourceNotFound("canvas")
            argument: Argument | None = None
            if payload.argument_id is not None:
                argument = await self.repository.get_argument_by_id(
                    organization_id, project_id, payload.argument_id
                )
                if argument is None or argument.canvas_id != canvas_id:
                    raise ResourceNotFound("argument")
            existing = await self.repository.get_current_claim_for_cell(
                organization_id,
                project_id,
                canvas_id,
                payload.argument_id,
                row.value,
            )
            if existing is not None:
                raise ConflictError(
                    "CLAIM_ALREADY_EXISTS",
                    "This canvas cell already has a claim. Edit its current version instead.",
                )
            text = payload.text.strip()
            claim = Claim(
                id=uuid4(),
                organization_id=organization_id,
                project_id=project_id,
                canvas_id=canvas_id,
                argument_id=payload.argument_id,
                row=row,
                text=text,
                evidence=payload.evidence.strip(),
                approved=False,
                version=1,
                market_overrides={},
            )
            self.repository.add(claim)
            if row == ClaimRow.PROBLEM_SUMMARY:
                canvas.problem_summary = text
            elif row == ClaimRow.DIFFERENTIATION_SUMMARY:
                canvas.differentiation_summary = text
            elif argument is not None:
                if row == ClaimRow.SUB_PROBLEM:
                    argument.sub_problem = text
                elif row == ClaimRow.PILLAR:
                    argument.differentiation_pillar = text
                elif row == ClaimRow.CAPABILITY:
                    argument.capability = text
                elif row == ClaimRow.FEATURE:
                    argument.features = [text]
                elif row == ClaimRow.BENEFIT:
                    argument.benefit = text
            await self._session.flush()
        return await self.get_canvas(organization_id, project_id, canvas_id, actor=actor)

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
            row = ClaimRow(old_claim.row)
            if row in (ClaimRow.PROBLEM_SUMMARY, ClaimRow.DIFFERENTIATION_SUMMARY):
                canvas = await self.repository.get_canvas_by_id(
                    organization_id, project_id, old_claim.canvas_id
                )
                if canvas is not None:
                    if row == ClaimRow.PROBLEM_SUMMARY:
                        canvas.problem_summary = text
                    else:
                        canvas.differentiation_summary = text
            elif old_claim.argument_id is not None:
                argument = await self.repository.get_argument_by_id(
                    organization_id, project_id, old_claim.argument_id
                )
                if argument is not None:
                    if row == ClaimRow.SUB_PROBLEM:
                        argument.sub_problem = text
                    elif row == ClaimRow.PILLAR:
                        argument.differentiation_pillar = text
                    elif row == ClaimRow.CAPABILITY:
                        argument.capability = text
                    elif row == ClaimRow.FEATURE:
                        argument.features = [text]
                    elif row == ClaimRow.BENEFIT:
                        argument.benefit = text
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
            demand = await self.repository.get_demand_for_claim(
                organization_id, project_id, claim_id
            )
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

    async def approve_claim(
        self,
        organization_id: UUID,
        project_id: UUID,
        claim_id: UUID,
        *,
        actor: AuthenticatedUser,
    ) -> ClaimResponse:
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
            claim.approved = True
            claim.approved_by = actor.user_id
            claim.approved_at = datetime.now(UTC)
            await self._session.flush()
            citation_count = await self.repository.get_citation_count(
                organization_id, project_id, claim_id
            )
            return self._claim_response(claim, citation_count=citation_count)

    async def list_content_cards(
        self,
        organization_id: UUID,
        project_id: UUID,
        *,
        actor: AuthenticatedUser,
    ) -> list[ContentCardStub]:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            cards = await self.repository.get_project_content_cards(organization_id, project_id)
            return [ContentCardStub.model_validate(c, from_attributes=True) for c in cards]

    async def add_citation(
        self,
        organization_id: UUID,
        project_id: UUID,
        claim_id: UUID,
        payload: ClaimCitationCreateRequest,
        *,
        actor: AuthenticatedUser,
    ) -> DrilldownResponse:
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

            card: ContentCard | None = None
            if payload.content_card_id is not None:
                card = await self.repository.get_content_card_by_id(
                    organization_id, project_id, payload.content_card_id
                )
                if card is None:
                    raise ResourceNotFound("content_card")
            elif payload.title:
                card = ContentCard(
                    id=uuid4(),
                    organization_id=organization_id,
                    project_id=project_id,
                    kind="cluster",
                    title=payload.title.strip(),
                    url=payload.url.strip()
                    if payload.url
                    else f"https://example.com/test-{uuid4().hex[:6]}",
                    state="live",
                    origin="manual",
                )
                self.repository.add(card)
                await self._session.flush()
            else:
                raise BadRequestError("Either content_card_id or title must be provided.")

            existing_link = await self.repository.get_content_card_claim(
                organization_id, project_id, card.id, claim_id
            )
            if existing_link is None:
                link = ContentCardClaim(
                    id=uuid4(),
                    organization_id=organization_id,
                    project_id=project_id,
                    content_card_id=card.id,
                    claim_id=claim_id,
                )
                self.repository.add(link)
                await self._session.flush()

        return await self.get_claim_drilldown(organization_id, project_id, claim_id, actor=actor)
