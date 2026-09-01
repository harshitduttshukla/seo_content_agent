"""Project transport contracts."""

from datetime import datetime
from uuid import UUID

from app.domains.projects.models import ProjectStatus
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, min_length=2, max_length=80)
    description: str = Field(default="", max_length=2_000)
    default_locale: str = Field(default="en", min_length=2, max_length=20)
    default_country: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("default_country")
    @classmethod
    def uppercase_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=2_000)
    status: ProjectStatus
    default_locale: str = Field(min_length=2, max_length=20)
    default_country: str | None = Field(default=None, min_length=2, max_length=2)
    revision: int = Field(ge=1)

    @field_validator("default_country")
    @classmethod
    def uppercase_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class ProjectDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: str
    status: str
    default_locale: str
    default_country: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


class ProjectList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProjectDetail]
