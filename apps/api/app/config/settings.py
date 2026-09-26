"""Validated, environment-backed configuration for the API process."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration with production-only safety validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_ENV: Literal["local", "test", "staging", "production"] = "local"
    APP_NAME: str = "seo-content-agent"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ALLOW_LOCAL_AUTH: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/seo_content"
    DATABASE_MIGRATION_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/seo_content"
    )

    AUTH_ISSUER: AnyHttpUrl = AnyHttpUrl("https://identity.example.com/")
    AUTH_AUDIENCE: str = "seo-content-api"
    AUTH_JWKS_URL: AnyHttpUrl = AnyHttpUrl("https://identity.example.com/.well-known/jwks.json")
    AUTH_ALLOWED_ALGORITHMS: tuple[str, ...] = ("RS256",)
    AUTH_CLOCK_SKEW_SECONDS: int = Field(default=30, ge=0, le=300)

    CORS_ORIGINS: tuple[str, ...] | str = ("http://localhost:3000",)
    REQUEST_ID_HEADER: str = "X-Request-ID"

    AI_PROVIDER: str = "gemini"
    AI_API_KEY: str = ""
    AI_MODEL: str = "gemini-flash-latest"
    AI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    AI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    # Per-provider keys so generation can use Gemini and Claude side by side. AI_API_KEY
    # still serves AI_PROVIDER when its own key is not set.
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    # Comma-separated models users may pick (``provider:model`` or a bare model name);
    # empty offers the default models of every provider that has a key.
    AI_MODEL_OPTIONS: str = ""

    # Google Search Console (read-only OAuth). The refresh token is stored encrypted with
    # GSC_TOKEN_ENCRYPTION_KEY (a Fernet key); none of these values is ever returned or logged.
    GSC_OAUTH_CLIENT_ID: str = ""
    GSC_OAUTH_CLIENT_SECRET: str = ""
    GSC_OAUTH_REDIRECT_URI: str = "http://localhost:3000/api/integrations/google/callback"
    GSC_TOKEN_ENCRYPTION_KEY: str = ""

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    @field_validator("API_PREFIX")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/") or value.endswith("/"):
            raise ValueError("API_PREFIX must start with '/' and must not end with '/'")
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            val = value.strip()
            if val.startswith("[") and val.endswith("]"):
                import json

                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return tuple(str(x) for x in parsed)
                except Exception:
                    pass
            return tuple(item.strip() for item in val.split(",") if item.strip())
        if isinstance(value, (list, tuple, set)):
            return tuple(str(item) for item in value)
        return ("http://localhost:3000",)

    @model_validator(mode="after")
    def validate_production_safety(self) -> Self:
        if self.APP_ENV == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if "*" in self.CORS_ORIGINS:
                raise ValueError("Wildcard CORS origins are forbidden in production")
            if self.AUTH_ISSUER.host == "identity.example.com":
                raise ValueError("A real OIDC issuer is required in production")
            if self.ALLOW_LOCAL_AUTH:
                raise ValueError("Local authentication is forbidden in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated process settings singleton."""

    return Settings()
