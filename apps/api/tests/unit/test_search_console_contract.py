"""Unit tests for the GSC adapter, normalization, token cipher and date ranges.
Google is replaced by an httpx MockTransport: no network, no real credentials."""

import json
from datetime import date
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
import pytest
from app.core.errors import DomainError
from app.domains.search_console.normalize import (
    AnalyticsRow,
    RejectedRow,
    TokenCipher,
    normalize_response,
    normalize_row,
)
from app.domains.search_console.schemas import DateRange
from app.domains.search_console.service import resolve_range
from app.integrations.google_search_console import (
    GoogleSearchConsoleClient,
    GSCBadResponse,
    GSCPermissionDenied,
    GSCRateLimited,
    GSCReauthRequired,
    GSCUnavailable,
)
from cryptography.fernet import Fernet

START, END = date(2026, 8, 27), date(2026, 9, 23)


def row(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "keys": ["2026-09-01", "landed cost", "https://example.com/landed-cost"],
        "clicks": 3,
        "impressions": 120,
        "ctr": 0.025,
        "position": 7.4,
    }
    base.update(over)
    return base


# ── Normalization ─────────────────────────────────────────────────


def test_a_valid_row_is_normalized_exactly() -> None:
    result = normalize_row(row(), START, END)
    assert result == AnalyticsRow(
        date=date(2026, 9, 1),
        query="landed cost",
        page="https://example.com/landed-cost",
        clicks=3,
        impressions=120,
        ctr=0.025,
        position=7.4,
    )


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("text", "not an object"),
        (row(keys=["2026-09-01", "q"]), "keys must be [date, query, page]"),
        (row(keys=["01/09/2026", "q", "https://e.com/"]), "invalid date"),
        (row(keys=["2026-01-01", "q", "https://e.com/"]), "date outside the requested range"),
        (row(keys=["2026-09-01", "q", "/relative"]), "page is not an absolute http(s) URL"),
        (row(clicks=None), "missing or non-numeric metric"),
        (row(clicks=True), "missing or non-numeric metric"),
        (row(clicks=-1), "clicks and impressions must be non-negative integers"),
        (row(impressions=1.5), "clicks and impressions must be non-negative integers"),
        (row(clicks=5, impressions=4), "clicks exceed impressions"),
        (row(ctr=1.2), "ctr outside 0..1"),
        (row(position=0.4), "position below 1"),
    ],
)
def test_malformed_rows_are_rejected_with_a_reason(raw: object, reason: str) -> None:
    result = normalize_row(raw, START, END)
    assert isinstance(result, RejectedRow) and result.reason == reason


def test_empty_query_is_kept_and_missing_rows_are_an_empty_result() -> None:
    kept = normalize_row(row(keys=["2026-09-01", "", "https://e.com/"]), START, END)
    assert isinstance(kept, AnalyticsRow) and kept.query == ""
    assert normalize_response({"responseAggregationType": "byPage"}, START, END) == ([], [])
    accepted, rejected = normalize_response({"rows": [row(), row(ctr=5)]}, START, END)
    assert len(accepted) == 1 and len(rejected) == 1  # nothing silently discarded
    _, bad = normalize_response({"rows": "nope"}, START, END)
    assert bad[0].reason == "rows is not a list"


def test_token_cipher_round_trip_and_tamper() -> None:
    cipher = TokenCipher(Fernet.generate_key().decode())
    secret = "1//refresh-token-value"
    stored = cipher.encrypt(secret)
    assert secret not in stored and cipher.decrypt(stored) == secret
    with pytest.raises(ValueError):
        TokenCipher(Fernet.generate_key().decode()).decrypt(stored)
    with pytest.raises(ValueError):
        TokenCipher("")


def test_date_range_defaults_and_limits() -> None:
    today = date(2026, 9, 26)
    start, end = resolve_range(DateRange(), today)  # 28 inclusive days, ending 2 days ago
    assert (start, end) == (date(2026, 8, 28), date(2026, 9, 24)) and (end - start).days == 27
    assert resolve_range(DateRange(start_date=START, end_date=END), today) == (START, END)
    for start, end in [(END, START), (START, date(2026, 10, 1)), (date(2024, 1, 1), END)]:
        with pytest.raises(DomainError) as raised:
            resolve_range(DateRange(start_date=start, end_date=end), today)
        assert raised.value.code == "INVALID_DATE_RANGE"
    with pytest.raises(ValueError):
        DateRange(start_date=START)


# ── Google adapter ────────────────────────────────────────────────


def client(handler: object) -> tuple[GoogleSearchConsoleClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)  # type: ignore[operator]

    return (
        GoogleSearchConsoleClient(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="http://localhost:3000/cb",
            client=httpx.AsyncClient(transport=httpx.MockTransport(record)),
        ),
        seen,
    )


def test_authorization_url_requests_offline_read_only_access() -> None:
    c, _ = client(lambda r: httpx.Response(200))
    params = parse_qs(urlsplit(c.authorization_url("state-123")).query)
    assert params["scope"][0].split() == [
        "https://www.googleapis.com/auth/webmasters.readonly",
        "openid",
        "email",
    ]
    assert params["access_type"] == ["offline"] and params["prompt"] == ["consent"]
    assert params["state"] == ["state-123"] and params["redirect_uri"] == [
        "http://localhost:3000/cb"
    ]
    assert "client_secret" not in params


@pytest.mark.asyncio
async def test_code_exchange_and_refresh() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        if form["grant_type"] == ["authorization_code"]:
            assert form["code"] == ["abc"] and form["client_secret"] == ["csecret"]
            return httpx.Response(
                200,
                json={
                    "access_token": "at",
                    "refresh_token": "rt",
                    "scope": "https://www.googleapis.com/auth/webmasters.readonly",
                    "expires_in": 3599,
                },
            )
        return httpx.Response(200, json={"access_token": "at2", "expires_in": 3599})

    c, _ = client(handler)
    grant = await c.exchange_code("abc")
    assert (grant.access_token, grant.refresh_token) == ("at", "rt")
    assert (await c.refresh("rt")).access_token == "at2"


@pytest.mark.asyncio
async def test_revoked_refresh_token_requires_reconnect() -> None:
    c, _ = client(lambda r: httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(GSCReauthRequired):
        await c.refresh("rt")


@pytest.mark.asyncio
async def test_sites_and_search_analytics_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer at"
        if request.url.path.endswith("/sites"):
            return httpx.Response(
                200,
                json={
                    "siteEntry": [
                        {"siteUrl": "sc-domain:example.com", "permissionLevel": "siteOwner"}
                    ]
                },
            )
        return httpx.Response(200, json={"rows": [row()]})

    c, seen = client(handler)
    sites = await c.list_sites("at")
    assert [(s.site_url, s.permission_level) for s in sites] == [
        ("sc-domain:example.com", "siteOwner")
    ]
    data = await c.query_search_analytics(
        "at", "sc-domain:example.com", start_date=START, end_date=END, start_row=25_000
    )
    assert data["rows"][0]["clicks"] == 3
    query = seen[-1]
    assert unquote(query.url.raw_path.decode()).endswith(
        "/sites/sc-domain:example.com/searchAnalytics/query"
    )
    assert "sc-domain%3Aexample.com" in query.url.raw_path.decode()
    assert json.loads(query.content) == {
        "startDate": "2026-08-27",
        "endDate": "2026-09-23",
        "dimensions": ["date", "query", "page"],
        "type": "web",
        "rowLimit": 25_000,
        "startRow": 25_000,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(401, json={}), GSCReauthRequired),
        (httpx.Response(403, json={"error": {"message": "no"}}), GSCPermissionDenied),
        (httpx.Response(429, json={}), GSCRateLimited),
        (httpx.Response(503, json={}), GSCUnavailable),
        (httpx.Response(200, text="<html>"), GSCBadResponse),
        (httpx.Response(200, json={"siteEntry": [{"nope": 1}]}), GSCBadResponse),
    ],
)
async def test_api_errors_map_to_clear_states(response: httpx.Response, error: type) -> None:
    c, _ = client(lambda r: response)
    with pytest.raises(error) as raised:
        await c.list_sites("secret-access-token")
    assert "secret-access-token" not in raised.value.message


@pytest.mark.asyncio
async def test_timeouts_are_reported_as_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    c, _ = client(handler)
    with pytest.raises(GSCUnavailable):
        await c.list_sites("at")
