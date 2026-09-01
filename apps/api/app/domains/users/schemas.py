"""User transport contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    email: str
    display_name: str
    status: str
    created_at: datetime
    last_seen_at: datetime | None
