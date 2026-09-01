from typing import Any

import pytest
from app.config.settings import Settings
from pydantic import ValidationError


def settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_local_defaults_are_safe_and_runnable() -> None:
    result = settings()

    assert result.API_PREFIX == "/api/v1"
    assert result.CORS_ORIGINS == ("http://localhost:3000",)
    assert "postgresql+asyncpg" in result.DATABASE_URL


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        settings(
            APP_ENV="production",
            CORS_ORIGINS=("*",),
            AUTH_ISSUER="https://accounts.example.test/",
        )


def test_comma_separated_origins_are_parsed() -> None:
    result = settings(CORS_ORIGINS="https://one.test, https://two.test")

    assert result.CORS_ORIGINS == ("https://one.test", "https://two.test")
