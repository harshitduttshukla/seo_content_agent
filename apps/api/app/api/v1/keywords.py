"""API routes for keyword management, CSV imports, and keyword retrieval."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, Request, UploadFile

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.keywords.schemas import (
    KeywordCreate,
    KeywordDeleteResponse,
    KeywordDetail,
    KeywordImportResponse,
    KeywordList,
    KeywordUpdate,
)
from app.domains.keywords.service import KeywordService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["keywords"])


@router.post(
    "/projects/{project_id}/keywords",
    response_model=ApiResponse[KeywordDetail],
    status_code=201,
)
async def create_keyword(
    project_id: UUID,
    payload: KeywordCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordDetail]:
    kw = await KeywordService().create_keyword(
        session,
        actor=actor,
        project_id=project_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, kw)


@router.get(
    "/projects/{project_id}/keywords",
    response_model=ApiResponse[KeywordList],
)
async def list_keywords(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    search: Annotated[str | None, Query()] = None,
    intent: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    min_volume: Annotated[int | None, Query()] = None,
    max_volume: Annotated[int | None, Query()] = None,
    min_difficulty: Annotated[float | None, Query()] = None,
    max_difficulty: Annotated[float | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[KeywordList]:
    kws = await KeywordService().list_keywords(
        session,
        actor=actor,
        project_id=project_id,
        search=search,
        intent=intent,
        status=status,
        min_volume=min_volume,
        max_volume=max_volume,
        min_difficulty=min_difficulty,
        max_difficulty=max_difficulty,
        limit=limit,
        offset=offset,
    )
    return success(request, kws)


@router.get(
    "/projects/{project_id}/keywords/{keyword_id}",
    response_model=ApiResponse[KeywordDetail],
)
async def get_keyword(
    project_id: UUID,
    keyword_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordDetail]:
    kw = await KeywordService().get_keyword(
        session,
        actor=actor,
        project_id=project_id,
        keyword_id=keyword_id,
    )
    return success(request, kw)


@router.put(
    "/projects/{project_id}/keywords/{keyword_id}",
    response_model=ApiResponse[KeywordDetail],
)
async def update_keyword(
    project_id: UUID,
    keyword_id: UUID,
    payload: KeywordUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordDetail]:
    kw = await KeywordService().update_keyword(
        session,
        actor=actor,
        project_id=project_id,
        keyword_id=keyword_id,
        payload=payload,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, kw)


@router.delete(
    "/projects/{project_id}/keywords/{keyword_id}",
    response_model=ApiResponse[KeywordDeleteResponse],
)
async def delete_keyword(
    project_id: UUID,
    keyword_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordDeleteResponse]:
    deleted = await KeywordService().delete_keyword(
        session,
        actor=actor,
        project_id=project_id,
        keyword_id=keyword_id,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, deleted)


@router.post(
    "/projects/{project_id}/keywords/import",
    response_model=ApiResponse[KeywordImportResponse],
    status_code=201,
)
async def import_keywords(
    project_id: UUID,
    file: Annotated[UploadFile, File()],
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordImportResponse]:
    content = await file.read()
    import_res = await KeywordService().import_csv(
        session,
        actor=actor,
        project_id=project_id,
        file_content=content,
        filename=file.filename or "keywords.csv",
        request_id=request.state.request_id if hasattr(request.state, "request_id") else "",
    )
    return success(request, import_res)


@router.get(
    "/projects/{project_id}/keywords/imports/{import_id}",
    response_model=ApiResponse[KeywordImportResponse],
)
async def get_import_status(
    project_id: UUID,
    import_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[KeywordImportResponse]:
    job = await KeywordService().get_import(
        session,
        actor=actor,
        project_id=project_id,
        import_id=import_id,
    )
    return success(request, job)
