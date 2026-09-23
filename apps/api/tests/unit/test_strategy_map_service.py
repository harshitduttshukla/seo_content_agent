"""Unit tests for the read-only V3 strategy map (handoff §4.4)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from app.domains.canvas.map_service import StrategyMapService
from app.domains.canvas.models import Area, Argument, Canvas
from app.domains.canvas.schemas import MapAreaNode
from app.security.principal import AuthenticatedUser, PermissionCode


@asynccontextmanager
async def passthrough_transaction(session: object):
    yield session


def actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="map-test",
        email="map@example.com",
        display_name="Map Tester",
    )


def canvas(
    organization_id: UUID,
    project_id: UUID,
    *,
    parent_id: UUID | None = None,
    product_line: str | None = None,
) -> Canvas:
    return Canvas(
        id=uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        parent_id=parent_id,
        product_line=product_line,
        company_anchor={},
        persona_anchor={},
        use_case_anchor={},
        alternative_anchor={},
        category_anchor={},
        problem_summary="",
        differentiation_summary="",
        version=1,
    )


def argument(
    canvas_row: Canvas,
    order: int,
    *,
    pillar: str = "",
    inherited_from: UUID | None = None,
    override: bool = False,
) -> Argument:
    return Argument(
        id=uuid4(),
        organization_id=canvas_row.organization_id,
        project_id=canvas_row.project_id,
        canvas_id=canvas_row.id,
        order=order,
        sub_problem="",
        differentiation_pillar=pillar,
        capability="",
        features=[],
        benefit="",
        inherited_from=inherited_from,
        override=override,
    )


def area(
    canvas_row: Canvas,
    name: str,
    *,
    parent_id: UUID | None = None,
    default_argument_id: UUID | None = None,
) -> Area:
    return Area(
        id=uuid4(),
        organization_id=canvas_row.organization_id,
        project_id=canvas_row.project_id,
        canvas_id=canvas_row.id,
        parent_id=parent_id,
        name=name,
        default_argument_id=default_argument_id,
    )


def build_service(
    *,
    canvases: list[Canvas],
    arguments: list[Argument],
    areas: list[Area],
    cell_counts: dict[UUID, int] | None = None,
    demand_counts: dict[UUID, int] | None = None,
    card_counts: dict[UUID, int] | None = None,
    card_states: dict[UUID, dict[str, int]] | None = None,
    unassigned: int = 0,
) -> StrategyMapService:
    service = StrategyMapService(AsyncMock())
    service._authorization.require_project = AsyncMock(return_value="viewer")
    service.repository.get_canvases_for_project = AsyncMock(return_value=canvases)
    service.repository.get_arguments_for_project = AsyncMock(return_value=arguments)
    service.repository.get_areas_for_project = AsyncMock(return_value=areas)
    service.repository.get_claim_counts_by_canvas = AsyncMock(return_value=cell_counts or {})
    service.repository.get_kept_demand_counts_by_area = AsyncMock(return_value=demand_counts or {})
    # ``card_counts`` is shorthand for cards that are all live; ``card_states`` sets states.
    states = {area_id: {"live": count} for area_id, count in (card_counts or {}).items()}
    states.update(card_states or {})
    service.repository.get_card_state_counts_by_area = AsyncMock(return_value=states)
    service.repository.count_cards_without_area = AsyncMock(return_value=unassigned)
    return service


async def run(service: StrategyMapService, organization_id: UUID, project_id: UUID):
    with (
        patch("app.domains.canvas.map_service.transactional_session", passthrough_transaction),
        patch("app.domains.canvas.map_service.set_actor_context", AsyncMock()),
    ):
        return await service.get_strategy_map(organization_id, project_id, actor=actor())


def flatten(nodes: list[MapAreaNode]) -> list[MapAreaNode]:
    out: list[MapAreaNode] = []
    for node in nodes:
        out.append(node)
        out.extend(flatten(node.children))
    return out


@pytest.mark.asyncio
async def test_no_canvas_returns_null_company_canvas() -> None:
    service = build_service(canvases=[], arguments=[], areas=[])
    result = await run(service, uuid4(), uuid4())
    assert result.company_canvas is None


@pytest.mark.asyncio
async def test_company_canvas_with_no_areas_still_reports_its_counts() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    service = build_service(
        canvases=[company],
        arguments=[argument(company, 0), argument(company, 1), argument(company, 2)],
        areas=[],
        cell_counts={company.id: 41},
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    assert result.company_canvas.is_company is True
    assert result.company_canvas.name == "Company canvas"
    assert result.company_canvas.argument_count == 3
    assert result.company_canvas.cell_count == 41
    assert result.company_canvas.areas == []
    assert result.company_canvas.product_lines == []


@pytest.mark.asyncio
async def test_read_requires_strategy_read_permission() -> None:
    organization_id, project_id = uuid4(), uuid4()
    service = build_service(canvases=[], arguments=[], areas=[])
    await run(service, organization_id, project_id)

    assert (
        service._authorization.require_project.await_args.kwargs["permission"]
        is PermissionCode.STRATEGY_READ
    )


@pytest.mark.asyncio
async def test_sub_areas_recurse_to_arbitrary_depth() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    root = area(company, "Duties & Taxes")
    level2 = area(company, "Landed cost", parent_id=root.id)
    level3 = area(company, "Item-level", parent_id=level2.id)
    level4 = area(company, "HS codes", parent_id=level3.id)
    service = build_service(
        canvases=[company],
        arguments=[],
        areas=[level4, level2, root, level3],  # deliberately unordered
        card_counts={level4.id: 2},
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    tree = result.company_canvas.areas
    assert [node.name for node in tree] == ["Duties & Taxes"]
    assert [node.name for node in tree[0].children] == ["Landed cost"]
    assert [node.name for node in tree[0].children[0].children] == ["Item-level"]
    deepest = tree[0].children[0].children[0].children
    assert [node.name for node in deepest] == ["HS codes"]
    assert deepest[0].card_count == 2


@pytest.mark.asyncio
async def test_counts_are_kept_demand_and_all_card_states_for_this_area_only() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    parent = area(company, "Duties & Taxes")
    child = area(company, "Landed cost", parent_id=parent.id)
    service = build_service(
        canvases=[company],
        arguments=[],
        areas=[parent, child],
        demand_counts={child.id: 412},
        card_counts={child.id: 4},
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    parent_node = result.company_canvas.areas[0]
    child_node = parent_node.children[0]
    # Counts are never rolled up from sub-areas.
    assert (parent_node.demand_count, parent_node.card_count) == (0, 0)
    assert (child_node.demand_count, child_node.card_count) == (412, 4)

    kept_filter = service.repository.get_kept_demand_counts_by_area
    kept_filter.assert_awaited_once_with(organization_id, project_id)
    service.repository.get_card_state_counts_by_area.assert_awaited_once_with(
        organization_id, project_id
    )


@pytest.mark.parametrize(
    ("demand", "cards", "expected_gap"),
    [
        (61, 0, True),  # known demand, no content
        (0, 0, False),  # nothing asked for, nothing missing
        (61, 5, False),  # demand covered
        (0, 5, False),  # content without demand is not a gap
    ],
)
@pytest.mark.asyncio
async def test_content_gap_is_demand_with_zero_cards(
    demand: int, cards: int, expected_gap: bool
) -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    leaf = area(company, "Returns and refunds of duty")
    service = build_service(
        canvases=[company],
        arguments=[],
        areas=[leaf],
        demand_counts={leaf.id: demand} if demand else {},
        card_counts={leaf.id: cards} if cards else {},
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    assert result.company_canvas.areas[0].content_gap is expected_gap


@pytest.mark.asyncio
async def test_card_count_includes_every_state() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    target = area(company, "Landed cost")
    breakdown = {
        "backlog": 1,
        "planned": 1,
        "drafting": 1,
        "qa_passed": 1,
        "approved": 1,
        "live": 1,
    }
    service = build_service(
        canvases=[company], arguments=[], areas=[target], card_states={target.id: breakdown}
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    node = result.company_canvas.areas[0]
    assert node.card_count == 6
    assert node.card_states == breakdown
    # Narrowing by state reads the breakdown; the default total stays all states.
    produced = {k: v for k, v in node.card_states.items() if k in ("approved", "live")}
    assert sum(produced.values()) == 2
    assert node.card_count == 6


@pytest.mark.asyncio
async def test_parent_with_content_below_shows_descendant_states_not_a_gap() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    parent = area(company, "Duties & Taxes")
    child_a = area(company, "A planned", parent_id=parent.id)
    child_b = area(company, "B drafting", parent_id=parent.id)
    child_c = area(company, "C in review", parent_id=parent.id)
    grandchild = area(company, "C1 planned", parent_id=child_c.id)
    service = build_service(
        canvases=[company],
        arguments=[],
        areas=[parent, child_a, child_b, child_c, grandchild],
        # The parent has demand of its own but no card attached directly.
        demand_counts={parent.id: 61},
        card_states={
            child_a.id: {"planned": 1},
            child_b.id: {"drafting": 1},
            child_c.id: {"qa_passed": 1},
            grandchild.id: {"planned": 2},
        },
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    parent_node = result.company_canvas.areas[0]
    assert parent_node.card_count == 0
    assert parent_node.content_gap is False
    # Every state below is shown as it is: summed, not collapsed into one status.
    assert parent_node.descendant_card_states == {"planned": 3, "drafting": 1, "qa_passed": 1}
    child_c_node = next(n for n in parent_node.children if n.name == "C in review")
    assert child_c_node.descendant_card_states == {"planned": 2}


@pytest.mark.asyncio
async def test_parent_with_demand_and_no_content_anywhere_below_is_a_gap() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    parent = area(company, "Duties & Taxes")
    child = area(company, "Landed cost", parent_id=parent.id)
    service = build_service(
        canvases=[company], arguments=[], areas=[parent, child], demand_counts={parent.id: 61}
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    parent_node = result.company_canvas.areas[0]
    assert parent_node.descendant_card_states == {}
    assert parent_node.content_gap is True
    assert parent_node.children[0].content_gap is False  # no demand of its own


@pytest.mark.asyncio
async def test_unmapped_area_sorts_last_and_is_never_a_content_gap() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    unmapped = area(company, "Unmapped")
    zebra = area(company, "Zebra area")
    alpha = area(company, "Alpha area")
    service = build_service(
        canvases=[company],
        arguments=[],
        areas=[unmapped, zebra, alpha],
        card_counts={unmapped.id: 37},
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    nodes = result.company_canvas.areas
    assert [node.name for node in nodes] == ["Alpha area", "Zebra area", "Unmapped"]
    assert nodes[-1].is_unmapped is True
    assert nodes[-1].content_gap is False


@pytest.mark.asyncio
async def test_unmapped_area_with_zero_cards_still_has_no_coral_chip() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    unmapped = area(company, "  unmapped  ")  # matched case-insensitively, trimmed
    service = build_service(
        canvases=[company], arguments=[], areas=[unmapped], demand_counts={unmapped.id: 12}
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    node = result.company_canvas.areas[0]
    assert node.is_unmapped is True
    assert node.card_count == 0
    assert node.content_gap is False  # demand, zero cards, still exempt


@pytest.mark.asyncio
async def test_default_argument_pillar_surfaces_for_the_teal_chip() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    pillar_argument = argument(company, 0, pillar="Item-level landed cost")
    tagged = area(company, "Landed cost", default_argument_id=pillar_argument.id)
    untagged = area(company, "Deemed supplier / IOSS")
    service = build_service(
        canvases=[company],
        arguments=[pillar_argument],
        areas=[tagged, untagged],
        card_counts={tagged.id: 4, untagged.id: 3},
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    by_name = {node.name: node for node in result.company_canvas.areas}
    assert by_name["Landed cost"].default_argument_pillar == "Item-level landed cost"
    assert by_name["Deemed supplier / IOSS"].default_argument_pillar is None


@pytest.mark.asyncio
async def test_inheritance_summary_renders_inherits_override_and_adds() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    a1 = argument(company, 0)
    a2 = argument(company, 1)
    a3 = argument(company, 2)

    duties = canvas(
        organization_id, project_id, parent_id=company.id, product_line="Duties & Taxes"
    )
    duties_inherits_a1 = argument(duties, 0, inherited_from=a1.id)
    duties_adds = argument(duties, 1)

    localization = canvas(
        organization_id, project_id, parent_id=company.id, product_line="Localization"
    )
    localization_inherits_a2 = argument(localization, 0, inherited_from=a2.id)
    localization_override = argument(localization, 1, inherited_from=a3.id, override=True)

    service = build_service(
        canvases=[company, duties, localization],
        arguments=[
            a1,
            a2,
            a3,
            duties_inherits_a1,
            duties_adds,
            localization_inherits_a2,
            localization_override,
        ],
        areas=[],
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    lines = {node.name: node for node in result.company_canvas.product_lines}

    assert lines["Duties & Taxes"].inherits == ["A1"]
    assert lines["Duties & Taxes"].override_count == 0
    # The company canvas holds A1 to A3, so a child's own argument continues at A4.
    assert lines["Duties & Taxes"].adds == ["A4"]

    assert lines["Localization"].inherits == ["A2"]
    assert lines["Localization"].override_count == 1
    # An overridden argument is counted, not listed as carried unchanged.
    assert lines["Localization"].adds == []

    # The company canvas itself never carries an inheritance summary.
    assert result.company_canvas.inherits == []
    assert result.company_canvas.adds == []
    assert result.company_canvas.override_count == 0


@pytest.mark.asyncio
async def test_areas_attach_to_the_canvas_that_owns_them() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    line = canvas(organization_id, project_id, parent_id=company.id, product_line="Localization")
    company_area = area(company, "Company-level area")
    line_area = area(line, "Translation")
    service = build_service(
        canvases=[company, line],
        arguments=[],
        areas=[company_area, line_area],
        card_counts={company_area.id: 1, line_area.id: 8},
    )
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    assert [node.name for node in result.company_canvas.areas] == ["Company-level area"]
    assert [node.name for node in result.company_canvas.product_lines[0].areas] == ["Translation"]


@pytest.mark.asyncio
async def test_cards_without_an_area_are_reported_not_hidden() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    service = build_service(canvases=[company], arguments=[], areas=[], unassigned=37)
    result = await run(service, organization_id, project_id)

    assert result.unassigned_card_count == 37


@pytest.mark.asyncio
async def test_area_parent_cycle_does_not_hang_assembly() -> None:
    organization_id, project_id = uuid4(), uuid4()
    company = canvas(organization_id, project_id)
    first = area(company, "First")
    second = area(company, "Second", parent_id=first.id)
    first.parent_id = second.id  # a cycle the FK alone does not prevent
    service = build_service(canvases=[company], arguments=[], areas=[first, second])
    result = await run(service, organization_id, project_id)

    assert result.company_canvas is not None
    # Neither area is a root of the canvas, so the cycle yields no rows rather than
    # recursing forever.
    assert result.company_canvas.areas == []
