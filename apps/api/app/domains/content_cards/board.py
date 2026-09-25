"""V3 Content Hub plan board rules (handoff §5.1, §5.2). Pure, no I/O.

The board's seven columns are a projection of the card state machine: several
states share a column, and no column has a state of its own. The only moves the
board may make are Backlog ↔ Planned; every other transition belongs to
Production and is refused here even when the state machine would allow it.
"""

from enum import StrEnum

from app.core.errors import ConflictError
from app.domains.content_cards.schemas import VALID_STATE_TRANSITIONS, ContentCardState


class BoardColumn(StrEnum):
    BACKLOG = "backlog"
    PLANNED = "planned"
    OUTLINE = "outline"
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    LIVE = "live"


class ColumnTone(StrEnum):
    """§5.1 colour semantics: grey rests, teal is the system, coral is a human."""

    REST = "rest"
    SYSTEM = "system"
    HUMAN = "human"


BOARD_COLUMNS: tuple[tuple[BoardColumn, str, ColumnTone], ...] = (
    (BoardColumn.BACKLOG, "Backlog", ColumnTone.REST),
    (BoardColumn.PLANNED, "Planned", ColumnTone.REST),
    (BoardColumn.OUTLINE, "Outline", ColumnTone.SYSTEM),
    (BoardColumn.DRAFT, "Draft", ColumnTone.SYSTEM),
    (BoardColumn.REVIEW, "Review", ColumnTone.HUMAN),
    (BoardColumn.APPROVED, "Approved", ColumnTone.REST),
    (BoardColumn.LIVE, "Live", ColumnTone.REST),
)

STATE_COLUMN: dict[ContentCardState, BoardColumn] = {
    ContentCardState.BACKLOG: BoardColumn.BACKLOG,
    ContentCardState.PLANNED: BoardColumn.PLANNED,
    ContentCardState.BUNDLED: BoardColumn.PLANNED,
    ContentCardState.OUTLINED: BoardColumn.OUTLINE,
    ContentCardState.DRAFTING: BoardColumn.DRAFT,
    ContentCardState.QA_FAILED: BoardColumn.DRAFT,
    ContentCardState.QA_PASSED: BoardColumn.REVIEW,
    ContentCardState.APPROVED: BoardColumn.APPROVED,
    ContentCardState.LIVE: BoardColumn.LIVE,
}

# States whose cards the Planned column orders by ``priority``.
PLANNED_COLUMN_STATES: frozenset[ContentCardState] = frozenset(
    state for state, column in STATE_COLUMN.items() if column is BoardColumn.PLANNED
)

# §5.1 "Drag is allowed Backlog ↔ Planned": the only transitions the board exposes.
BOARD_TRANSITIONS: frozenset[tuple[ContentCardState, ContentCardState]] = frozenset(
    {
        (ContentCardState.BACKLOG, ContentCardState.PLANNED),
        (ContentCardState.PLANNED, ContentCardState.BACKLOG),
    }
)


def column_for_state(state: str) -> BoardColumn:
    """The one column a stored state belongs to. Unknown states are a data error."""
    return STATE_COLUMN[ContentCardState(state)]


def require_valid_transition(current: str, target: ContentCardState) -> None:
    """Refuse any move the §5.2 state machine does not list. The single check."""
    allowed = VALID_STATE_TRANSITIONS.get(ContentCardState(current), [])
    if target not in allowed:
        raise ConflictError(
            "INVALID_STATE_TRANSITION",
            f"A card cannot move from {current} to {target}.",
            details={"current_state": current, "target_state": str(target)},
        )


def require_board_transition(current: str, target: ContentCardState) -> None:
    """The board's narrower rule: only Backlog ↔ Planned, and legal per §5.2."""
    if (ContentCardState(current), target) not in BOARD_TRANSITIONS:
        raise ConflictError(
            "BOARD_MOVE_NOT_ALLOWED",
            "The board only moves cards between Backlog and Planned.",
            details={"current_state": current, "target_state": str(target)},
        )
    require_valid_transition(current, target)


def market_code(market: dict[str, object] | None) -> str | None:
    """``{"lang": "en", "country": "GB"}`` → ``"en-GB"``; missing parts → None."""
    if not market:
        return None
    lang, country = market.get("lang"), market.get("country")
    if not isinstance(lang, str) or not isinstance(country, str) or not lang or not country:
        return None
    return f"{lang}-{country}"
