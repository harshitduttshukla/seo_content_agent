"""Google Search Console persistence: connection, property mapping, analytics rows.

Organization → Project → (one) GscConnection (the Google account authorized for the
project) → Website → (one) GscProperty → GscSearchAnalyticsRow. Every row carries
organization_id and project_id for RLS and tenant-scoped queries.
"""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class GscConnectionStatus(StrEnum):
    PENDING = "pending"  # OAuth started, waiting for Google's callback
    CONNECTED = "connected"
    REAUTH_REQUIRED = "reauth_required"  # refresh token revoked/expired
    DISCONNECTED = "disconnected"  # token removed by a user; synced data is kept


class GscConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gsc_connections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_gsc_connections_org_proj_projects",
            ondelete="CASCADE",
        ),
        UniqueConstraint("project_id", name="uq_gsc_connections_project"),
        # Referenced with the tenant so a property cannot point at another tenant's connection.
        UniqueConstraint(
            "organization_id", "project_id", "id", name="uq_gsc_connections_org_proj_id"
        ),
        CheckConstraint(
            "status IN ('pending', 'connected', 'reauth_required', 'disconnected')",
            name="ck_gsc_connections_status_allowed",
        ),
        Index("ix_gsc_connections_oauth_state", "oauth_state_hash"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    google_account_email: Mapped[str | None] = mapped_column(String(320))
    # Fernet ciphertext of the refresh token; never returned by the API.
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # SHA-256 of the OAuth state (CSRF) and who started the flow.
    oauth_state_hash: Mapped[str | None] = mapped_column(String(64))
    oauth_state_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    oauth_started_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    connected_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class GscProperty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A Search Console property mapped to one project website."""

    __tablename__ = "gsc_properties"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_gsc_properties_org_proj_projects",
            ondelete="CASCADE",
        ),
        # Same-tenant references: the website and connection must share the property's
        # organization and project.
        ForeignKeyConstraint(
            ["organization_id", "project_id", "website_id"],
            ["websites.organization_id", "websites.project_id", "websites.id"],
            name="fk_gsc_properties_org_proj_website",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "connection_id"],
            [
                "gsc_connections.organization_id",
                "gsc_connections.project_id",
                "gsc_connections.id",
            ],
            name="fk_gsc_properties_org_proj_connection",
            ondelete="CASCADE",
        ),
        UniqueConstraint("website_id", name="uq_gsc_properties_website"),
        UniqueConstraint(
            "organization_id",
            "project_id",
            "website_id",
            "id",
            name="uq_gsc_properties_org_proj_website_id",
        ),
        Index("ix_gsc_properties_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    # e.g. "sc-domain:example.com" or "https://www.example.com/"
    site_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    permission_level: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    mapped_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_start: Mapped[date | None] = mapped_column(Date)
    last_sync_end: Mapped[date | None] = mapped_column(Date)


class GscSearchAnalyticsRow(UUIDPrimaryKeyMixin, Base):
    """One Search Analytics row for dimensions (date, query, page)."""

    __tablename__ = "gsc_search_analytics"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_gsc_search_analytics_org_proj_projects",
            ondelete="CASCADE",
        ),
        # Same tenant and same website as the property the row was synced from.
        ForeignKeyConstraint(
            ["organization_id", "project_id", "website_id", "property_id"],
            [
                "gsc_properties.organization_id",
                "gsc_properties.project_id",
                "gsc_properties.website_id",
                "gsc_properties.id",
            ],
            name="fk_gsc_search_analytics_org_proj_website_property",
            ondelete="CASCADE",
        ),
        # Idempotency: a re-sync of the same day/query/page updates in place.
        UniqueConstraint(
            "property_id", "date", "query", "page", name="uq_gsc_search_analytics_row"
        ),
        Index("ix_gsc_search_analytics_property_date", "property_id", "date"),
        Index("ix_gsc_search_analytics_org_proj", "organization_id", "project_id"),
        CheckConstraint("clicks >= 0 AND impressions >= 0", name="ck_gsc_search_analytics_counts"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    property_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[str] = mapped_column(Text, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, nullable=False)
    position: Mapped[float] = mapped_column(Float, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    job_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
