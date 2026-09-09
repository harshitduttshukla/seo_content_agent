from typing import Literal

import pytest
from app.config.settings import Settings
from app.core.errors import AuthenticationRequired
from app.security.oidc import OIDCTokenVerifier


@pytest.mark.asyncio
async def test_local_auth_accepts_allowlisted_user_when_explicitly_enabled() -> None:
    verifier = OIDCTokenVerifier(Settings(_env_file=None, APP_ENV="local", ALLOW_LOCAL_AUTH=True))

    claims = await verifier.verify("dev-admin")

    assert claims.issuer == "http://local-dev"
    assert claims.subject == "dev-admin"
    assert claims.email == "admin@example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("app_env", "allow_local_auth", "token"),
    [
        ("local", False, "dev-admin"),
        ("staging", True, "dev-admin"),
        ("local", True, "dev-unknown"),
    ],
)
async def test_local_auth_rejects_disabled_environment_or_unknown_user(
    app_env: Literal["local", "staging"],
    allow_local_auth: bool,
    token: str,
) -> None:
    verifier = OIDCTokenVerifier(
        Settings(
            _env_file=None,
            APP_ENV=app_env,
            ALLOW_LOCAL_AUTH=allow_local_auth,
        )
    )

    with pytest.raises(
        AuthenticationRequired, match="Local development authentication is disabled"
    ):
        await verifier.verify(token)
