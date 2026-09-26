"""FastAPI application factory for the Phase 1 modular monolith."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.errors import (
    handle_app_error,
    handle_database_error,
    handle_unexpected_error,
    handle_validation_error,
)
from app.api.middleware import RequestContextMiddleware
from app.api.responses import success
from app.api.v1 import router as v1_router
from app.api.v3 import router as v3_router
from app.config.settings import Settings, get_settings
from app.core.errors import AppError
from app.db.runtime_role import assert_runtime_role_enforces_rls
from app.db.session import build_engine, build_session_factory
from app.observability.logging import configure_logging
from app.schemas.common import ApiResponse
from app.security.oidc import OIDCTokenVerifier, TokenVerifier


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    token_verifier: TokenVerifier | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.LOG_LEVEL)
    runtime_engine = engine or build_engine(runtime_settings)
    runtime_factory = session_factory or build_session_factory(runtime_engine)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if engine is None:
            # The process's own database connection must be subject to RLS.
            await assert_runtime_role_enforces_rls(application.state.engine)
        yield
        if engine is None:
            await application.state.engine.dispose()

    application = FastAPI(
        title=runtime_settings.APP_NAME,
        version="1.0.0",
        debug=runtime_settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs" if runtime_settings.APP_ENV != "production" else None,
        redoc_url=None,
    )
    application.state.settings = runtime_settings
    application.state.engine = runtime_engine
    application.state.session_factory = runtime_factory
    application.state.token_verifier = token_verifier or OIDCTokenVerifier(runtime_settings)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(
        RequestContextMiddleware, request_id_header=runtime_settings.REQUEST_ID_HEADER
    )

    application.add_exception_handler(AppError, handle_app_error)  # type: ignore[arg-type]
    application.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]
    application.add_exception_handler(SQLAlchemyError, handle_database_error)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, handle_unexpected_error)

    application.include_router(v1_router, prefix=runtime_settings.API_PREFIX)
    application.include_router(v3_router, prefix="/api")

    @application.get("/health/live", response_model=ApiResponse[dict[str, str]], tags=["health"])
    async def liveness(request: Request) -> ApiResponse[dict[str, str]]:
        return success(request, {"status": "ok"})

    @application.get("/health/ready", response_model=ApiResponse[dict[str, str]], tags=["health"])
    async def readiness(request: Request) -> ApiResponse[dict[str, str]]:
        async with runtime_factory() as session:
            await session.execute(text("SELECT 1"))
        return success(request, {"status": "ready"})

    return application


app = create_app()
