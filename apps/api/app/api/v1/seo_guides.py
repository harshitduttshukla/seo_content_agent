"""API routes for SEO Guides, structured outlines, rules, and versions."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.seo.schemas import (
    SEOGuideDetail,
    SEOGuideUpdate,
    SEOGuideVersionList,
)
from app.domains.seo.service import SEOGuideService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["seo-guides"])


@router.get(
    "/content-pages/{page_id}/seo-guide",
    response_model=ApiResponse[SEOGuideDetail],
)
async def get_or_create_seo_guide(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[SEOGuideDetail]:
    guide = await SEOGuideService().get_or_create_guide(
        session,
        actor=actor,
        page_id=page_id,
    )
    return success(request, guide)


@router.put(
    "/content-pages/{page_id}/seo-guide",
    response_model=ApiResponse[SEOGuideDetail],
)
async def update_seo_guide(
    page_id: UUID,
    payload: SEOGuideUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[SEOGuideDetail]:
    guide = await SEOGuideService().update_guide(
        session,
        actor=actor,
        page_id=page_id,
        payload=payload,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, guide)


@router.post(
    "/content-pages/{page_id}/seo-guide/approve",
    response_model=ApiResponse[SEOGuideDetail],
)
async def approve_seo_guide(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[SEOGuideDetail]:
    guide = await SEOGuideService().approve_guide(
        session,
        actor=actor,
        page_id=page_id,
        request_id=getattr(request.state, "request_id", ""),
    )
    return success(request, guide)


@router.get(
    "/content-pages/{page_id}/seo-guide/versions",
    response_model=ApiResponse[SEOGuideVersionList],
)
async def list_seo_guide_versions(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[SEOGuideVersionList]:
    versions = await SEOGuideService().list_versions(
        session,
        actor=actor,
        page_id=page_id,
    )
    return success(request, versions)
