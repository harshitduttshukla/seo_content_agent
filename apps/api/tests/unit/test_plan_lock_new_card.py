"""The "new" chip rule for cards added after the plan was locked (V3 §5.1)."""

from datetime import UTC, datetime, timedelta

from app.domains.projects.service import is_added_after_plan_lock

LOCKED_AT = datetime(2026, 9, 24, 10, 0, tzinfo=UTC)


def test_card_created_before_or_at_the_lock_is_not_new() -> None:
    assert is_added_after_plan_lock(LOCKED_AT - timedelta(seconds=1), LOCKED_AT) is False
    assert is_added_after_plan_lock(LOCKED_AT, LOCKED_AT) is False


def test_card_created_after_the_lock_is_new() -> None:
    assert is_added_after_plan_lock(LOCKED_AT + timedelta(microseconds=1), LOCKED_AT) is True


def test_nothing_is_new_before_the_plan_is_locked() -> None:
    assert is_added_after_plan_lock(LOCKED_AT, None) is False
