"""Pydantic schemas for AI Orchestrator requests, workflows, tools, and results."""

from datetime import datetime
from uuid import UUID

from app.domains.orchestrator.models import (
    StepStatus,
    ToolExecutionStatus,
    WorkflowIntent,
    WorkflowStatus,
)
from app.domains.orchestrator.policies import ToolRiskLevel
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


class ToolDescriptorDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
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
