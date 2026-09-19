"""V3 Job Runs domain Pydantic v2 schemas.

V3 Reference: seo-geo-system-handoff-v3.md §3.1, §6.8
"""

from __future__ import annotations

from enum import StrEnum


class JobRunStatus(StrEnum):
    """V3: Status of a job run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(StrEnum):
    """V3 §6.8: Known job types.

    The five production model calls plus pipeline operations.
    This is not exhaustive — job_type on the model is a free string
    to allow future extension without migration.
    """

    OUTLINE = "outline"
    DRAFT = "draft"
    QA_EXTRACTION = "qa_extraction"
    REPAIR = "repair"
    SECTION_REGENERATE = "section_regenerate"
    CLASSIFY = "classify"
    SCORE = "score"
    STALE_CLAIM_SCAN = "stale_claim_scan"
    AUTO_APPROVE = "auto_approve"
    SITE_IMPORT = "site_import"


class TriggerSource(StrEnum):
    """V3 §6.5: Who/what triggered a job."""

    USER = "user"
    AUTO_APPROVE = "auto_approve"
    PIPELINE = "pipeline"
    CLI = "cli"
    MCP = "mcp"
    SYSTEM = "system"
