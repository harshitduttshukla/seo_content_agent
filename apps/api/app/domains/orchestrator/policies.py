"""Execution policies, risk thresholds, and guardrails for the AI Orchestrator."""

from enum import StrEnum
from typing import Final


class ToolRiskLevel(StrEnum):
    READ = "READ"
    SUGGEST = "SUGGEST"
    WRITE = "WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"


# Default limits
DEFAULT_MAX_WORKFLOW_STEPS: Final[int] = 10
ABSOLUTE_MAX_WORKFLOW_STEPS: Final[int] = 20
DEFAULT_MAX_TOKEN_BUDGET: Final[int] = 20_000
DEFAULT_MAX_RETRIES: Final[int] = 3

# Risk levels requiring explicit human approval before execution
APPROVAL_REQUIRED_RISK_LEVELS: Final[set[ToolRiskLevel]] = {
    ToolRiskLevel.WRITE,
    ToolRiskLevel.DESTRUCTIVE,
    ToolRiskLevel.EXTERNAL_ACTION,
}

# Error categories that are fatal and should never be retried
NON_RETRYABLE_ERROR_CODES: Final[set[str]] = {
    "TOOL_NOT_FOUND",
    "TOOL_PERMISSION_DENIED",
    "PERMISSION_DENIED",
    "RESOURCE_NOT_FOUND",
    "BAD_REQUEST",
    "VALIDATION_ERROR",
    "INVALID_ARGUMENTS",
    "CONFLICT",
    "SELF_LINK_FORBIDDEN",
}


def requires_human_approval(risk_level: ToolRiskLevel) -> bool:
    """Returns True if the tool risk level requires explicit human approval."""
    return risk_level in APPROVAL_REQUIRED_RISK_LEVELS


def is_error_retryable(error_code: str) -> bool:
    """Returns True if the error is considered transient and safe to retry."""
    return error_code not in NON_RETRYABLE_ERROR_CODES
