"""Framework-independent application error types."""

from http import HTTPStatus


class AppError(Exception):
    """A safe error that can cross the HTTP boundary."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        field: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field
        self.details = details or {}


class AuthenticationRequired(AppError):
    def __init__(self, message: str = "Authentication is required.") -> None:
        super().__init__("AUTHENTICATION_REQUIRED", message, HTTPStatus.UNAUTHORIZED)


class PermissionDenied(AppError):
    def __init__(self, message: str = "You do not have permission for this action.") -> None:
        super().__init__("PERMISSION_DENIED", message, HTTPStatus.FORBIDDEN)


class ResourceNotFound(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            f"{resource.upper()}_NOT_FOUND",
            f"{resource.replace('_', ' ').title()} was not found.",
            HTTPStatus.NOT_FOUND,
        )


class ConflictError(AppError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(code, message, HTTPStatus.CONFLICT, details=details)


class InvalidCursor(AppError):
    def __init__(self) -> None:
        super().__init__(
            "INVALID_CURSOR", "The pagination cursor is invalid.", HTTPStatus.BAD_REQUEST
        )
