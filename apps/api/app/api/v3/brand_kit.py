"""V3 Brand Kit routes."""

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.brand_kit.schemas import (
    BrandKitDetailResponse,
    BrandKitResponse,
    BrandKitUpsertRequest,
    SocialProofCreateRequest,
    SocialProofResponse,
    VoiceSnippetCreateRequest,
    VoiceSnippetResponse,
)
from app.domains.brand_kit.service import BrandKitService
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/brand-kit", tags=["v3_brand_kit"])


@router.get("", response_model=ApiResponse[BrandKitDetailResponse])
async def get_brand_kit(
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[BrandKitDetailResponse]:
    result = await BrandKitService(session).get(organization_id, project_id, actor=actor)
    return success(request, result)


@router.put("", response_model=ApiResponse[BrandKitResponse])
async def upsert_brand_kit(
    payload: BrandKitUpsertRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[BrandKitResponse]:
    result = await BrandKitService(session).upsert(
        organization_id, project_id, payload, actor=actor
    )
    return success(request, result)


@router.post(
    "/voice-snippets",
    response_model=ApiResponse[VoiceSnippetResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_voice_snippet(
    payload: VoiceSnippetCreateRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[VoiceSnippetResponse]:
    result = await BrandKitService(session).create_voice_snippet(
        organization_id, project_id, payload, actor=actor
    )
    return success(request, result)


@router.post(
    "/social-proofs",
    response_model=ApiResponse[SocialProofResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_social_proof(
    payload: SocialProofCreateRequest,
    organization_id: UUID,
    project_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[SocialProofResponse]:
    result = await BrandKitService(session).create_social_proof(
        organization_id, project_id, payload, actor=actor
    )
    return success(request, result)
