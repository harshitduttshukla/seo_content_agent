"""Migration-facing import registry for all implemented ORM models."""

from app.domains.audit.models import AuditLog, IdempotencyRecord, OutboxEvent
from app.domains.auth.models import (
    OrganizationMember,
    Permission,
    ProjectMember,
    Role,
    RolePermission,
)
from app.domains.content.models import ContentPage, ContentPageVersion, PageLink
from app.domains.crawling.models import CrawlEvent, CrawlJob, CrawlUrl
from app.domains.organizations.models import Organization
from app.domains.projects.models import Project
from app.domains.users.models import User
from app.domains.websites.models import Website

__all__ = [
    "AuditLog",
    "ContentPage",
    "ContentPageVersion",
    "CrawlEvent",
    "CrawlJob",
    "CrawlUrl",
    "IdempotencyRecord",
    "Organization",
    "OrganizationMember",
    "OutboxEvent",
    "PageLink",
    "Permission",
    "Project",
    "ProjectMember",
    "Role",
    "RolePermission",
    "User",
    "Website",
]
