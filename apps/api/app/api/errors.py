"""Central exception-to-contract mapping."""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import AppError
from app.schemas.common import ApiResponse, ErrorItem, ResponseMeta

logger = logging.getLogger(__name__)


def error_response(request: Request, error: ErrorItem, status_code: int) -> JSONResponse:
    payload = ApiResponse[object](
        data=None,
        meta=ResponseMeta(request_id=getattr(request.state, "request_id", "unknown")),
        errors=[error],
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "application request failed",
        extra={"error_code": exc.code, "status_code": exc.status_code},
    )
    headers: dict[str, str] = {}
    response = error_response(
        request,
        ErrorItem(
            code=exc.code,
            message=exc.message,
            field=exc.field,
            details=exc.details,
        ),
        exc.status_code,
    )
    if exc.status_code == 401:
        headers["WWW-Authenticate"] = "Bearer"
        response.headers.update(headers)
    return response


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    location = first.get("loc", ())
    field = ".".join(str(item) for item in location if item not in {"body", "query", "path"})
    return error_response(
        request,
        ErrorItem(
            code="VALIDATION_ERROR",
            message="The request contains invalid data.",
            field=field or None,
            details={"reason": str(first.get("msg", "invalid value"))},
        ),
        422,
    )


async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("database operation failed", extra={"error_code": "DATABASE_ERROR"})
    return error_response(
        request,
        ErrorItem(code="INTERNAL_ERROR", message="The request could not be completed."),
        500,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unexpected request failure", extra={"error_code": "INTERNAL_ERROR"})
    return error_response(
        request,
        ErrorItem(code="INTERNAL_ERROR", message="The request could not be completed."),
        500,
    )
