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

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/seo_content"
    DATABASE_MIGRATION_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/seo_content"
    )

    AUTH_ISSUER: AnyHttpUrl = AnyHttpUrl("https://identity.example.com/")
    AUTH_AUDIENCE: str = "seo-content-api"
    AUTH_JWKS_URL: AnyHttpUrl = AnyHttpUrl("https://identity.example.com/.well-known/jwks.json")
    AUTH_ALLOWED_ALGORITHMS: tuple[str, ...] = ("RS256",)
    AUTH_CLOCK_SKEW_SECONDS: int = Field(default=30, ge=0, le=300)

    CORS_ORIGINS: tuple[str, ...] = ("http://localhost:3000",)
    REQUEST_ID_HEADER: str = "X-Request-ID"

    @field_validator("API_PREFIX")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/") or value.endswith("/"):
            raise ValueError("API_PREFIX must start with '/' and must not end with '/'")
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @model_validator(mode="after")
    def validate_production_safety(self) -> Self:
        if self.APP_ENV == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if "*" in self.CORS_ORIGINS:
                raise ValueError("Wildcard CORS origins are forbidden in production")
            if self.AUTH_ISSUER.host == "identity.example.com":
                raise ValueError("A real OIDC issuer is required in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated process settings singleton."""

    return Settings()
