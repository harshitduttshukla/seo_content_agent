"""Deterministic Plan rules: kept demand nodes → planned content cards (V3 §4.5).

This module decides; it never reads or writes the database and never calls a
model. Scores, areas, funnels and competitor links are read exactly as stored —
the external pipeline produced them, and Plan does not recompute any of them.

Rules, applied per (area_id, market) group:

1. Every competitor-linked BOFU node (``funnel == "bofu"`` and at least one
   competitor id or name) becomes a ``compare`` card.
   Implementation rule for this pass, not stated in the handoff: specialised
   intent takes precedence, so when the top-scoring node is competitor-linked
   BOFU it becomes the compare card and the pillar is the next node.
2. The highest-ranked remaining node becomes the ``pillar`` card.
3. Remaining nodes with ``volume >= cluster_volume_floor`` become ``cluster``
   cards.
4. Remaining nodes below the floor (a missing volume counts as below) are
   attached to the pillar's ``secondary_demand_ids``.

Ranking, used for every "highest" decision:
    score descending (missing score last), then volume descending (missing
    volume last), then node id ascending as the stable final tie-break.

Deferred, because no stored deterministic signal exists yet:
    - refresh cards (a node's "best match" to an imported card)
    - dual-primary keyword + prompt merging (no "same intent" link)
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.domains.canvas.schemas import WorkspaceConfig
from app.domains.content_cards.models import ContentCardKind
from app.domains.demand.models import DemandNode, DemandNodeStatus, DemandNodeType

DEFERRED_CASES: tuple[str, ...] = (
    "Refresh cards are not created: no stored signal links a demand node to its "
    "best-matching imported card.",
    "Keyword + prompt dual-primary cards are not merged: no stored signal says two "
    "nodes share an intent.",
)

SKIP_NOT_FOUND = "Not found in this project."
SKIP_ALREADY_CARDED = "DemandNode already has ContentCard."
SKIP_NO_AREA = "No area assigned; Plan groups by area."


def skip_not_kept(status: str) -> str:
    return f"Status is {status}; only kept nodes are planned."


@dataclass(frozen=True)
class PlannedCard:
    kind: ContentCardKind
    node: DemandNode
    secondary_nodes: tuple[DemandNode, ...]
    word_budget: int


@dataclass(frozen=True)
class PlanGroup:
    area_id: UUID
    country: str | None
    cards: tuple[PlannedCard, ...]


@dataclass(frozen=True)
class Skip:
    node_id: UUID
    node: DemandNode | None
    reason: str


@dataclass(frozen=True)
class Plan:
    selected_count: int
    eligible_count: int
    groups: tuple[PlanGroup, ...]
    skipped: tuple[Skip, ...]
    deferred: tuple[str, ...] = field(default=DEFERRED_CASES)


def rank_key(node: DemandNode) -> tuple[bool, float, bool, int, str]:
    """Score desc, volume desc (missing values last), then id asc."""
    return (
        node.score is None,
        -(node.score or 0.0),
        node.volume is None,
        -(node.volume or 0),
        str(node.id),
    )


def is_competitor_linked_bofu(node: DemandNode) -> bool:
    return node.funnel == "bofu" and bool(node.competitor_ids or node.competitor_names)


def build_plan(
    selected_ids: Sequence[UUID],
    nodes: Iterable[DemandNode],
    carded_ids: set[UUID],
    config: WorkspaceConfig,
) -> Plan:
    """Turn a selection into a plan. Pure: same inputs, same plan."""
    unique_ids = list(dict.fromkeys(selected_ids))
    by_id = {node.id: node for node in nodes}
    skipped: list[Skip] = []
    groups: dict[tuple[UUID, str | None], list[DemandNode]] = {}

    for node_id in unique_ids:
        node = by_id.get(node_id)
        if node is None:
            skipped.append(Skip(node_id, None, SKIP_NOT_FOUND))
        elif node.status != DemandNodeStatus.KEPT:
            skipped.append(Skip(node_id, node, skip_not_kept(node.status)))
        elif node.id in carded_ids:
            skipped.append(Skip(node_id, node, SKIP_ALREADY_CARDED))
        elif node.area_id is None:
            skipped.append(Skip(node_id, node, SKIP_NO_AREA))
        else:
            groups.setdefault((node.area_id, node.country), []).append(node)

    planned = tuple(
        _plan_group(area_id, country, members, config)
        for (area_id, country), members in sorted(
            groups.items(), key=lambda item: (str(item[0][0]), item[0][1] or "")
        )
    )
    return Plan(
        selected_count=len(unique_ids),
        eligible_count=sum(len(members) for members in groups.values()),
        groups=planned,
        skipped=tuple(skipped),
    )


def _plan_group(
    area_id: UUID, country: str | None, members: list[DemandNode], config: WorkspaceConfig
) -> PlanGroup:
    budgets = config.word_budgets
    floor = config.cluster_volume_floor
    ranked = sorted(members, key=rank_key)

    compares = [node for node in ranked if is_competitor_linked_bofu(node)]
    rest = [node for node in ranked if not is_competitor_linked_bofu(node)]

    cards: list[PlannedCard] = []
    if rest:
        pillar, remainder = rest[0], rest[1:]
        clusters = [node for node in remainder if node.volume is not None and node.volume >= floor]
        secondaries = [node for node in remainder if node not in clusters]
        cards.append(
            PlannedCard(ContentCardKind.PILLAR, pillar, tuple(secondaries), budgets.pillar)
        )
        cards.extend(
            PlannedCard(ContentCardKind.CLUSTER, node, (), budgets.cluster) for node in clusters
        )
    cards.extend(
        PlannedCard(ContentCardKind.COMPARE, node, (), budgets.compare) for node in compares
    )
    return PlanGroup(area_id=area_id, country=country, cards=tuple(cards))


def card_market(country: str | None, config: WorkspaceConfig) -> dict[str, object]:
    """ContentCard.market from stored data only: the node's country, and the
    language of the workspace market configured for that country, if any."""
    if country is None:
        return {}
    market: dict[str, object] = {"country": country}
    for configured in config.markets:
        if configured.country.upper() == country.upper():
            market["lang"] = configured.lang
            break
    return market


def primary_fields(node: DemandNode) -> dict[str, UUID | None]:
    """A prompt node is a prompt primary; anything else is the demand primary."""
    if node.type == DemandNodeType.PROMPT:
        return {"primary_demand_id": None, "primary_prompt_id": node.id}
    return {"primary_demand_id": node.id, "primary_prompt_id": None}
