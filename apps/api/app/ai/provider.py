"""Provider-neutral AI interfaces used by application services."""

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class AIMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[AIMessage]
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_output_tokens: int = Field(default=1_500, ge=1, le=32_000)
    metadata: dict[str, str] = Field(default_factory=dict)


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class GenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    provider: str
    model: str
    usage: Usage
    finish_reason: str
    provider_request_id: str | None = None


class EmbeddingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vectors: list[list[float]]
    provider: str
    model: str
    usage: Usage


class AIProvider(Protocol):
    """Adapter contract; provider exceptions are mapped to application errors."""

    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    def stream(self, request: GenerationRequest) -> AsyncIterator[str]: ...

    async def embed(
        self,
        texts: Sequence[str],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> EmbeddingResult: ...
