"""The "new" chip rule: a card entered Planned after the plan was locked (V3 §5.1)."""

from datetime import UTC, datetime, timedelta

from app.domains.content_cards.models import ContentCard, ContentCardState
from app.domains.projects.service import is_added_after_plan_lock
from sqlalchemy.sql.functions import now

LOCKED_AT = datetime(2026, 9, 24, 11, 0, tzinfo=UTC)


def test_planned_before_the_lock_is_not_new() -> None:
    assert is_added_after_plan_lock(LOCKED_AT - timedelta(hours=1), LOCKED_AT) is False


def test_planned_exactly_at_the_lock_is_not_new() -> None:
    assert is_added_after_plan_lock(LOCKED_AT, LOCKED_AT) is False


def test_planned_after_the_lock_is_new() -> None:
    assert is_added_after_plan_lock(LOCKED_AT + timedelta(microseconds=1), LOCKED_AT) is True


def test_nothing_is_new_without_a_lock() -> None:
    assert is_added_after_plan_lock(LOCKED_AT, None) is False


def test_a_card_never_stamped_is_not_new() -> None:
    assert is_added_after_plan_lock(None, LOCKED_AT) is False


def _card(state: str) -> ContentCard:
    return ContentCard(kind="cluster", state=state, origin="plan", title="t")


def test_constructing_a_planned_card_stamps_planned_at() -> None:
    assert isinstance(_card(ContentCardState.PLANNED).planned_at, now)


def test_constructing_a_non_planned_card_leaves_planned_at_empty() -> None:
    assert _card(ContentCardState.BACKLOG).planned_at is None
    assert _card(ContentCardState.LIVE).planned_at is None


def test_leaving_planned_keeps_planned_at() -> None:
    card = _card(ContentCardState.PLANNED)
    card.planned_at = LOCKED_AT
    card.state = ContentCardState.BUNDLED
    assert card.planned_at == LOCKED_AT


def test_setting_planned_on_a_planned_card_does_not_restamp() -> None:
    card = _card(ContentCardState.PLANNED)
    card.planned_at = LOCKED_AT
    card.state = ContentCardState.PLANNED
    assert card.planned_at == LOCKED_AT
