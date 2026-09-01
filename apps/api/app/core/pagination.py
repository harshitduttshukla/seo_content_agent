"""Application-level pagination result."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageResult[ItemT]:
    items: list[ItemT]
    next_cursor: str | None
    has_more: bool
