"""Pydantic contracts for the V3 Brand Kit API."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrandKitUpsertRequest(BaseModel):
    spelling: str = Field(default="", max_length=64)
    banned_words: list[str] = Field(default_factory=list, max_length=100)
    style: str = Field(default="", max_length=10_000)
    vocabulary: str = Field(default="", max_length=10_000)
    tone_profile: str = Field(default="", max_length=10_000)
    profile_provisional: bool = True


class BrandKitResponse(BrandKitUpsertRequest):
    id: UUID
    revision: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VoiceSnippetCreateRequest(BaseModel):
    source_type: str = Field(min_length=1, max_length=50)
    source_name: str = Field(min_length=1, max_length=300)
    captured_on: date
    content: str = Field(min_length=1, max_length=20_000)
    area_id: UUID | None = None


class VoiceSnippetResponse(VoiceSnippetCreateRequest):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SocialProofCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=500)
    proof_type: str = Field(min_length=1, max_length=50)
    area_ids: list[UUID] = Field(default_factory=list, max_length=50)
    markets: list[str] = Field(default_factory=list, max_length=50)
    approved: bool = False


class SocialProofResponse(SocialProofCreateRequest):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BrandKitDetailResponse(BaseModel):
    brand_kit: BrandKitResponse | None
    voice_snippets: list[VoiceSnippetResponse]
    social_proofs: list[SocialProofResponse]
