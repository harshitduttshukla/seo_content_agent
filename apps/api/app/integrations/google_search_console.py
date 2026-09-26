"""Google OAuth 2.0 and Search Console API adapter (read-only).

Endpoints used (Google's published contracts):
- ``https://accounts.google.com/o/oauth2/v2/auth`` — authorization (``access_type=offline``)
- ``https://oauth2.googleapis.com/token`` — code exchange and refresh
- ``https://oauth2.googleapis.com/revoke`` — revoke on disconnect
- ``GET https://www.googleapis.com/webmasters/v3/sites`` — properties the account can read
- ``POST https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/searchAnalytics/query``

Scope: ``webmasters.readonly`` plus ``openid email`` to show which account is connected.
Tokens are never logged or put into error messages.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import quote, urlencode

import httpx

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API_BASE = "https://www.googleapis.com/webmasters/v3"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = ("https://www.googleapis.com/auth/webmasters.readonly", "openid", "email")
MAX_ROW_LIMIT = 25_000  # searchAnalytics.query maximum per request


class GSCError(Exception):
    """Base for Search Console adapter failures; ``code`` is safe to show users."""

    code = "GSC_API_ERROR"
    status = 502

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class GSCReauthRequired(GSCError):
    code = "GSC_REAUTH_REQUIRED"
    status = 409


class GSCPermissionDenied(GSCError):
    code = "GSC_PERMISSION_DENIED"
    status = 403


class GSCRateLimited(GSCError):
    code = "GSC_RATE_LIMITED"
    status = 429


class GSCUnavailable(GSCError):
    code = "GSC_UNAVAILABLE"
    status = 503


class GSCBadResponse(GSCError):
    code = "GSC_BAD_RESPONSE"
    status = 502


@dataclass(frozen=True, slots=True)
class TokenGrant:
    access_token: str
    refresh_token: str | None
    scope: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class SiteEntry:
    site_url: str
    permission_level: str


class GoogleSearchConsoleClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._timeout = timeout
        self._client = client

    # ── OAuth ────────────────────────────────────────────────────

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",  # always return a refresh token
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> TokenGrant:
        data = await self._token_request(
            {
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
            }
        )
        return self._grant(data)

    async def refresh(self, refresh_token: str) -> TokenGrant:
        data = await self._token_request(
            {
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            }
        )
        return self._grant(data)

    async def revoke(self, token: str) -> None:
        try:
            await self._send("POST", REVOKE_URL, data={"token": token})
        except GSCError:  # best effort: the local connection is removed either way
            logger.warning("Google token revoke failed; local credentials removed anyway")

    async def account_email(self, access_token: str) -> str | None:
        try:
            data = await self._json("GET", USERINFO_URL, access_token)
        except GSCError:
            return None
        email = data.get("email")
        return email if isinstance(email, str) else None

    # ── Search Console ───────────────────────────────────────────

    async def list_sites(self, access_token: str) -> list[SiteEntry]:
        data = await self._json("GET", f"{API_BASE}/sites", access_token)
        entries = data.get("siteEntry", [])
        if not isinstance(entries, list):
            raise GSCBadResponse("Search Console returned an unexpected sites list.")
        sites: list[SiteEntry] = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("siteUrl"), str):
                raise GSCBadResponse("Search Console returned a malformed site entry.")
            sites.append(
                SiteEntry(
                    site_url=entry["siteUrl"],
                    permission_level=str(entry.get("permissionLevel", "")),
                )
            )
        return sites

    async def query_search_analytics(
        self,
        access_token: str,
        site_url: str,
        *,
        start_date: date,
        end_date: date,
        dimensions: tuple[str, ...] = ("date", "query", "page"),
        start_row: int = 0,
        row_limit: int = MAX_ROW_LIMIT,
    ) -> dict[str, Any]:
        body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": list(dimensions),
            "type": "web",
            "rowLimit": min(row_limit, MAX_ROW_LIMIT),
            "startRow": start_row,
        }
        url = f"{API_BASE}/sites/{quote(site_url, safe='')}/searchAnalytics/query"
        return await self._json("POST", url, access_token, json=body)

    # ── HTTP ─────────────────────────────────────────────────────

    async def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        response = await self._send("POST", TOKEN_URL, data=form)
        payload = self._payload(response)
        if response.status_code == 400 and payload.get("error") in (
            "invalid_grant",
            "unauthorized_client",
        ):
            raise GSCReauthRequired("Google access was revoked or expired. Reconnect Google.")
        if response.status_code >= 400:
            raise GSCError(f"Google token request failed ({response.status_code}).")
        return payload

    @staticmethod
    def _grant(data: dict[str, Any]) -> TokenGrant:
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise GSCBadResponse("Google returned no access token.")
        refresh = data.get("refresh_token")
        return TokenGrant(
            access_token=token,
            refresh_token=refresh if isinstance(refresh, str) and refresh else None,
            scope=str(data.get("scope", "")),
            expires_in=int(data.get("expires_in", 0) or 0),
        )

    async def _json(
        self, method: str, url: str, access_token: str, *, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await self._send(
            method, url, headers={"Authorization": f"Bearer {access_token}"}, json=json
        )
        payload = self._payload(response)
        if response.status_code == 401:
            raise GSCReauthRequired("Google rejected the access token. Reconnect Google.")
        if response.status_code == 403:
            raise GSCPermissionDenied(
                "The connected Google account has no access to this Search Console property."
            )
        if response.status_code == 404:
            raise GSCPermissionDenied("Search Console property not found for this account.")
        if response.status_code == 429:
            raise GSCRateLimited("Search Console rate limit reached. Try again later.")
        if response.status_code >= 500:
            raise GSCUnavailable(f"Search Console is unavailable ({response.status_code}).")
        if response.status_code >= 400:
            error = payload.get("error")
            detail = error.get("message") if isinstance(error, dict) else None
            raise GSCError(f"Search Console rejected the request: {detail or response.status_code}")
        return payload

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            if self._client is not None:
                return await self._client.request(method, url, **kwargs)
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                return await client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise GSCUnavailable("Search Console did not respond in time.") from exc
        except httpx.RequestError as exc:
            raise GSCUnavailable("Could not reach Google.") from exc

    @staticmethod
    def _payload(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            if response.status_code < 400:
                raise GSCBadResponse("Google returned a non-JSON response.") from exc
            return {}
        return data if isinstance(data, dict) else {}
