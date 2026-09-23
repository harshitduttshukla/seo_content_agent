"""Unit tests for the deterministic Plan rules (V3 §4.5)."""

from uuid import UUID, uuid4

from app.domains.canvas.schemas import WorkspaceConfig
from app.domains.demand.models import DemandNode
from app.domains.demand.planning import (
    DEFERRED_CASES,
    SKIP_ALREADY_CARDED,
    SKIP_NO_AREA,
    SKIP_NOT_FOUND,
    Plan,
    PlanGroup,
    build_plan,
    card_market,
    primary_fields,
)

AREA_A = UUID("00000000-0000-0000-0000-00000000000a")
AREA_B = UUID("00000000-0000-0000-0000-00000000000b")


def node(
    text: str,
    *,
    score: float | None = 0.5,
    volume: int | None = 100,
    status: str = "kept",
    area_id: UUID | None = AREA_A,
    country: str | None = "IN",
    funnel: str | None = None,
    competitors: list[str] | None = None,
    node_type: str = "keyword",
    node_id: UUID | None = None,
) -> DemandNode:
    return DemandNode(
        id=node_id or uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        type=node_type,
        text=text,
        volume=volume,
        country=country,
        area_id=area_id,
        funnel=funnel,
        status=status,
        score=score,
        competitor_ids=[],
        competitor_names=competitors or [],
        origin="upload",
    )


def plan_for(
    nodes: list[DemandNode],
    *,
    config: WorkspaceConfig | None = None,
    carded: tuple[UUID, ...] = (),
) -> Plan:
    return build_plan([n.id for n in nodes], nodes, set(carded), config or WorkspaceConfig())


def kinds(group: PlanGroup) -> list[tuple[str, str]]:
    return [(card.kind.value, card.node.text) for card in group.cards]


def test_only_kept_nodes_are_planned_and_discarded_are_skipped() -> None:
    kept = node("kept")
    discarded = node("discarded", status="discarded")
    pending = node("pending", status="pending")
    plan = plan_for([kept, discarded, pending])

    assert plan.selected_count == 3
    assert plan.eligible_count == 1
    assert kinds(plan.groups[0]) == [("pillar", "kept")]
    reasons = {skip.node.text: skip.reason for skip in plan.skipped if skip.node}
    assert reasons["discarded"] == "Status is discarded; only kept nodes are planned."
    assert reasons["pending"] == "Status is pending; only kept nodes are planned."


def test_area_and_market_are_planned_independently() -> None:
    india = node("ev charging india", country="IN", score=0.9)
    usa = node("ev charging usa", country="US", score=0.4)
    other_area = node("fleet software", area_id=AREA_B, country="IN", score=0.7)
    plan = plan_for([india, usa, other_area])

    by_key = {(g.area_id, g.country): kinds(g) for g in plan.groups}
    assert by_key == {
        (AREA_A, "IN"): [("pillar", "ev charging india")],
        (AREA_A, "US"): [("pillar", "ev charging usa")],
        (AREA_B, "IN"): [("pillar", "fleet software")],
    }


def test_highest_score_is_pillar_rest_split_by_the_configured_floor() -> None:
    config = WorkspaceConfig.model_validate({"cluster_volume_floor": 300})
    top = node("top", score=0.9, volume=50)
    big = node("big", score=0.5, volume=300)  # at the floor → cluster
    small = node("small", score=0.8, volume=299)  # below → secondary
    unknown = node("unknown volume", score=0.7, volume=None)  # missing → secondary
    plan = plan_for([small, big, top, unknown], config=config)

    group = plan.groups[0]
    assert kinds(group) == [("pillar", "top"), ("cluster", "big")]
    assert [n.text for n in group.cards[0].secondary_nodes] == ["small", "unknown volume"]


def test_cluster_floor_comes_from_workspace_config_not_a_constant() -> None:
    nodes = [node("top", score=0.9), node("mid", score=0.5, volume=100)]
    low_floor = plan_for(
        nodes, config=WorkspaceConfig.model_validate({"cluster_volume_floor": 100})
    )
    high_floor = plan_for(
        nodes, config=WorkspaceConfig.model_validate({"cluster_volume_floor": 101})
    )

    assert kinds(low_floor.groups[0]) == [("pillar", "top"), ("cluster", "mid")]
    assert kinds(high_floor.groups[0]) == [("pillar", "top")]
    assert [n.text for n in high_floor.groups[0].cards[0].secondary_nodes] == ["mid"]


def test_ties_break_on_volume_then_node_id_and_are_stable() -> None:
    first = node("a", score=0.5, volume=100, node_id=UUID(int=1))
    second = node("b", score=0.5, volume=100, node_id=UUID(int=2))
    louder = node("c", score=0.5, volume=500, node_id=UUID(int=3))

    for order in ([first, second, louder], [louder, second, first], [second, louder, first]):
        plan = plan_for(order)
        # Equal score: higher volume wins; equal volume: lower id wins.
        assert kinds(plan.groups[0])[0] == ("pillar", "c")
        assert [c.node.text for c in plan.groups[0].cards[1:]] == ["a", "b"]


def test_missing_score_ranks_last() -> None:
    unscored = node("unscored", score=None, volume=10_000)
    scored = node("scored", score=0.1, volume=10)
    assert kinds(plan_for([unscored, scored]).groups[0])[0] == ("pillar", "scored")


def test_top_competitor_linked_bofu_is_compare_and_next_node_is_pillar() -> None:
    node_a = node("a vs rival", score=100, funnel="bofu", competitors=["Rival"])
    node_b = node("b normal", score=90)
    plan = plan_for([node_a, node_b])

    assert kinds(plan.groups[0]) == [("pillar", "b normal"), ("compare", "a vs rival")]
    primaries = [card.node.id for card in plan.groups[0].cards]
    assert len(primaries) == len(set(primaries))  # node A produced one card, not two


def test_every_competitor_linked_bofu_node_is_compare_whatever_its_volume() -> None:
    pillar = node("pillar", score=0.9)
    low_volume_compare = node("x vs y", score=0.2, volume=5, funnel="bofu", competitors=["Y"])
    bofu_without_competitor = node("bofu plain", score=0.1, volume=5, funnel="bofu")
    competitor_not_bofu = node("mofu vs", score=0.1, volume=5, funnel="mofu", competitors=["Y"])
    plan = plan_for([pillar, low_volume_compare, bofu_without_competitor, competitor_not_bofu])

    group = plan.groups[0]
    assert kinds(group) == [("pillar", "pillar"), ("compare", "x vs y")]
    assert sorted(n.text for n in group.cards[0].secondary_nodes) == ["bofu plain", "mofu vs"]


def test_group_of_only_compare_nodes_has_no_pillar() -> None:
    only = node("a vs b", funnel="bofu", competitors=["B"])
    assert kinds(plan_for([only]).groups[0]) == [("compare", "a vs b")]


def test_already_carded_missing_and_arealess_nodes_are_skipped_with_reasons() -> None:
    carded = node("carded")
    arealess = node("no area", area_id=None)
    fresh = node("fresh")
    missing_id = uuid4()
    plan = build_plan(
        [carded.id, arealess.id, fresh.id, missing_id],
        [carded, arealess, fresh],
        {carded.id},
        WorkspaceConfig(),
    )

    assert {skip.node_id: skip.reason for skip in plan.skipped} == {
        carded.id: SKIP_ALREADY_CARDED,
        arealess.id: SKIP_NO_AREA,
        missing_id: SKIP_NOT_FOUND,
    }
    assert kinds(plan.groups[0]) == [("pillar", "fresh")]


def test_duplicate_ids_in_the_selection_count_once() -> None:
    only = node("only")
    plan = build_plan([only.id, only.id], [only], set(), WorkspaceConfig())
    assert plan.selected_count == 1
    assert len(plan.groups[0].cards) == 1


def test_word_budgets_come_from_workspace_config() -> None:
    config = WorkspaceConfig.model_validate(
        {
            "word_budgets": {"pillar": 2500, "cluster": 900, "compare": 1200},
            "cluster_volume_floor": 0,
        }
    )
    plan = plan_for(
        [
            node("pillar", score=0.9),
            node("cluster", score=0.5),
            node("compare", score=0.1, funnel="bofu", competitors=["Z"]),
        ],
        config=config,
    )
    assert {card.kind.value: card.word_budget for card in plan.groups[0].cards} == {
        "pillar": 2500,
        "cluster": 900,
        "compare": 1200,
    }


def test_refresh_and_dual_primary_are_reported_as_deferred_never_produced() -> None:
    keyword = node("ev charging", score=0.9)
    prompt = node("which ev charger is best", score=0.8, node_type="prompt", volume=None)
    plan = plan_for([keyword, prompt])

    assert plan.deferred == DEFERRED_CASES
    assert all(card.kind.value != "refresh" for group in plan.groups for card in group.cards)
    # No merge: the prompt is not folded into the keyword's card as a co-primary.
    assert [n.text for n in plan.groups[0].cards[0].secondary_nodes] == ["which ev charger is best"]


def test_market_uses_the_node_country_and_configured_language_only() -> None:
    config = WorkspaceConfig.model_validate({"markets": [{"lang": "en", "country": "IN"}]})
    assert card_market("IN", config) == {"country": "IN", "lang": "en"}
    assert card_market("US", config) == {"country": "US"}  # no language invented
    assert card_market(None, config) == {}


def test_prompt_nodes_fill_the_prompt_primary_slot() -> None:
    keyword = node("kw")
    prompt = node("pr", node_type="prompt")
    assert primary_fields(keyword) == {"primary_demand_id": keyword.id, "primary_prompt_id": None}
    assert primary_fields(prompt) == {"primary_demand_id": None, "primary_prompt_id": prompt.id}
