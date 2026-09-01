"""Organization and membership transport contracts."""

from datetime import datetime
from uuid import UUID

from app.domains.auth.models import MembershipStatus
from app.domains.organizations.models import OrganizationStatus
from app.security.principal import RoleCode
from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, min_length=2, max_length=80)


class OrganizationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=80)
    status: OrganizationStatus
    revision: int = Field(ge=1)


class OrganizationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: MembershipStatus
    revision: int
    created_at: datetime
    updated_at: datetime


class OrganizationList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationDetail]


class OrganizationMemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    role: RoleCode


class OrganizationMemberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: RoleCode
    status: str


class OrganizationMemberDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    user_id: UUID
    email: str
    display_name: str
    role: RoleCode
    status: str
    joined_at: datetime


class OrganizationMemberList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationMemberDetail]
