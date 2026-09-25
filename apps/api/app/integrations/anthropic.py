"""Anthropic (Claude) AI provider conforming to the AIProvider interface.

Uses the Messages API: ``POST {base_url}/v1/messages`` with ``x-api-key`` and
``anthropic-version`` headers. Anthropic has no embeddings endpoint, so
``embed`` is explicitly unsupported rather than faked.
"""

import logging
from collections.abc import AsyncIterator, Mapping, Sequence

import httpx

from app.ai.provider import (
    AIProvider,
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    Usage,
)
from app.core.errors import DomainError

logger = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_BASE_URL = "https://api.anthropic.com"


class AnthropicAIProvider(AIProvider):
    """Production provider for Anthropic's Claude models via the Messages API."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-sonnet-5",
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 300.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client

    @staticmethod
    def _payload(request: GenerationRequest, model: str) -> dict[str, object]:
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        turns: list[dict[str, str]] = []
        for message in request.messages:
            if message.role == "system":
                continue
            role = "assistant" if message.role in ("assistant", "model") else "user"
            if turns and turns[-1]["role"] == role:
                turns[-1]["content"] += "\n\n" + message.content
            else:
                turns.append({"role": role, "content": message.content})
        if not turns or turns[0]["role"] != "user":
            turns.insert(0, {"role": "user", "content": "Process request."})
        payload: dict[str, object] = {
            "model": model,
            "max_tokens": request.max_output_tokens,
            # The Messages API accepts 0.0-1.0.
            "temperature": min(request.temperature, 1.0),
            "messages": turns,
        }
        if system:
            payload["system"] = system
        return payload

    async def _post(
        self, url: str, payload: dict[str, object], headers: dict[str, str]
    ) -> httpx.Response:
        try:
            if self._client:
                return await self._client.post(url, json=payload, headers=headers)
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                return await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as ex:
            raise DomainError(
                "AI_TIMEOUT",
                f"Anthropic API request timed out after {self._timeout}s.",
                http_status=504,
            ) from ex
        except httpx.RequestError as ex:
            raise DomainError(
                "AI_NETWORK_ERROR",
                f"Failed to communicate with Anthropic API: {ex}",
                http_status=502,
            ) from ex

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        model = request.model or self._model
        url = f"{self._base_url}/v1/messages"
        headers = {
            "content-type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        payload = self._payload(request, model)
        resp = await self._post(url, payload, headers)
        if resp.status_code == 400 and "temperature" in resp.text:
            # Newer models (e.g. Claude Sonnet 5) reject sampling parameters; retry once without.
            logger.warning("Model %s rejected temperature; retrying without it.", model)
            payload.pop("temperature", None)
            resp = await self._post(url, payload, headers)

        if resp.status_code == 429:
            raise DomainError(
                "AI_RATE_LIMIT",
                "Anthropic API rate limit exceeded. Please retry shortly.",
                http_status=429,
            )
        if resp.status_code in (503, 529):
            raise DomainError(
                "AI_UNAVAILABLE",
                "Anthropic API is temporarily overloaded. Please retry shortly.",
                http_status=503,
            )
        if resp.status_code >= 400:
            is_json = resp.headers.get("content-type", "").startswith("application/json")
            error = resp.json().get("error", {}) if is_json else {}
            message = error.get("message", resp.text) if isinstance(error, dict) else resp.text
            # Never echo request headers (the API key) into errors or logs.
            raise DomainError(
                "AI_PROVIDER_ERROR",
                f"Anthropic API error ({resp.status_code}): {message}",
                http_status=502,
            )

        data = resp.json()
        blocks = data.get("content") or []
        text = "".join(
            str(b.get("text", ""))
            for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        )
        if not text:
            raise DomainError(
                "AI_EMPTY_RESPONSE",
                "Anthropic returned no text content.",
                http_status=502,
            )
        usage = data.get("usage") or {}
        return GenerationResult(
            text=text,
            provider="anthropic",
            model=str(data.get("model", model)),
            usage=Usage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            ),
            finish_reason=str(data.get("stop_reason") or "end_turn"),
            provider_request_id=data.get("id"),
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        result = await self.generate(request)
        yield result.text

    async def embed(
        self,
        texts: Sequence[str],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> EmbeddingResult:
        raise DomainError(
            "AI_EMBEDDING_UNSUPPORTED",
            "The Anthropic provider does not offer embeddings; configure an embedding provider.",
            http_status=501,
        )
