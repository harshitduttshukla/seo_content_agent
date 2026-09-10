"""Provider-neutral OIDC JWT verification."""

import asyncio
from typing import Final, Protocol

import jwt
from jwt import PyJWKClient
from pydantic import BaseModel, ConfigDict

from app.config.settings import Settings
from app.core.errors import AuthenticationRequired

LOCAL_AUTH_USERS: Final[frozenset[str]] = frozenset({"admin", "seo_lead"})


class IdentityClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    issuer: str
    subject: str
    email: str
    display_name: str


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> IdentityClaims: ...


class OIDCTokenVerifier:
    """Verify asymmetric OIDC access tokens against a rotating JWKS."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._issuer = str(settings.AUTH_ISSUER)
        self._audience = settings.AUTH_AUDIENCE
        self._algorithms = list(settings.AUTH_ALLOWED_ALGORITHMS)
        self._clock_skew = settings.AUTH_CLOCK_SKEW_SECONDS
        self._jwks = PyJWKClient(str(settings.AUTH_JWKS_URL), cache_keys=True)

    async def verify(self, token: str) -> IdentityClaims:
        if token.startswith("dev-"):
            username = token.removeprefix("dev-").strip()
            if (
                self._settings.APP_ENV not in ("local", "test")
                or not self._settings.ALLOW_LOCAL_AUTH
                or username not in LOCAL_AUTH_USERS
            ):
                raise AuthenticationRequired("Local development authentication is disabled.")
            clean_name = username.replace("_", " ").replace("-", " ").title()
            return IdentityClaims(
                issuer="http://local-dev",
                subject=f"dev-{username}",
                email=f"{username}@example.com",
                display_name=clean_name,
            )
        try:
            claims = await asyncio.to_thread(self._decode, token)
            email = str(claims.get("email", ""))
            display_name = str(claims.get("name") or claims.get("preferred_username") or email)
            if not email:
                raise AuthenticationRequired("The identity token does not include an email claim.")
            return IdentityClaims(
                issuer=str(claims["iss"]),
                subject=str(claims["sub"]),
                email=email,
                display_name=display_name,
            )
        except AuthenticationRequired:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise AuthenticationRequired("The access token is invalid or expired.") from exc

    def _decode(self, token: str) -> dict[str, object]:
        signing_key = self._jwks.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=self._algorithms,
            audience=self._audience,
            issuer=self._issuer,
            leeway=self._clock_skew,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
        )
        return dict(decoded)
