"""API contracts for the read-only Google Search Console integration (Phase 6A).

No schema carries a token, secret or ciphertext.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ConnectionState = Literal[
    "not_connected", "pending", "connected", "reauth_required", "disconnected"
]
MAX_RANGE_DAYS = 16 * 31  # Search Console keeps about 16 months of data


class MappedProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_url: str
    permission_level: str
    last_synced_at: datetime | None
    last_sync_start: date | None
    last_sync_end: date | None
    stored_rows: int


class SyncRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_run_id: UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    start_date: date | None
    end_date: date | None
    rows_fetched: int
    rows_stored: int
    rows_rejected: int
    truncated: bool
    error: str | None


class WebsiteSearchConsole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website_id: UUID
    website_name: str
    base_url: str
    property: MappedProperty | None
    last_sync: SyncRun | None


class SearchConsoleStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    # False until the OAuth client and encryption key are set on the server.
    configured: bool
    state: ConnectionState
    google_account_email: str | None
    connected_at: datetime | None
    last_error: str | None
    can_manage: bool
    websites: list[WebsiteSearchConsole]


class ConnectStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_url: str


class OAuthCallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=16, max_length=256)


class OAuthCallbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    state: ConnectionState
    google_account_email: str | None


class AvailableProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_url: str
    permission_level: str
    # Websites in this project already mapped to it.
    mapped_website_ids: list[UUID]


class AvailablePropertyList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AvailableProperty]


class PropertyMapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_url: str = Field(min_length=1, max_length=2048)


class DateRange(BaseModel):
    """Inclusive dates; defaults to the 28 days ending two days ago (GSC's usual lag)."""

    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _both_or_neither(self) -> "DateRange":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("give both start_date and end_date, or neither")
        return self


class SyncRequest(DateRange):
    pass


class AnalyticsRowOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    query: str
    page: str
    clicks: int
    impressions: int
    ctr: float
    position: float


class AnalyticsTotals(BaseModel):
    """Sums over stored (date, query, page) rows. Google drops anonymized queries from
    query-level data, so these can be lower than the property totals in the GSC UI."""

    model_config = ConfigDict(extra="forbid")

    clicks: int
    impressions: int
    ctr: float
    # Impression-weighted average position over the rows.
    position: float | None
    rows: int
    queries: int
    pages: int


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website_id: UUID
    site_url: str
    start_date: date
    end_date: date
    totals: AnalyticsTotals
    rows: list[AnalyticsRowOut]
    next_offset: int | None


AnalyticsSort = Literal["clicks", "impressions", "ctr", "position", "date"]
