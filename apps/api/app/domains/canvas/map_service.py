"""Read-only strategy-map assembly for the Strategy module's Map tab.

V3 Reference: seo-geo-system-handoff-v3.md §4.4, §1.2 principle 1, §3.1

The map is the one view that shows the whole strategy graph at once:

    company canvas → product-line canvases → areas → sub-areas

Nothing here writes. There is no JobRun, because this is a read and not a job,
and there is no model call, because every number is an aggregate over rows that
already exist.

Query budget is fixed regardless of how many areas a tenant has: the actor
context and authorization checks, then seven repository reads — canvases,
arguments, areas, claim counts, kept-demand counts, card counts by state, and one scalar
for cards no area claims. Adding a per-area query here would turn
a 200-area tenant into 200 round trips, so counts arrive pre-grouped.
"""

from collections.abc import Sequence
from uuid import UUID

from app.db.session import set_actor_context, transactional_session
from app.domains.canvas.models import Area, Argument, Canvas
from app.domains.canvas.repository import CanvasRepository
from app.domains.canvas.schemas import MapAreaNode, MapCanvasNode, StrategyMapResponse
from app.security.authorization import AuthorizationService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession

UNMAPPED_AREA_NAME = "unmapped"
"""Site import routes pages it cannot classify to an area named "Unmapped" (§4.6).

No column marks that area, so the name is the only available signal and it is
matched case-insensitively. Such an area sorts last among its siblings and never
carries the coral "content gap" chip: unmapped pages are cards, which is the
opposite problem to demand with no content at all.
"""


def _sum_states(breakdowns: Sequence[dict[str, int]]) -> dict[str, int]:
    """Add per-state card counts together; states are listed, never ranked."""
    total: dict[str, int] = {}
    for breakdown in breakdowns:
        for state, count in breakdown.items():
            total[state] = total.get(state, 0) + count
    return total


class StrategyMapService:
    """Assembles the read-only combined tree for one project."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = CanvasRepository(session)
        self._session = session
        from app.domains.auth.repository import AuthorizationRepository

        self._authorization = AuthorizationService(AuthorizationRepository())

    async def get_strategy_map(
        self, organization_id: UUID, project_id: UUID, *, actor: AuthenticatedUser
    ) -> StrategyMapResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            await self._authorization.require_project(
                self._session,
                user_id=actor.user_id,
                organization_id=organization_id,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            canvases = list(
                await self.repository.get_canvases_for_project(organization_id, project_id)
            )
            company = next((canvas for canvas in canvases if canvas.parent_id is None), None)
            if company is None:
                return StrategyMapResponse(company_canvas=None, unassigned_card_count=0)

            arguments = list(
                await self.repository.get_arguments_for_project(organization_id, project_id)
            )
            areas = list(await self.repository.get_areas_for_project(organization_id, project_id))
            cell_counts = await self.repository.get_claim_counts_by_canvas(
                organization_id, project_id
            )
            demand_counts = await self.repository.get_kept_demand_counts_by_area(
                organization_id, project_id
            )
            card_state_counts = await self.repository.get_card_state_counts_by_area(
                organization_id, project_id
            )
            unassigned_card_count = await self.repository.count_cards_without_area(
                organization_id, project_id
            )

        return StrategyMapResponse(
            company_canvas=self._build_tree(
                company,
                canvases,
                arguments,
                areas,
                cell_counts=cell_counts,
                demand_counts=demand_counts,
                card_state_counts=card_state_counts,
            ),
            unassigned_card_count=unassigned_card_count,
        )

    # ── tree assembly ────────────────────────────────────────────────

    def _build_tree(
        self,
        company: Canvas,
        canvases: Sequence[Canvas],
        arguments: Sequence[Argument],
        areas: Sequence[Area],
        *,
        cell_counts: dict[UUID, int],
        demand_counts: dict[UUID, int],
        card_state_counts: dict[UUID, dict[str, int]],
    ) -> MapCanvasNode:
        arguments_by_canvas: dict[UUID, list[Argument]] = {}
        for argument in arguments:
            arguments_by_canvas.setdefault(argument.canvas_id, []).append(argument)

        labels = self._argument_labels(company, canvases, arguments_by_canvas)
        pillars = {argument.id: argument.differentiation_pillar or None for argument in arguments}

        areas_by_canvas: dict[UUID, list[Area]] = {}
        for area in areas:
            areas_by_canvas.setdefault(area.canvas_id, []).append(area)

        def canvas_node(canvas: Canvas) -> MapCanvasNode:
            own = sorted(arguments_by_canvas.get(canvas.id, []), key=lambda a: a.order)
            is_company = canvas.parent_id is None
            inherits: list[str] = []
            adds: list[str] = []
            override_count = 0
            if not is_company:
                for argument in own:
                    if argument.override:
                        # An overridden argument is not carried "unchanged", so it is
                        # counted rather than listed among the inherited labels.
                        override_count += 1
                    elif argument.inherited_from is not None:
                        inherits.append(labels.get(argument.inherited_from, ""))
                    else:
                        adds.append(labels.get(argument.id, ""))
            return MapCanvasNode(
                id=canvas.id,
                name=canvas.product_line or "Company canvas",
                product_line=canvas.product_line,
                is_company=is_company,
                argument_count=len(own),
                cell_count=cell_counts.get(canvas.id, 0),
                inherits=[label for label in inherits if label],
                override_count=override_count,
                adds=[label for label in adds if label],
                areas=self._area_nodes(
                    areas_by_canvas.get(canvas.id, []),
                    pillars=pillars,
                    demand_counts=demand_counts,
                    card_state_counts=card_state_counts,
                ),
                product_lines=[
                    canvas_node(child)
                    for child in canvases
                    if child.parent_id == canvas.id and child.id != canvas.id
                ],
            )

        return canvas_node(company)

    def _area_nodes(
        self,
        canvas_areas: Sequence[Area],
        *,
        pillars: dict[UUID, str | None],
        demand_counts: dict[UUID, int],
        card_state_counts: dict[UUID, dict[str, int]],
    ) -> list[MapAreaNode]:
        """Nest one canvas's areas by parent_id, recursing to arbitrary depth."""
        by_id = {area.id: area for area in canvas_areas}
        children_of: dict[UUID | None, list[Area]] = {}
        for area in canvas_areas:
            # An area whose parent is absent from this canvas is treated as a root
            # rather than dropped, so no row disappears from the map silently.
            parent = area.parent_id if area.parent_id in by_id else None
            children_of.setdefault(parent, []).append(area)

        def is_unmapped(area: Area) -> bool:
            return area.name.strip().lower() == UNMAPPED_AREA_NAME

        def sort_key(area: Area) -> tuple[bool, str]:
            # The Unmapped area sorts last among its siblings (§4.6).
            return (is_unmapped(area), area.name.casefold())

        def build(parent_id: UUID | None, seen: frozenset[UUID]) -> list[MapAreaNode]:
            nodes: list[MapAreaNode] = []
            for area in sorted(children_of.get(parent_id, []), key=sort_key):
                if area.id in seen:
                    continue  # parent_id cycles cannot hang the request
                children = build(area.id, seen | {area.id})
                card_states = dict(card_state_counts.get(area.id, {}))
                card_count = sum(card_states.values())
                descendant_card_states = _sum_states(
                    [child.card_states for child in children]
                    + [child.descendant_card_states for child in children]
                )
                demand_count = demand_counts.get(area.id, 0)
                unmapped = is_unmapped(area)
                nodes.append(
                    MapAreaNode(
                        id=area.id,
                        name=area.name,
                        parent_id=area.parent_id,
                        default_argument_id=area.default_argument_id,
                        default_argument_pillar=(
                            pillars.get(area.default_argument_id)
                            if area.default_argument_id is not None
                            else None
                        ),
                        demand_count=demand_count,
                        card_count=card_count,
                        card_states=card_states,
                        descendant_card_states=descendant_card_states,
                        is_unmapped=unmapped,
                        # A gap is known demand with no content: none on this area and
                        # none below it. Unmapped pages are cards, never a gap.
                        content_gap=(
                            demand_count > 0
                            and card_count == 0
                            and not descendant_card_states
                            and not unmapped
                        ),
                        children=children,
                    )
                )
            return nodes

        return build(None, frozenset())

    @staticmethod
    def _argument_labels(
        company: Canvas,
        canvases: Sequence[Canvas],
        arguments_by_canvas: dict[UUID, list[Argument]],
    ) -> dict[UUID, str]:
        """Assign the A1, A2, A3… labels the inheritance summary reads back.

        Company-canvas arguments are numbered by their own order. An argument that
        exists only on a child canvas continues the numbering past the company
        canvas's count, which is why the mockup's third product line "adds A4"
        against a company canvas holding A1 to A3.
        """
        labels: dict[UUID, str] = {}
        company_arguments = sorted(arguments_by_canvas.get(company.id, []), key=lambda a: a.order)
        for index, argument in enumerate(company_arguments, start=1):
            labels[argument.id] = f"A{index}"

        next_label = len(company_arguments) + 1
        for canvas in canvases:
            if canvas.parent_id is None:
                continue
            own = sorted(arguments_by_canvas.get(canvas.id, []), key=lambda a: a.order)
            for argument in own:
                if argument.inherited_from is None and not argument.override:
                    labels[argument.id] = f"A{next_label}"
                    next_label += 1
        return labels
