"""Search Analytics response → validated rows. Pure; no I/O.

Each API row is ``{"keys": [date, query, page], "clicks", "impressions", "ctr",
"position"}``. Rows that do not match are rejected with a reason and counted; they
are never silently dropped. Google omits anonymized queries from query-dimension
results, so an empty query string is kept as-is rather than invented.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True, slots=True)
class AnalyticsRow:
    date: date
    query: str
    page: str
    clicks: int
    impressions: int
    ctr: float
    position: float


@dataclass(frozen=True, slots=True)
class RejectedRow:
    reason: str
    raw: dict[str, Any]


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def normalize_row(raw: object, start: date, end: date) -> AnalyticsRow | RejectedRow:
    if not isinstance(raw, dict):
        return RejectedRow("not an object", {"value": repr(raw)[:200]})
    keys = raw.get("keys")
    if not isinstance(keys, list) or len(keys) != 3 or not all(isinstance(k, str) for k in keys):
        return RejectedRow("keys must be [date, query, page]", raw)
    day_text, query, page = keys
    try:
        day = date.fromisoformat(day_text)
    except ValueError:
        return RejectedRow("invalid date", raw)
    if not start <= day <= end:
        return RejectedRow("date outside the requested range", raw)
    parts = urlsplit(page)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return RejectedRow("page is not an absolute http(s) URL", raw)
    clicks, impressions = _number(raw.get("clicks")), _number(raw.get("impressions"))
    ctr, position = _number(raw.get("ctr")), _number(raw.get("position"))
    if clicks is None or impressions is None or ctr is None or position is None:
        return RejectedRow("missing or non-numeric metric", raw)
    if clicks < 0 or impressions < 0 or clicks != int(clicks) or impressions != int(impressions):
        return RejectedRow("clicks and impressions must be non-negative integers", raw)
    if clicks > impressions:
        return RejectedRow("clicks exceed impressions", raw)
    if not 0.0 <= ctr <= 1.0:
        return RejectedRow("ctr outside 0..1", raw)
    if position < 1.0 and impressions > 0:
        return RejectedRow("position below 1", raw)
    return AnalyticsRow(
        date=day,
        query=query,
        page=page,
        clicks=int(clicks),
        impressions=int(impressions),
        ctr=ctr,
        position=position,
    )


def normalize_response(
    payload: dict[str, Any], start: date, end: date
) -> tuple[list[AnalyticsRow], list[RejectedRow]]:
    """``rows`` may be absent (no data for the range): that is an empty result, not an error."""
    raw_rows = payload.get("rows", [])
    if not isinstance(raw_rows, list):
        return [], [RejectedRow("rows is not a list", {"rows": repr(raw_rows)[:200]})]
    accepted: list[AnalyticsRow] = []
    rejected: list[RejectedRow] = []
    for raw in raw_rows:
        result = normalize_row(raw, start, end)
        (accepted if isinstance(result, AnalyticsRow) else rejected).append(result)  # type: ignore[arg-type]
    return accepted, rejected


class TokenCipher:
    """Fernet (AES-128-CBC + HMAC) around the Google refresh token."""

    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("GSC_TOKEN_ENCRYPTION_KEY is not configured")
        self._fernet = Fernet(key.encode())

    def encrypt(self, token: str) -> str:
        return self._fernet.encrypt(token.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("stored Google credential cannot be decrypted") from exc
