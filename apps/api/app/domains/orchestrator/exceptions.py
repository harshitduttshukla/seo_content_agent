"""Custom domain exceptions for the AI Orchestrator."""

from http import HTTPStatus

from app.core.errors import DomainError


class ToolNotFoundError(DomainError):
    def __init__(self, tool_name: str) -> None:
        super().__init__(
            code="TOOL_NOT_FOUND",
            message=f"Registered tool '{tool_name}' was not found.",
            http_status=HTTPStatus.NOT_FOUND,
            details={"tool_name": tool_name},
        )


class ToolPermissionDeniedError(DomainError):
    def __init__(self, tool_name: str, required_permission: str) -> None:
        super().__init__(
            code="TOOL_PERMISSION_DENIED",
            message=(
                f"User lacks required permission '{required_permission}' for tool '{tool_name}'."
            ),
            http_status=HTTPStatus.FORBIDDEN,
            details={"tool_name": tool_name, "required_permission": required_permission},
        )


class ToolExecutionError(DomainError):
    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(
            code="TOOL_EXECUTION_FAILED",
            message=f"Execution of tool '{tool_name}' failed: {reason}",
            http_status=HTTPStatus.BAD_REQUEST,
            details={"tool_name": tool_name, "reason": reason},
        )


class WorkflowStateError(DomainError):
    def __init__(self, current_status: str, action: str) -> None:
        super().__init__(
            code="INVALID_WORKFLOW_STATE",
            message=f"Cannot perform '{action}' on workflow in state '{current_status}'.",
            http_status=HTTPStatus.CONFLICT,
            details={"current_status": current_status, "action": action},
        )


class VerificationFailedError(DomainError):
    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(
            code="VERIFICATION_FAILED",
            message=f"Post-action verification for tool '{tool_name}' failed: {reason}",
            http_status=HTTPStatus.UNPROCESSABLE_ENTITY,
            details={"tool_name": tool_name, "reason": reason},
        )


class MaxRetriesExceededError(DomainError):
    def __init__(self, tool_name: str, attempts: int) -> None:
        super().__init__(
            code="MAX_RETRIES_EXCEEDED",
            message=f"Tool '{tool_name}' exceeded maximum retry attempts ({attempts}).",
            http_status=HTTPStatus.BAD_GATEWAY,
            details={"tool_name": tool_name, "attempts": attempts},
        )


class BudgetExceededError(DomainError):
    def __init__(self, tokens_used: int, budget: int) -> None:
        super().__init__(
            code="TOKEN_BUDGET_EXCEEDED",
            message=f"Workflow exceeded allocated token budget ({tokens_used} > {budget}).",
            http_status=HTTPStatus.TOO_MANY_REQUESTS,
            details={"tokens_used": tokens_used, "budget": budget},
        )
