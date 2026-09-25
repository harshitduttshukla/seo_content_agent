"""Authenticated identity and authorization vocabulary."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RoleCode(StrEnum):
    ADMIN = "admin"
    SEO_MANAGER = "seo_manager"
    CONTENT_MANAGER = "content_manager"
    WRITER = "writer"
    EDITOR = "editor"
    VIEWER = "viewer"


class PermissionCode(StrEnum):
    ORGANIZATION_READ = "organization.read"
    ORGANIZATION_UPDATE = "organization.update"
    MEMBERS_READ = "members.read"
    MEMBERS_MANAGE = "members.manage"
    PROJECT_READ = "project.read"
    PROJECT_CREATE = "project.create"
    PROJECT_UPDATE = "project.update"
    PROJECT_DELETE = "project.delete"
    WEBSITE_READ = "website.read"
    WEBSITE_CREATE = "website.create"
    WEBSITE_UPDATE = "website.update"
    WEBSITE_DELETE = "website.delete"
    STRATEGY_READ = "strategy.read"
    STRATEGY_WRITE = "strategy.write"
    KEYWORD_READ = "keyword.read"
    KEYWORD_WRITE = "keyword.write"
    CONTENT_READ = "content.read"
    CONTENT_WRITE = "content.write"
    # V3 gates (G1 outline review): approve or send back. Writers and viewers lack it.
    CONTENT_REVIEW = "content.review"
    SEO_READ = "seo.read"
    SEO_WRITE = "seo.write"
    AI_USE = "ai.use"
    AI_WRITE = "ai.write"
    PUBLISH_EXECUTE = "publish.execute"


class AuthenticatedUser(BaseModel):
    """Internal user resolved from a verified external identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: UUID
    issuer: str
    subject: str
    email: str
    display_name: str


# Compatibility aliases for Phase 0 imports; authorization is now resource-scoped.
Principal = AuthenticatedUser
Role = RoleCode
