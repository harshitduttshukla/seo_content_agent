"""V3 site-import routes."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content_cards.schemas import (
    SiteImportRequest,
    SiteImportResponse,
    SiteImportStatusResponse,
)
from app.domains.content_cards.service import SiteImportService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["v3_site_import"])


@router.post("/site-import/run", response_model=ApiResponse[SiteImportResponse])
async def run_site_import(
    payload: SiteImportRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[SiteImportResponse]:
    result = await SiteImportService(session).run_site_import(
        organization_id,
        project_id,
        str(payload.url),
        actor=actor,
        website_id=payload.website_id,
        force_refresh=payload.force_refresh,
    )
    return success(request, result)


@router.get(
    "/site-import/{job_id}/status",
    response_model=ApiResponse[SiteImportStatusResponse],
)
async def get_site_import_status(
    job_id: UUID,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[SiteImportStatusResponse]:
    result = await SiteImportService(session).get_import_status(organization_id, project_id, job_id, actor=actor)
    return success(request, result)
