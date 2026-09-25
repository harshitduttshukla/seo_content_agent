"""Unit tests for the V3 Content Hub board rules and card projection (§5.1, §5.2)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from app.core.errors import ConflictError
from app.domains.content_cards.board import (
    BOARD_COLUMNS,
    BoardColumn,
    column_for_state,
    market_code,
    require_board_transition,
    require_valid_transition,
)
from app.domains.content_cards.hub_service import (
    board_card,
    filter_options,
    transition_content_card,
)
from app.domains.content_cards.models import ContentCard
from app.domains.content_cards.repository import BoardFacet, BoardRow
from app.domains.content_cards.schemas import ContentCardState

LOCK = datetime(2026, 9, 24, 10, 0, tzinfo=UTC)


def _card(**overrides: Any) -> ContentCard:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "project_id": uuid4(),
        "kind": "cluster",
        "state": "planned",
        "origin": "plan",
        "title": "Card",
        "market": {"lang": "en", "country": "GB"},
        "secondary_demand_ids": [],
        "stale_claims": [],
        "priority": 1,
        "revision": 1,
        "updated_at": LOCK,
    }
    values.update(overrides)
    planned_at = values.pop("planned_at", None)
    card = ContentCard(**values)
    card.planned_at = planned_at  # after construction, overriding the listener's stamp
    return card


def _row(card: ContentCard, **overrides: Any) -> BoardRow:
    values: dict[str, Any] = {
        "card": card,
        "area_name": None,
        "argument_name": None,
        "owner_name": None,
        "demand_text": None,
        "demand_volume": None,
        "demand_score": None,
        "prompt_text": None,
        "prompt_score": None,
        "prompt_citation_gap": None,
        "prompt_platforms": None,
    }
    values.update(overrides)
    return BoardRow(**values)


@pytest.mark.parametrize(
    ("state", "column"),
    [
        ("backlog", BoardColumn.BACKLOG),
        ("planned", BoardColumn.PLANNED),
        ("bundled", BoardColumn.PLANNED),
        ("outlined", BoardColumn.OUTLINE),
        ("drafting", BoardColumn.DRAFT),
        ("qa_failed", BoardColumn.DRAFT),
        ("qa_passed", BoardColumn.REVIEW),
        ("approved", BoardColumn.APPROVED),
        ("live", BoardColumn.LIVE),
    ],
)
def test_every_state_maps_to_exactly_one_column(state: str, column: BoardColumn) -> None:
    assert column_for_state(state) is column


def test_qa_passed_is_review_and_qa_failed_is_draft() -> None:
    assert column_for_state("qa_passed") is BoardColumn.REVIEW
    assert column_for_state("qa_failed") is BoardColumn.DRAFT


def test_the_board_has_seven_columns_in_state_machine_order_with_their_tones() -> None:
    assert [(key.value, label, tone.value) for key, label, tone in BOARD_COLUMNS] == [
        ("backlog", "Backlog", "rest"),
        ("planned", "Planned", "rest"),
        ("outline", "Outline", "system"),
        ("draft", "Draft", "system"),
        ("review", "Review", "human"),
        ("approved", "Approved", "rest"),
        ("live", "Live", "rest"),
    ]


def test_unknown_state_is_a_data_error() -> None:
    with pytest.raises(ValueError):
        column_for_state("review")


@pytest.mark.parametrize(
    ("current", "target"),
    [("backlog", ContentCardState.PLANNED), ("planned", ContentCardState.BACKLOG)],
)
def test_board_allows_backlog_and_planned_moves(current: str, target: ContentCardState) -> None:
    require_board_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("backlog", ContentCardState.LIVE),
        ("backlog", ContentCardState.DRAFTING),
        ("planned", ContentCardState.DRAFTING),
        ("planned", ContentCardState.APPROVED),
        ("planned", ContentCardState.BUNDLED),  # legal in §5.2, but Production's move
        ("drafting", ContentCardState.APPROVED),
        ("approved", ContentCardState.LIVE),
        ("bundled", ContentCardState.BACKLOG),
        ("backlog", ContentCardState.BACKLOG),
        ("planned", ContentCardState.PLANNED),
    ],
)
def test_board_refuses_every_other_move(current: str, target: ContentCardState) -> None:
    with pytest.raises(ConflictError) as raised:
        require_board_transition(current, target)
    assert raised.value.code == "BOARD_MOVE_NOT_ALLOWED"


def test_state_machine_refuses_an_unlisted_transition() -> None:
    with pytest.raises(ConflictError) as raised:
        require_valid_transition("backlog", ContentCardState.LIVE)
    assert raised.value.code == "INVALID_STATE_TRANSITION"
    require_valid_transition("qa_passed", ContentCardState.APPROVED)


def test_transition_sets_state_bumps_revision_and_stamps_entry_into_planned() -> None:
    card = _card(state="backlog", revision=3)
    transition_content_card(card, ContentCardState.PLANNED)
    assert card.state == "planned"
    assert card.revision == 4
    assert card.planned_at is not None  # the listener's now() expression


def test_transition_refuses_illegal_target_and_changes_nothing() -> None:
    card = _card(state="backlog", revision=3)
    with pytest.raises(ConflictError):
        transition_content_card(card, ContentCardState.APPROVED)
    assert (card.state, card.revision) == ("backlog", 3)


@pytest.mark.parametrize(
    ("planned_at", "locked_at", "new"),
    [
        (LOCK + timedelta(seconds=1), None, False),  # unlocked
        (None, LOCK, False),  # never stamped
        (LOCK - timedelta(seconds=1), LOCK, False),
        (LOCK, LOCK, False),  # equality is not new
        (LOCK + timedelta(microseconds=1), LOCK, True),
    ],
)
def test_new_chip_uses_planned_at_strictly_after_the_lock(
    planned_at: datetime | None, locked_at: datetime | None, new: bool
) -> None:
    card = _card(planned_at=planned_at)
    assert board_card(_row(card), locked_at).is_new_after_plan_lock is new


def test_new_chip_ignores_created_at() -> None:
    # Created well before the lock, planned after it: new.
    card = _card(created_at=LOCK - timedelta(days=30), planned_at=LOCK + timedelta(hours=1))
    assert board_card(_row(card), LOCK).is_new_after_plan_lock is True
    # Created after the lock but planned before it (impossible order, still planned_at wins).
    card = _card(created_at=LOCK + timedelta(days=1), planned_at=LOCK - timedelta(hours=1))
    assert board_card(_row(card), LOCK).is_new_after_plan_lock is False


def test_new_chip_only_appears_in_the_planned_column() -> None:
    card = _card(state="outlined", planned_at=LOCK + timedelta(hours=1))
    assert board_card(_row(card), LOCK).is_new_after_plan_lock is False


def test_card_face_projects_stored_and_joined_data_without_inventing_any() -> None:
    area_id, argument_id, demand_id, prompt_id = uuid4(), uuid4(), uuid4(), uuid4()
    card = _card(
        area_id=area_id,
        argument_id=argument_id,
        primary_demand_id=demand_id,
        primary_prompt_id=prompt_id,
        secondary_demand_ids=[str(uuid4()), str(uuid4())],
        stale_claims=[{"claim_id": "CLM-021"}],
        state="qa_passed",
    )
    face = board_card(
        _row(
            card,
            area_name="Landed cost",
            argument_name="Deemed supplier",
            demand_text="landed cost",
            demand_volume=390,
            demand_score=None,
            prompt_text="who handles duties",
            prompt_score=3.0,
            prompt_citation_gap=1.0,
            prompt_platforms=["chatgpt", "perplexity", "gemini"],
        ),
        None,
    )
    assert face.column == "review"
    assert face.market == "en-GB"
    assert face.area is not None and face.area.name == "Landed cost"
    assert face.argument is not None and face.argument.name == "Deemed supplier"
    assert face.owner is None  # no owner stored → none shown
    assert face.primary_demand is not None and face.primary_demand.volume == 390
    assert face.primary_prompt is not None and face.primary_prompt.platform_count == 3
    assert face.score == 3.0  # demand unscored → prompt score
    assert face.secondary_demand_count == 2
    assert face.stale_claim_count == 1
    assert face.has_qa_report is False


def test_market_code_needs_both_parts() -> None:
    assert market_code({"lang": "fr", "country": "FR"}) == "fr-FR"
    assert market_code({"lang": "fr"}) is None
    assert market_code({}) is None


def test_filter_options_are_distinct_and_sorted() -> None:
    area_a, area_b, owner = uuid4(), uuid4(), uuid4()
    facets = [
        BoardFacet(area_b, "Translation", None, None, owner, "Patrice", "compare", {}),
        BoardFacet(
            area_a, "Landed cost", None, None, owner, "Patrice", "cluster",
            {"lang": "en", "country": "GB"},
        ),
        BoardFacet(
            area_a, "Landed cost", None, None, None, None, "cluster",
            {"lang": "fr", "country": "FR"},
        ),
    ]  # fmt: skip
    options = filter_options(facets)
    assert [area.name for area in options.areas] == ["Landed cost", "Translation"]
    assert [owner.name for owner in options.owners] == ["Patrice"]
    assert options.kinds == ["cluster", "compare"]
    assert options.markets == ["en-GB", "fr-FR"]
    assert options.arguments == []
