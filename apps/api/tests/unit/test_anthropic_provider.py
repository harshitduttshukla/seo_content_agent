"""AnthropicAIProvider against a fake HTTP transport: no network, no paid calls."""

import json

import httpx
import pytest
from app.ai.provider import AIMessage, GenerationRequest
from app.core.errors import DomainError
from app.integrations.anthropic import ANTHROPIC_VERSION, AnthropicAIProvider


def _provider(handler: object) -> tuple[AnthropicAIProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)  # type: ignore[operator]

    client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    return AnthropicAIProvider("test-key", model="claude-sonnet-5", client=client), seen


def _request(**kw: object) -> GenerationRequest:
    messages = [
        AIMessage(role="system", content="rules"),
        AIMessage(role="user", content="first"),
        AIMessage(role="assistant", content="bad"),
        AIMessage(role="user", content="fix it"),
    ]
    return GenerationRequest(messages=messages, max_output_tokens=12_000, **kw)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_generate_maps_the_messages_api_contract() -> None:
    body = {
        "id": "msg_1",
        "model": "claude-sonnet-5",
        "content": [{"type": "text", "text": '{"ok": true}'}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 12, "output_tokens": 7},
    }
    provider, seen = _provider(lambda r: httpx.Response(200, json=body))
    result = await provider.generate(_request(temperature=1.5))

    request = seen[0]
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == "test-key"
    assert request.headers["anthropic-version"] == ANTHROPIC_VERSION
    sent = json.loads(request.content)
    assert sent["system"] == "rules" and sent["max_tokens"] == 12_000
    assert sent["temperature"] == 1.0  # clamped to the API's range
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant", "user"]
    assert (result.text, result.provider, result.model) == (
        '{"ok": true}',
        "anthropic",
        "claude-sonnet-5",
    )
    assert (result.usage.input_tokens, result.usage.output_tokens) == (12, 7)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [(429, "AI_RATE_LIMIT"), (529, "AI_UNAVAILABLE"), (400, "AI_PROVIDER_ERROR")],
)
async def test_errors_map_to_application_errors_without_the_key(status: int, code: str) -> None:
    error = {"type": "error", "error": {"type": "x", "message": "nope"}}
    provider, _ = _provider(lambda r: httpx.Response(status, json=error))
    with pytest.raises(DomainError) as raised:
        await provider.generate(_request())
    assert raised.value.code == code and "test-key" not in raised.value.message


@pytest.mark.asyncio
async def test_empty_content_and_embeddings_are_explicit_errors() -> None:
    empty = {"content": [], "usage": {"input_tokens": 1, "output_tokens": 0}}
    provider, _ = _provider(lambda r: httpx.Response(200, json=empty))
    with pytest.raises(DomainError) as raised:
        await provider.generate(_request())
    assert raised.value.code == "AI_EMPTY_RESPONSE"
    with pytest.raises(DomainError) as unsupported:
        await provider.embed(["x"])
    assert unsupported.value.code == "AI_EMBEDDING_UNSUPPORTED"


@pytest.mark.asyncio
async def test_retries_once_without_temperature_when_the_model_rejects_it() -> None:
    ok = {"model": "claude-sonnet-5", "content": [{"type": "text", "text": "x"}], "usage": {}}
    rejected = {
        "type": "error",
        "error": {"message": "`temperature` is deprecated for this model."},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)
        return (
            httpx.Response(400, json=rejected)
            if "temperature" in sent
            else httpx.Response(200, json=ok)
        )

    provider, seen = _provider(handler)
    assert (await provider.generate(_request())).text == "x"
    assert len(seen) == 2 and "temperature" not in json.loads(seen[1].content)
