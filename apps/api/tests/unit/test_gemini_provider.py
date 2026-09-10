"""Unit tests for GeminiAIProvider and provider factory."""

import json
from unittest.mock import patch

import httpx
import pytest
from app.ai.provider import AIMessage, GenerationRequest, GenerationResult, Usage
from app.core.errors import DomainError
from app.domains.ai.service import ContentAIService, MockAIProvider, get_ai_provider
from app.integrations.gemini import GeminiAIProvider


class StaticResponseProvider(MockAIProvider):
    def __init__(self, text: str, finish_reason: str = "STOP") -> None:
        self._text = text
        self._finish_reason = finish_reason

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        return GenerationResult(
            text=self._text,
            provider="gemini",
            model="gemini-flash-latest",
            usage=Usage(input_tokens=1, output_tokens=1),
            finish_reason=self._finish_reason,
        )


@pytest.mark.asyncio
async def test_gemini_generate_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/models/gemini-flash-latest:generateContent"
        assert request.headers["x-goog-api-key"] == "test-key"
        body = json.loads(request.read())
        assert "system_instruction" in body
        assert body["system_instruction"]["parts"][0]["text"] == "System instructions"
        assert body["contents"][0]["role"] == "user"
        assert body["contents"][0]["parts"][0]["text"] == "Hello Gemini"

        response_body = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": '{"message": "Hello human", "operations": []}'}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                    "index": 0,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 15,
                "candidatesTokenCount": 20,
                "totalTokenCount": 35,
            },
            "modelVersion": "gemini-flash-latest",
            "responseId": "res-12345",
        }
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiAIProvider(
            api_key="test-key",
            model="gemini-flash-latest",
            client=client,
        )

        req = GenerationRequest(
            messages=[
                AIMessage(role="system", content="System instructions"),
                AIMessage(role="user", content="Hello Gemini"),
            ],
            temperature=0.2,
            max_output_tokens=1000,
        )

        result = await provider.generate(req)
        assert result.provider == "gemini"
        assert result.text == '{"message": "Hello human", "operations": []}'
        assert result.usage.input_tokens == 15
        assert result.usage.output_tokens == 20
        assert result.finish_reason == "STOP"
        assert result.provider_request_id == "res-12345"


@pytest.mark.asyncio
async def test_content_ai_service_accepts_null_diff_summary() -> None:
    provider = StaticResponseProvider(
        json.dumps(
            {
                "message": "This page uses SEO naturally across its headings and paragraphs.",
                "operations": [],
                "reason": "Answered the user's question.",
                "diff_summary": None,
            }
        )
    )

    response = await ContentAIService(provider).generate_edit_proposal(
        [AIMessage(role="user", content="What SEO is added to this page?")]
    )

    assert response.message == "This page uses SEO naturally across its headings and paragraphs."
    assert response.operations == []
    assert response.diff_summary == {}


@pytest.mark.asyncio
async def test_content_ai_service_does_not_expose_invalid_json_envelope() -> None:
    provider = StaticResponseProvider(
        json.dumps(
            {
                "message": "Here is the readable answer.",
                "operations": [{"operation": "unsupported_operation"}],
                "reason": "Answered without making an edit.",
            }
        )
    )

    response = await ContentAIService(provider).generate_edit_proposal(
        [AIMessage(role="user", content="Explain the page SEO")]
    )

    assert response.message == "Here is the readable answer."
    assert response.operations == []


@pytest.mark.asyncio
async def test_content_ai_service_rejects_truncated_json_without_displaying_it() -> None:
    provider = StaticResponseProvider(
        '{"message":"Completed the article","operations":[{"operation":"replace_block"',
        finish_reason="MAX_TOKENS",
    )

    response = await ContentAIService(provider).generate_edit_proposal(
        [AIMessage(role="user", content="Complete the entire article")]
    )

    assert response.operations == []
    assert "incomplete structured proposal" in response.message
    assert "output limit" in response.message
    assert not response.message.startswith("{")


@pytest.mark.asyncio
async def test_gemini_generate_rate_limit_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Quota exceeded"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiAIProvider(
            api_key="test-key",
            client=client,
        )

        req = GenerationRequest(
            messages=[AIMessage(role="user", content="Hello")],
        )

        with pytest.raises(DomainError) as exc_info:
            await provider.generate(req)
        assert exc_info.value.code == "AI_RATE_LIMIT"
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_gemini_embed_batch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/models/gemini-embedding-001:batchEmbedContents"
        assert request.headers["x-goog-api-key"] == "test-key"
        body = json.loads(request.read())
        assert len(body["requests"]) == 2

        response_body = {
            "embeddings": [
                {"values": [0.1, 0.2, 0.3]},
                {"values": [0.4, 0.5, 0.6]},
            ]
        }
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiAIProvider(
            api_key="test-key",
            client=client,
        )

        res = await provider.embed(["first sentence", "second sentence"])
        assert len(res.vectors) == 2
        assert res.vectors[0] == [0.1, 0.2, 0.3]
        assert res.vectors[1] == [0.4, 0.5, 0.6]


def test_get_ai_provider_factory() -> None:
    with patch("app.config.settings.get_settings") as mock_get_settings:
        # 1. Test environment defaults to MockAIProvider
        mock_settings = mock_get_settings.return_value
        mock_settings.APP_ENV = "test"
        mock_settings.AI_PROVIDER = "mock"
        mock_settings.AI_API_KEY = ""
        provider = get_ai_provider()
        assert isinstance(provider, MockAIProvider)

        # 2. Configured Gemini provider in local/prod environment
        mock_settings.APP_ENV = "local"
        mock_settings.AI_PROVIDER = "gemini"
        mock_settings.AI_API_KEY = "test-gemini-key"
        mock_settings.AI_MODEL = "gemini-flash-latest"
        mock_settings.AI_EMBEDDING_MODEL = "gemini-embedding-001"
        mock_settings.AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

        provider = get_ai_provider()
        assert isinstance(provider, GeminiAIProvider)
        assert provider._api_key == "test-gemini-key"


@pytest.mark.asyncio
async def test_gemini_generate_fallback_on_503() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v1beta/models/gemini-flash-latest:generateContent":
            return httpx.Response(503, json={"error": {"message": "Model overloaded"}})
        if request.url.path == "/v1beta/models/gemini-3.5-flash:generateContent":
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": '{"message": "Fallback response", "operations": []}'}
                                ],
                                "role": "model",
                            },
                            "finishReason": "STOP",
                            "index": 0,
                        }
                    ],
                    "modelVersion": "gemini-3.5-flash",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiAIProvider(
            api_key="test-key",
            model="gemini-flash-latest",
            client=client,
        )
        req = GenerationRequest(messages=[AIMessage(role="user", content="Hello")])
        res = await provider.generate(req)
        assert len(calls) == 2
        assert calls[0] == "/v1beta/models/gemini-flash-latest:generateContent"
        assert calls[1] == "/v1beta/models/gemini-3.5-flash:generateContent"
        assert res.model == "gemini-3.5-flash"
        assert res.text == '{"message": "Fallback response", "operations": []}'
