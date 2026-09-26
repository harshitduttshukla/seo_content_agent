"""Migration-facing import registry for all implemented ORM models."""

from app.domains.audit.models import AuditLog, IdempotencyRecord, OutboxEvent
from app.domains.auth.models import (
    OrganizationMember,
    Permission,
    ProjectMember,
    Role,
    RolePermission,
)
from app.domains.brand_kit.models import BrandKit, SocialProof, VoiceSnippet
from app.domains.canvas.models import Area, Argument, Canvas, Claim
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
from app.domains.content_cards.models import ContentCard, ContentCardClaim
from app.domains.content_harness.models import ContentHarnessRun
from app.domains.crawling.models import CrawlEvent, CrawlJob, CrawlUrl
from app.domains.demand.models import DemandNode
from app.domains.internal_linking.models import LinkOpportunity, PageRelationship
from app.domains.job_runs.models import JobRun
from app.domains.orchestrator.models import (
    AIWorkflow,
    AIWorkflowStep,
    ToolExecutionRecord,
)
from app.domains.organizations.models import Organization
from app.domains.projects.models import Project
from app.domains.search_console.models import GscConnection, GscProperty, GscSearchAnalyticsRow
from app.domains.strategy.models import SEOStrategy, SEOStrategyVersion
from app.domains.users.models import User
from app.domains.websites.models import Website

__all__ = [
    "AIEditProposal",
    "AIWorkflow",
    "AIWorkflowStep",
    "Area",
    "Argument",
    "AuditLog",
    "BrandKit",
    "Canvas",
    "Claim",
    "ClusteringRun",
    "ContentArchitectureVersion",
    "ContentBrief",
    "ContentBriefVersion",
    "ContentCard",
    "ContentCardClaim",
    "ContentChatMessage",
    "ContentChatSession",
    "ContentDocument",
    "ContentDocumentVersion",
    "ContentHarnessRun",
    "ContentMapEdge",
    "ContentMapNode",
    "ContentOpportunity",
    "ContentPage",
    "ContentPageVersion",
    "ContentPillar",
    "CrawlEvent",
    "CrawlJob",
    "CrawlUrl",
    "DemandNode",
    "GscConnection",
    "GscProperty",
    "GscSearchAnalyticsRow",
    "IdempotencyRecord",
    "JobRun",
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
    "SocialProof",
    "ToolExecutionRecord",
    "Topic",
    "User",
    "VoiceSnippet",
    "Website",
]
