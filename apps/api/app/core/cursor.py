"""Opaque cursor encoding shared by stable database list operations."""

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.errors import InvalidCursor


@dataclass(frozen=True, slots=True)
class Cursor:
    created_at: datetime
    resource_id: UUID


def encode_cursor(created_at: datetime, resource_id: UUID) -> str:
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(resource_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str | None) -> Cursor | None:
    if value is None:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding))
        return Cursor(
            created_at=datetime.fromisoformat(payload["created_at"]),
            resource_id=UUID(payload["id"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidCursor from exc
