"""Transport-level response and pagination contracts."""

from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class ErrorItem(BaseModel):
    """Stable machine-readable error entry."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class ResponseMeta(BaseModel):
    """Request metadata shared by success and failure responses."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    next_cursor: str | None = None
    has_more: bool | None = None


class ApiResponse[DataT](BaseModel):
    """Public response envelope; failures set data to null."""

    model_config = ConfigDict(extra="forbid")

    data: DataT | None
    meta: ResponseMeta
    errors: list[ErrorItem] = Field(default_factory=list)


class CursorPageParams(BaseModel):
    """Validated cursor pagination inputs before endpoint-specific filtering."""

    model_config = ConfigDict(extra="forbid")

    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)
