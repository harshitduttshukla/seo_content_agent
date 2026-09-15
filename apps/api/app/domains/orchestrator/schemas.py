"""Pydantic schemas for AI Orchestrator requests, workflows, tools, and results."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.domains.orchestrator.models import (
    StepStatus,
    ToolExecutionStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.policies import ToolAvailability, ToolRiskLevel
from pydantic import BaseModel, ConfigDict, Field


class IntentClassificationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: WorkflowIntent
    confidence: float = Field(ge=0.0, le=1.0)
    document_id: UUID | None = None
    requires_tools: bool = True
    parameters: dict[str, object] = Field(default_factory=dict)


class OrchestratorRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: UUID
    message: str = Field(min_length=1, max_length=5000)
    selected_block_ids: list[str] = Field(default_factory=list)
    intent: WorkflowIntent | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class WorkflowPlanStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    step_index: int = Field(ge=0)
    tool_name: str
    description: str
    risk_level: ToolRiskLevel
    requires_approval: bool = False
    input_arguments: dict[str, object] = Field(default_factory=dict)


class WorkflowStepDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    workflow_id: UUID
    step_index: int
    step_type: str
    tool_name: str
    status: StepStatus
    input: dict[str, object]
    output: dict[str, object]
    error: dict[str, object] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ToolExecutionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    workflow_id: UUID
    step_id: UUID
    tool_name: str
    status: ToolExecutionStatus
    input: dict[str, object]
    output: dict[str, object]
    error: dict[str, object] | None = None
    retry_count: int = 0
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime


class WorkflowDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    organization_id: UUID
    project_id: UUID
    document_id: UUID
    created_by_id: UUID | None
    intent: str
    status: WorkflowStatus
    current_step: int
    plan: list[dict[str, object]]
    result: dict[str, object]
    error: dict[str, object] | None = None
    token_usage: dict[str, object]
    steps: list[WorkflowStepDetail] = Field(default_factory=list)
    pending_proposal_id: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[WorkflowDetail]
    total: int


class WorkflowResumeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    step_id: UUID | None = None


class WorkflowCancelRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reason: str = "User cancelled"


class ToolCostDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimated_usd_per_call: Decimal = Field(ge=0)
    billing_unit: str


class ToolRateLimitsDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_calls_per_workflow: int = Field(gt=0)
    max_concurrent_calls: int = Field(gt=0)


class ToolDescriptorDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    authentication_requirements: list[str]
    permissions: list[str]
    cost: ToolCostDTO
    rate_limits: ToolRateLimitsDTO
    availability: ToolAvailability
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    risk_level: ToolRiskLevel
    required_permission: str
    enabled: bool = True


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tool_name: str
    status: ToolExecutionStatus
    result: dict[str, object]
    metadata: dict[str, object] = Field(default_factory=dict)


class LLMToolCall(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class LLMReasoningOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    tool_calls: list[LLMToolCall] = Field(default_factory=list)
    explanation: str = ""


# ---------------------------------------------------------------------------
# Content Agent Decision, Observation, and Execution Contracts
# ---------------------------------------------------------------------------


class AgentDecisionType(StrEnum):
    TOOL_CALL = "TOOL_CALL"
    FINAL = "FINAL"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: AgentDecisionType
    tool_name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    reasoning_summary: str | None = Field(default=None, max_length=500)
    final_response: str | None = None
    approval_reason: str | None = None


class ToolObservation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    execution_id: str
    tool_name: str
    status: str  # SUCCESS, FAILED, REJECTED, TIMEOUT
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    iteration: int = 0
    duration_ms: float | None = None
    provenance: dict[str, Any] | None = None


class AgentTerminationReason(StrEnum):
    COMPLETED = "COMPLETED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    MAX_TOOL_CALLS = "MAX_TOOL_CALLS"
    TIMEOUT = "TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    MODEL_ERROR = "MODEL_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    workflow_id: UUID
    status: WorkflowStatus
    intent: str
    summary: str
    actions_taken: list[str] = Field(default_factory=list)
    proposals_created: list[UUID] = Field(default_factory=list)
    observations_summary: list[str] = Field(default_factory=list)
    verification: dict[str, Any] | None = None
    approval_required: bool = False
    termination_reason: str = AgentTerminationReason.COMPLETED.value


class AgentState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    workflow_id: UUID
    iteration: int = 0
    tool_call_count: int = 0
    user_request: str
    intent: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    decisions: list[AgentDecision] = Field(default_factory=list)
    observations: list[ToolObservation] = Field(default_factory=list)
    pending_proposal_id: UUID | None = None
    termination_reason: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
