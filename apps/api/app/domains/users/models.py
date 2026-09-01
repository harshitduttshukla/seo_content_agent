"""Global OIDC-backed user identity model."""

from datetime import datetime
from enum import StrEnum

from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("identity_issuer", "identity_subject"),
        CheckConstraint("status IN ('active', 'suspended')", name="status_allowed"),
        Index("ix_users_normalized_email", "normalized_email"),
    )

    identity_issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    identity_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=UserStatus.ACTIVE)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
