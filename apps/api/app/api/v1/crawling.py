"""API routes for website verification and crawl job orchestration."""

from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.crawling.schemas import (
    CrawlJobCreate,
    CrawlJobDetail,
    CrawlJobList,
    CrawlStatusSummary,
    WebsiteVerificationDetail,
    WebsiteVerificationRequest,
)
from app.domains.crawling.service import CrawlService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["crawling"])


@router.get(
    "/websites/{website_id}/verification",
    response_model=ApiResponse[WebsiteVerificationDetail],
)
async def get_verification_info(
    website_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[WebsiteVerificationDetail]:
    detail = await CrawlService().get_verification_info(session, actor=actor, website_id=website_id)
    return success(request, detail)


@router.post(
    "/websites/{website_id}/verify",
    response_model=ApiResponse[WebsiteVerificationDetail],
)
async def verify_website(
    website_id: UUID,
    payload: WebsiteVerificationRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[WebsiteVerificationDetail]:
    detail = await CrawlService().verify_website(
        session,
        actor=actor,
        website_id=website_id,
        method=payload.method,
        request_id=request.state.request_id,
    )
    return success(request, detail)


@router.get(
    "/websites/{website_id}/crawl-status",
    response_model=ApiResponse[CrawlStatusSummary],
)
async def get_crawl_status(
    website_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[CrawlStatusSummary]:
    summary = await CrawlService().get_crawl_status(session, actor=actor, website_id=website_id)
    return success(request, summary)


@router.post(
    "/websites/{website_id}/crawl",
    response_model=ApiResponse[CrawlJobDetail],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_crawl(
    website_id: UUID,
    payload: CrawlJobCreate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[CrawlJobDetail]:
    job = await CrawlService().start_crawl(
        session,
        actor=actor,
        website_id=website_id,
        config=payload.configuration,
        request_id=request.state.request_id,
    )
    return success(request, job)


@router.get(
    "/websites/{website_id}/crawl-jobs",
    response_model=ApiResponse[CrawlJobList],
)
async def list_crawl_jobs(
    website_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[CrawlJobList]:
    jobs = await CrawlService().list_crawl_jobs(
        session, actor=actor, website_id=website_id, limit=limit
    )
    return success(request, jobs)


@router.get(
    "/crawl-jobs/{crawl_job_id}",
    response_model=ApiResponse[CrawlJobDetail],
)
async def get_crawl_job(
    crawl_job_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[CrawlJobDetail]:
    job = await CrawlService().get_crawl_job(session, actor=actor, crawl_job_id=crawl_job_id)
    return success(request, job)


@router.post(
    "/crawl-jobs/{crawl_job_id}/cancel",
    response_model=ApiResponse[CrawlJobDetail],
)
async def cancel_crawl(
    crawl_job_id: UUID, request: Request, session: SessionDep, actor: CurrentUserDep
) -> ApiResponse[CrawlJobDetail]:
    job = await CrawlService().cancel_crawl(
        session, actor=actor, crawl_job_id=crawl_job_id, request_id=request.state.request_id
    )
    return success(request, job)
