"""Migration-facing import registry for all implemented ORM models."""

from app.domains.audit.models import AuditLog, IdempotencyRecord, OutboxEvent
from app.domains.auth.models import (
    OrganizationMember,
    Permission,
    ProjectMember,
    Role,
    RolePermission,
)
from app.domains.content.models import (
    ContentOpportunity,
    ContentPage,
    ContentPageVersion,
    ContentPillar,
    KeywordPageMapping,
    PageLink,
    Topic,
)
from app.domains.crawling.models import CrawlEvent, CrawlJob, CrawlUrl
from app.domains.keywords.models import (
    ClusteringRun,
    Keyword,
    KeywordCluster,
    KeywordClusterMember,
    KeywordImport,
    KeywordImportRow,
)
from app.domains.organizations.models import Organization
from app.domains.projects.models import Project
from app.domains.strategy.models import SEOStrategy, SEOStrategyVersion
from app.domains.users.models import User
from app.domains.websites.models import Website

__all__ = [
    "AuditLog",
    "ClusteringRun",
    "ContentOpportunity",
    "ContentPage",
    "ContentPageVersion",
    "ContentPillar",
    "CrawlEvent",
    "CrawlJob",
    "CrawlUrl",
    "IdempotencyRecord",
    "Keyword",
    "KeywordCluster",
    "KeywordClusterMember",
    "KeywordImport",
    "KeywordImportRow",
    "KeywordPageMapping",
    "Organization",
    "OrganizationMember",
    "OutboxEvent",
    "PageLink",
    "Permission",
    "Project",
    "ProjectMember",
    "Role",
    "RolePermission",
    "SEOStrategy",
    "SEOStrategyVersion",
    "Topic",
    "User",
    "Website",
]
