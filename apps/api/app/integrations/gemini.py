"""Google Gemini AI Provider implementation conforming to the AIProvider interface."""

import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import cast

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


class GeminiAIProvider(AIProvider):
    """Production provider integrating Google's Gemini generative and embedding APIs."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-flash-latest",
        embedding_model: str = "gemini-embedding-001",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._embedding_model = embedding_model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generates content via Gemini's generateContent endpoint."""
        model = request.model or self._model
        url = f"{self._base_url}/models/{model}:generateContent"

        system_instruction_parts: list[dict[str, str]] = []
        contents: list[dict[str, object]] = []

        for msg in request.messages:
            if msg.role == "system":
                system_instruction_parts.append({"text": msg.content})
            elif msg.role in ("user", "human"):
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role in ("assistant", "model"):
                contents.append({"role": "model", "parts": [{"text": msg.content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": msg.content}]})

        # Ensure at least one user content exists
        if not contents:
            contents.append({"role": "user", "parts": [{"text": "Process request."}]})

        # Ensure turns alternate or merge adjacent same-role messages
        merged_contents: list[dict[str, object]] = []
        for turn in contents:
            if merged_contents and merged_contents[-1]["role"] == turn["role"]:
                prev_parts = cast(list[dict[str, str]], merged_contents[-1]["parts"])
                curr_parts = cast(list[dict[str, str]], turn["parts"])
                prev_parts.extend(curr_parts)
            else:
                merged_contents.append(turn)

        gen_config: dict[str, object] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_output_tokens,
        }

        # Request JSON output by default unless explicitly opted out
        response_mime = request.metadata.get("response_mime_type", "application/json")
        if response_mime:
            gen_config["responseMimeType"] = response_mime

        payload: dict[str, object] = {
            "contents": merged_contents,
            "generationConfig": gen_config,
        }

        if system_instruction_parts:
            payload["system_instruction"] = {"parts": system_instruction_parts}

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

        try:
            if self._client:
                resp = await self._client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as ex:
            raise DomainError(
                "AI_TIMEOUT",
                f"Gemini API request timed out after {self._timeout}s.",
                http_status=504,
            ) from ex
        except httpx.RequestError as ex:
            raise DomainError(
                "AI_NETWORK_ERROR",
                f"Failed to communicate with Gemini API: {ex}",
                http_status=502,
            ) from ex

        # Fallback to gemini-3.5-flash if primary model is overloaded (503) or unavailable (404)
        if resp.status_code in (503, 404) and model != "gemini-3.5-flash":
            fallback_model = "gemini-3.5-flash"
            logger.warning(
                "Gemini model %s returned status %d. Falling back to %s.",
                model,
                resp.status_code,
                fallback_model,
            )
            fallback_url = f"{self._base_url}/models/{fallback_model}:generateContent"
            try:
                if self._client:
                    resp = await self._client.post(fallback_url, json=payload, headers=headers)
                else:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        resp = await client.post(fallback_url, json=payload, headers=headers)
                if resp.status_code < 400:
                    model = fallback_model
            except httpx.RequestError as fb_err:
                logger.warning("Fallback to %s failed: %s", fallback_model, fb_err)

        if resp.status_code == 429:
            raise DomainError(
                "AI_RATE_LIMIT",
                "Gemini API quota or rate limit exceeded. Please retry shortly.",
                http_status=429,
            )
        if resp.status_code == 503:
            raise DomainError(
                "AI_UNAVAILABLE",
                "Gemini API model is temporarily overloaded. Please retry shortly.",
                http_status=503,
            )
        if resp.status_code >= 400:
            is_json = resp.headers.get("content-type", "").startswith("application/json")
            error_data = resp.json().get("error", {}) if is_json else {}
            err_msg = error_data.get("message", resp.text)
            raise DomainError(
                "AI_PROVIDER_ERROR",
                f"Gemini API error ({resp.status_code}): {err_msg}",
                http_status=502,
            )

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise DomainError(
                "AI_EMPTY_RESPONSE",
                "Gemini returned an empty response with no candidates.",
                http_status=502,
            )

        first_candidate = candidates[0]
        content = first_candidate.get("content", {})
        parts = content.get("parts", [])
        text = "".join(str(p.get("text", "")) for p in parts if "text" in p)

        usage_meta = data.get("usageMetadata", {})
        prompt_tokens = int(usage_meta.get("promptTokenCount", 0))
        candidates_tokens = int(usage_meta.get("candidatesTokenCount", 0))
        finish_reason = str(first_candidate.get("finishReason", "STOP"))
        response_id = data.get("responseId")

        return GenerationResult(
            text=text,
            provider="gemini",
            model=str(data.get("modelVersion", model)),
            usage=Usage(input_tokens=prompt_tokens, output_tokens=candidates_tokens),
            finish_reason=finish_reason,
            provider_request_id=response_id,
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Stream response. Yields generated text chunks."""
        res = await self.generate(request)
        yield res.text

    async def embed(
        self,
        texts: Sequence[str],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> EmbeddingResult:
        """Generates embedding vectors using Gemini batchEmbedContents."""
        if not texts:
            return EmbeddingResult(
                vectors=[],
                provider="gemini",
                model=self._embedding_model,
                usage=Usage(input_tokens=0, output_tokens=0),
            )

        url = f"{self._base_url}/models/{self._embedding_model}:batchEmbedContents"
        model_uri = f"models/{self._embedding_model}"

        requests_payload = [
            {
                "model": model_uri,
                "content": {"parts": [{"text": t}]},
            }
            for t in texts
        ]

        payload = {"requests": requests_payload}
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

        try:
            if self._client:
                resp = await self._client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as ex:
            raise DomainError(
                "AI_NETWORK_ERROR",
                f"Failed to generate embeddings: {ex}",
                http_status=502,
            ) from ex

        if resp.status_code >= 400:
            is_json = resp.headers.get("content-type", "").startswith("application/json")
            error_data = resp.json().get("error", {}) if is_json else {}
            err_msg = error_data.get("message", resp.text)
            raise DomainError(
                "AI_EMBEDDING_ERROR",
                f"Gemini embedding error ({resp.status_code}): {err_msg}",
                http_status=502,
            )

        data = resp.json()
        raw_embeddings = data.get("embeddings", [])
        vectors: list[list[float]] = [
            [float(val) for val in item.get("values", [])] for item in raw_embeddings
        ]

        total_input_chars = sum(len(t) for t in texts)
        estimated_tokens = max(1, total_input_chars // 4)

        return EmbeddingResult(
            vectors=vectors,
            provider="gemini",
            model=self._embedding_model,
            usage=Usage(input_tokens=estimated_tokens, output_tokens=0),
        )
