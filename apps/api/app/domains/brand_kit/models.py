"""Tenant-scoped persistence models for the V3 Brand Kit."""

from datetime import date
from uuid import UUID

from app.core.models import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import Boolean, Date, ForeignKeyConstraint, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class BrandKit(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    """One voice profile per organization/project workspace."""

    __tablename__ = "brand_kits"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_brand_kits_org_proj_projects",
            ondelete="CASCADE",
        ),
        Index("uq_brand_kits_project", "project_id", unique=True),
        Index("ix_brand_kits_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    spelling: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    banned_words: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    vocabulary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tone_profile: Mapped[str] = mapped_column(Text, nullable=False, default="")
    profile_provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class VoiceSnippet(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    """An attributed voice-corpus sample used to establish the tone profile."""

    __tablename__ = "voice_snippets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_voice_snippets_org_proj_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["area_id"], ["areas.id"], name="fk_voice_snippets_area_id_areas", ondelete="SET NULL"
        ),
        Index("ix_voice_snippets_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_name: Mapped[str] = mapped_column(String(300), nullable=False)
    captured_on: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    area_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)


class SocialProof(UUIDPrimaryKeyMixin, TimestampMixin, RevisionMixin, Base):
    """A market/area-constrained proof item; only approved items are usable downstream."""

    __tablename__ = "social_proofs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_social_proofs_org_proj_projects",
            ondelete="CASCADE",
        ),
        Index("ix_social_proofs_org_proj", "organization_id", "project_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    proof_type: Mapped[str] = mapped_column(String(50), nullable=False)
    area_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    markets: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
