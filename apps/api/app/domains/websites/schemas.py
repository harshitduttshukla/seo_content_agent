"""Website transport contracts."""

from datetime import datetime
from uuid import UUID

from app.domains.websites.models import WebsiteStatus
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class WebsiteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=160)
    url: HttpUrl
    locale: str = Field(default="en", min_length=2, max_length=20)
    country: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("country")
    @classmethod
    def uppercase_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class WebsiteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=160)
    url: HttpUrl
    status: WebsiteStatus
    locale: str = Field(min_length=2, max_length=20)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    revision: int = Field(ge=1)

    @field_validator("country")
    @classmethod
    def uppercase_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class WebsiteDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str
    base_url: str
    normalized_host: str
    status: str
    locale: str
    country: str | None
    verification_status: str
    revision: int
    created_at: datetime
    updated_at: datetime


class WebsiteList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WebsiteDetail]
