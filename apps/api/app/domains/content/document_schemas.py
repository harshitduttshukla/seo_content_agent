"""Pydantic schemas for Structured Document Blocks, Versioning, Chat, and AI Proposals."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.domains.content.editor_models import (
    DocumentStatus,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BlockType(StrEnum):
    DOCUMENT_TITLE = "DOCUMENT_TITLE"
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    BULLET_LIST = "BULLET_LIST"
    NUMBERED_LIST = "NUMBERED_LIST"
    QUOTE = "QUOTE"
    IMAGE = "IMAGE"
    LINK = "LINK"
    TABLE = "TABLE"
    FAQ = "FAQ"


class ContentBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Stable unique block identifier, e.g. block_001")
    type: BlockType = Field(default=BlockType.PARAGRAPH)
    text: str = Field(default="")
    level: int | None = Field(default=None, description="Heading level 1-6 if applicable")
    items: list[str] | None = Field(default=None, description="List items if applicable")
    data: dict[str, object] = Field(
        default_factory=dict, description="Metadata, url, alt, question/answer"
    )


class ContentDocumentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    website_id: UUID | None = None
    page_id: UUID
    brief_id: UUID | None = None
    title: str = ""
    slug: str = ""
    status: str = "DRAFT"
    current_version: int = 1
    lock_version: int = 1
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    plain_text: str = ""
    word_count: int = 0
    created_by_id: UUID | None = None
    updated_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v: object) -> object:
        return v if v else "DRAFT"

    @field_validator("title", "slug", "plain_text", mode="before")
    @classmethod
    def coerce_none_str(cls, v: object) -> object:
        return "" if v is None else v

    @field_validator("word_count", "current_version", "lock_version", mode="before")
    @classmethod
    def coerce_none_int(cls, v: object) -> object:
        return 1 if v is None else v


class ContentDocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    slug: str | None = None
    status: DocumentStatus | None = None
    content_blocks: list[ContentBlock] | None = None
    lock_version: int = Field(description="Current lock_version for optimistic concurrency")
    create_version_snapshot: bool = Field(
        default=False,
        description="Whether to create an immutable version checkpoint alongside autosave",
    )
    change_summary: str = Field(default="Document edit", max_length=1000)


class ContentDocumentVersionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    organization_id: UUID
    project_id: UUID
    version: int
    content_blocks: list[ContentBlock]
    plain_text: str
    word_count: int
    change_type: str
    change_summary: str
    created_by_id: UUID | None
    created_at: datetime


class ContentDocumentVersionList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[ContentDocumentVersionDetail]


class RestoreVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_summary: str = Field(default="Restored from previous version", max_length=1000)


# --- AI Chat & Operations ---


class OperationType(StrEnum):
    REPLACE_BLOCK = "replace_block"
    INSERT_BLOCK = "insert_block"
    DELETE_BLOCK = "delete_block"
    MOVE_BLOCK = "move_block"
    UPDATE_TITLE = "update_title"
    UPDATE_METADATA = "update_metadata"
    INSERT_LINK = "insert_link"
    BATCH_OPERATIONS = "batch_operations"


class AIOperation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    operation: OperationType
    block_id: str | None = None
    target_block_id: str | None = None
    position: str = Field(default="after", description="before or after for insert/move")
    block: ContentBlock | None = None
    old_content: str | None = None
    new_content: str | None = None
    url: str | None = None
    anchor_text: str | None = None
    reason: str = ""


class AIEditResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = Field(description="Conversational response to user")
    operations: list[AIOperation] = Field(default_factory=list)
    reason: str = ""
    diff_summary: dict[str, object] = Field(default_factory=dict)


class AIProposalDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    chat_message_id: UUID | None
    status: str
    operation_type: str
    target_block_ids: list[str]
    old_content: dict[str, object] | list[object]
    proposed_content: dict[str, object] | list[object]
    diff_summary: dict[str, object]
    reason: str
    ai_provider: str
    model: str
    reviewed_at: datetime | None
    reviewed_by_id: UUID | None
    applied_at: datetime | None
    applied_version: int | None
    created_at: datetime


AIEditProposalDetail = AIProposalDetail


class AIProposalList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[AIProposalDetail]


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=5000)
    selected_block_id: str | None = None
    selected_text: str | None = None
    command: str | None = Field(
        default=None,
        description="Optional shortcut command: rewrite, shorten, expand, add_faq, insert_link",
    )


class ChatMessageDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    document_id: UUID
    role: str
    content: str
    context_snapshot: dict[str, object]
    token_usage: dict[str, object]
    created_at: datetime
    proposal: AIProposalDetail | None = None


class ChatSessionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    document_id: UUID
    title: str
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageDetail] = Field(default_factory=list)
