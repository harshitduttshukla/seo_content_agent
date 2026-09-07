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
    AIEditProposal,
    ContentBrief,
    ContentBriefVersion,
    ContentChatMessage,
    ContentChatSession,
    ContentDocument,
    ContentDocumentVersion,
    ContentOpportunity,
    ContentPage,
    ContentPageVersion,
    ContentPillar,
    KeywordPageMapping,
    PageKeyword,
    PageLink,
    PlannedContentPage,
    Topic,
)
from app.domains.content_map.models import (
    ContentArchitectureVersion,
    ContentMapEdge,
    ContentMapNode,
)
from app.domains.crawling.models import CrawlEvent, CrawlJob, CrawlUrl
from app.domains.internal_linking.models import LinkOpportunity, PageRelationship
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
from app.domains.seo.models import SEOGuide, SEOGuideVersion
from app.domains.strategy.models import SEOStrategy, SEOStrategyVersion
from app.domains.users.models import User
from app.domains.websites.models import Website

__all__ = [
    "AIEditProposal",
    "AuditLog",
    "ClusteringRun",
    "ContentArchitectureVersion",
    "ContentBrief",
    "ContentBriefVersion",
    "ContentChatMessage",
    "ContentChatSession",
    "ContentDocument",
    "ContentDocumentVersion",
    "ContentMapEdge",
    "ContentMapNode",
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
    "LinkOpportunity",
    "Organization",
    "OrganizationMember",
    "OutboxEvent",
    "PageKeyword",
    "PageLink",
    "PageRelationship",
    "Permission",
    "PlannedContentPage",
    "Project",
    "ProjectMember",
    "Role",
    "RolePermission",
    "SEOGuide",
    "SEOGuideVersion",
    "SEOStrategy",
    "SEOStrategyVersion",
    "Topic",
    "User",
    "Website",
]
