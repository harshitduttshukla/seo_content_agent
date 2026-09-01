"""Metadata and execution contracts for governed AI tools."""

from enum import StrEnum
from typing import Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class ToolPermission(StrEnum):
    READ = "read"
    PROPOSE = "propose"
    HIGH_IMPACT = "high_impact"


class SideEffect(StrEnum):
    NONE = "none"
    CREATE_ANALYSIS = "create_analysis"
    CREATE_PROPOSAL = "create_proposal"
    MUTATE_AFTER_APPROVAL = "mutate_after_approval"


class ToolContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    project_id: UUID
    actor_user_id: UUID
    ai_run_id: UUID
    approval_id: UUID | None = None


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    permission: ToolPermission
    side_effect: SideEffect
    audit_required: bool = True


class AITool[InputT: BaseModel, OutputT: BaseModel](Protocol):
    """One authorized application operation exposed to an AI model."""

    descriptor: ToolDescriptor
    input_model: type[InputT]
    output_model: type[OutputT]

    async def execute(self, context: ToolContext, payload: InputT) -> OutputT: ...
