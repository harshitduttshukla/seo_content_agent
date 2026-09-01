"""Response-envelope construction with request metadata."""

from fastapi import Request

from app.schemas.common import ApiResponse, ResponseMeta


def success[DataT](
    request: Request,
    data: DataT,
    *,
    next_cursor: str | None = None,
    has_more: bool | None = None,
) -> ApiResponse[DataT]:
    return ApiResponse(
        data=data,
        meta=ResponseMeta(
            request_id=request.state.request_id,
            next_cursor=next_cursor,
            has_more=has_more,
        ),
        errors=[],
    )
