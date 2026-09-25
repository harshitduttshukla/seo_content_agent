"""V3 Content Hub plan board service (handoff §5.1).

Reads the board as one projection and makes the only moves the board owns:
Backlog ↔ Planned, and reordering within Planned by ``priority``. Every state
change goes through :func:`transition_content_card`, the single place the §5.2
state machine is enforced.
"""

from datetime import datetime
from uuid import UUID

from app.core.errors import ConflictError, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.audit.repository import AuditWriter
from app.domains.content_cards.board import (
    BOARD_COLUMNS,
    PLANNED_COLUMN_STATES,
    BoardColumn,
    column_for_state,
    market_code,
    require_board_transition,
    require_valid_transition,
)
from app.domains.content_cards.models import ContentCard
from app.domains.content_cards.repository import BoardFacet, BoardRow, ContentCardRepository
from app.domains.content_cards.schemas import (
    BoardCard,
    BoardColumnView,
    BoardDemandRef,
    BoardFilterOptions,
    BoardFilters,
    BoardMoveRequest,
    BoardRef,
    ContentCardState,
    ContentHubBoard,
    PlannedOrderRequest,
)
from app.domains.projects.service import ProjectService, is_added_after_plan_lock
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession

_PLANNED_STATES = sorted(PLANNED_COLUMN_STATES)


def transition_content_card(card: ContentCard, target: ContentCardState) -> None:
    """Apply a §5.2-legal state change to a loaded, locked, authorized card.

    Assigns through the model so the ``planned_at`` listener stamps entry into
    Planned; bumps ``revision`` for optimistic concurrency. Callers load with
    tenant scope and authorize first; this only validates and mutates.
    """
    require_valid_transition(card.state, target)
    card.state = target
    card.revision += 1


def _ref(ref_id: UUID | None, name: str | None) -> BoardRef | None:
    return BoardRef(id=ref_id, name=name or "") if ref_id is not None and name is not None else None


def board_card(row: BoardRow, plan_locked_at: datetime | None) -> BoardCard:
    card = row.card
    demand = (
        BoardDemandRef(id=card.primary_demand_id, text=row.demand_text, volume=row.demand_volume)
        if card.primary_demand_id is not None and row.demand_text is not None
        else None
    )
    prompt = (
        BoardDemandRef(
            id=card.primary_prompt_id,
            text=row.prompt_text,
            citation_gap=row.prompt_citation_gap,
            platform_count=len(row.prompt_platforms or []),
        )
        if card.primary_prompt_id is not None and row.prompt_text is not None
        else None
    )
    score = row.demand_score if row.demand_score is not None else row.prompt_score
    column = column_for_state(card.state)
    return BoardCard(
        id=card.id,
        title=card.title,
        kind=card.kind,
        state=card.state,
        column=column,
        origin=card.origin,
        area=_ref(card.area_id, row.area_name),
        argument=_ref(card.argument_id, row.argument_name),
        owner=_ref(card.owner, row.owner_name),
        market=market_code(card.market),
        due=card.due,
        priority=card.priority,
        primary_demand=demand,
        primary_prompt=prompt,
        secondary_demand_count=len(card.secondary_demand_ids),
        score=score,
        has_qa_report=card.qa_report is not None,
        url=card.url,
        cms_id=card.cms_id,
        published_at=card.published_at,
        stale_claim_count=len(card.stale_claims),
        planned_at=card.planned_at,
        # The chip belongs to the Planned column; the rule itself is the projects helper.
        is_new_after_plan_lock=column is BoardColumn.PLANNED
        and is_added_after_plan_lock(card.planned_at, plan_locked_at),
        revision=card.revision,
        updated_at=card.updated_at,
    )


def filter_options(facets: list[BoardFacet]) -> BoardFilterOptions:
    areas: dict[UUID, str] = {}
    arguments: dict[UUID, str] = {}
    owners: dict[UUID, str] = {}
    kinds: set[str] = set()
    markets: set[str] = set()
    for facet in facets:
        if facet.area_id is not None and facet.area_name is not None:
            areas[facet.area_id] = facet.area_name
        if facet.argument_id is not None and facet.argument_name is not None:
            arguments[facet.argument_id] = facet.argument_name
        if facet.owner_id is not None and facet.owner_name is not None:
            owners[facet.owner_id] = facet.owner_name
        kinds.add(facet.kind)
        code = market_code(facet.market)
        if code is not None:
            markets.add(code)

    def refs(values: dict[UUID, str]) -> list[BoardRef]:
        return [
            BoardRef(id=key, name=name)
            for key, name in sorted(values.items(), key=lambda item: (item[1], str(item[0])))
        ]

    return BoardFilterOptions(
        areas=refs(areas),
        kinds=sorted(kinds),
        owners=refs(owners),
        arguments=refs(arguments),
        markets=sorted(markets),
    )


class ContentHubService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = ContentCardRepository(session)
        self._projects = ProjectService()
        self._audit = AuditWriter()

    async def _authorize(
        self,
        organization_id: UUID,
        project_id: UUID,
        actor: AuthenticatedUser,
        permission: PermissionCode,
    ) -> datetime | None:
        """Membership + permission via the project service; returns ``plan_locked_at``."""
        project = await self._projects.get_model(
            self._session, actor=actor, project_id=project_id, permission=permission
        )
        if project.organization_id != organization_id:
            raise ResourceNotFound("project")
        return project.plan_locked_at

    async def _board(
        self,
        organization_id: UUID,
        project_id: UUID,
        filters: BoardFilters,
        locked_at: datetime | None,
    ) -> ContentHubBoard:
        rows = await self._repository.list_board_rows(organization_id, project_id, filters)
        facets = await self._repository.list_board_facets(organization_id, project_id)
        grouped: dict[BoardColumn, list[BoardCard]] = {key: [] for key, _, _ in BOARD_COLUMNS}
        for row in rows:
            card = board_card(row, locked_at)
            grouped[BoardColumn(card.column)].append(card)
        for key, cards in grouped.items():
            # Only Planned is ordered by priority (§5.1); the rest show latest activity first.
            if key is not BoardColumn.PLANNED:
                cards.sort(key=lambda item: (item.updated_at, str(item.id)), reverse=True)
        return ContentHubBoard(
            project_id=project_id,
            plan_locked_at=locked_at,
            total_count=len(rows),
            columns=[
                BoardColumnView(
                    key=key, label=label, tone=tone, count=len(grouped[key]), cards=grouped[key]
                )
                for key, label, tone in BOARD_COLUMNS
            ],
            filter_options=filter_options(facets),
        )

    async def get_board(
        self,
        organization_id: UUID,
        project_id: UUID,
        filters: BoardFilters,
        *,
        actor: AuthenticatedUser,
    ) -> ContentHubBoard:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            locked_at = await self._authorize(
                organization_id, project_id, actor, PermissionCode.CONTENT_READ
            )
            return await self._board(organization_id, project_id, filters, locked_at)

    async def move_card(
        self,
        organization_id: UUID,
        project_id: UUID,
        card_id: UUID,
        payload: BoardMoveRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> BoardCard:
        """Backlog ↔ Planned. Entering Planned puts the card at the bottom of the column."""
        target = ContentCardState(payload.target_state)
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            locked_at = await self._authorize(
                organization_id, project_id, actor, PermissionCode.CONTENT_WRITE
            )
            card = await self._repository.get_for_update(organization_id, project_id, card_id)
            if card is None:
                raise ResourceNotFound("content_card")
            if card.revision != payload.revision:
                raise ConflictError(
                    "VERSION_CONFLICT",
                    "The card changed; refresh and retry.",
                    details={"current_revision": card.revision},
                )
            previous = card.state
            require_board_transition(previous, target)
            if target is ContentCardState.PLANNED:
                bottom = await self._repository.max_priority_in_states(
                    organization_id, project_id, _PLANNED_STATES
                )
                card.priority = (bottom or 0) + 1
            transition_content_card(card, target)
            await self._session.flush()
            await self._session.refresh(card)
            self._audit.add(
                self._session,
                actor_user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                action="content_card.state_changed",
                resource_type="content_card",
                resource_id=card.id,
                request_id=request_id,
                metadata={"from": previous, "to": str(target), "via": "content_hub_board"},
            )
            rows = await self._repository.list_board_rows(
                organization_id, project_id, BoardFilters(), card_id=card.id
            )
            return board_card(rows[0], locked_at)

    async def reorder_planned(
        self,
        organization_id: UUID,
        project_id: UUID,
        payload: PlannedOrderRequest,
        *,
        actor: AuthenticatedUser,
        request_id: str,
    ) -> ContentHubBoard:
        """Set Planned priorities to 1..n in the given order.

        The request must list exactly the cards now in the Planned column; a
        missing, extra, duplicate or foreign id means the client's view is stale
        or wrong, and nothing is written.
        """
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            locked_at = await self._authorize(
                organization_id, project_id, actor, PermissionCode.CONTENT_WRITE
            )
            cards = await self._repository.list_in_states_for_update(
                organization_id, project_id, _PLANNED_STATES
            )
            by_id = {card.id: card for card in cards}
            requested = payload.card_ids
            if len(set(requested)) != len(requested) or set(requested) != set(by_id):
                raise ConflictError(
                    "PLANNED_ORDER_MISMATCH",
                    "The Planned column changed; refresh and retry.",
                    details={"planned_count": len(by_id)},
                )
            changed = 0
            for position, card_id in enumerate(requested, start=1):
                card = by_id[card_id]
                if card.priority != position:
                    card.priority = position
                    card.revision += 1
                    changed += 1
            await self._session.flush()
            if changed:
                self._audit.add(
                    self._session,
                    actor_user_id=actor.user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    action="content_card.planned_reordered",
                    resource_type="project",
                    resource_id=project_id,
                    request_id=request_id,
                    metadata={"changed_count": changed},
                )
            return await self._board(organization_id, project_id, BoardFilters(), locked_at)
