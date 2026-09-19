"""API routes for Content Documents, Blocks, Concurrency, Versions, Chat, and Proposals."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.responses import success
from app.domains.content.document_schemas import (
    AIProposalDetail,
    ChatMessageDetail,
    ChatMessageRequest,
    ChatSessionDetail,
    ContentDocumentDetail,
    ContentDocumentUpdate,
    ContentDocumentVersionDetail,
    ContentDocumentVersionList,
    RestoreVersionRequest,
)
from app.domains.content.document_service import ContentDocumentService
from app.domains.content.patch_service import DocumentPatchService
from app.domains.seo.quality_service import SEOQualityReport, SEOQualityService
from app.schemas.common import ApiResponse

router = APIRouter(tags=["content-documents"])


@router.get(
    "/content-pages/{page_id}/document",
    response_model=ApiResponse[ContentDocumentDetail],
)
async def get_or_create_document(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentDocumentDetail]:
    doc = await ContentDocumentService().get_or_create_document(
        session,
        actor=actor,
        page_id=page_id,
    )
    return success(request, doc)


@router.post(
    "/content-pages/{page_id}/document",
    response_model=ApiResponse[ContentDocumentDetail],
    status_code=201,
)
async def initialize_document(
    page_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentDocumentDetail]:
    doc = await ContentDocumentService().get_or_create_document(
        session,
        actor=actor,
        page_id=page_id,
    )
    return success(request, doc)


@router.put(
    "/content-documents/{document_id}",
    response_model=ApiResponse[ContentDocumentDetail],
)
async def update_document(
    document_id: UUID,
    payload: ContentDocumentUpdate,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentDocumentDetail]:
    doc = await ContentDocumentService().update_document(
        session,
        actor=actor,
        document_id=document_id,
        payload=payload,
    )
    return success(request, doc)


@router.get(
    "/content-documents/{document_id}/versions",
    response_model=ApiResponse[ContentDocumentVersionList],
)
async def list_document_versions(
    document_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentDocumentVersionList]:
    versions = await ContentDocumentService().list_versions(
        session,
        actor=actor,
        document_id=document_id,
    )
    return success(request, versions)


@router.get(
    "/content-documents/{document_id}/versions/{version}",
    response_model=ApiResponse[ContentDocumentVersionDetail],
)
async def get_document_version(
    document_id: UUID,
    version: int,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentDocumentVersionDetail]:
    v = await ContentDocumentService().get_version(
        session,
        actor=actor,
        document_id=document_id,
        version_num=version,
    )
    return success(request, v)


@router.post(
    "/content-documents/{document_id}/restore/{version}",
    response_model=ApiResponse[ContentDocumentDetail],
)
async def restore_document_version(
    document_id: UUID,
    version: int,
    payload: RestoreVersionRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentDocumentDetail]:
    doc = await ContentDocumentService().restore_version(
        session,
        actor=actor,
        document_id=document_id,
        version_num=version,
        change_summary=payload.change_summary,
    )
    return success(request, doc)


@router.post(
    "/content-documents/{document_id}/chat",
    response_model=ApiResponse[ChatMessageDetail],
)
async def chat_with_document(
    document_id: UUID,
    payload: ChatMessageRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ChatMessageDetail]:
    chat_response = await ContentDocumentService().chat_and_propose(
        session,
        actor=actor,
        document_id=document_id,
        payload=payload,
    )
    return success(request, chat_response)


@router.get(
    "/content-documents/{document_id}/chat",
    response_model=ApiResponse[ChatSessionDetail],
)
async def get_chat_history(
    document_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ChatSessionDetail]:
    chat_session = await ContentDocumentService().get_chat_session(
        session,
        actor=actor,
        document_id=document_id,
    )
    return success(request, chat_session)


@router.post(
    "/content-documents/{document_id}/patches/{patch_id}/apply",
    response_model=ApiResponse[ContentDocumentDetail],
)
async def apply_patch(
    document_id: UUID,
    patch_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[ContentDocumentDetail]:
    doc = await DocumentPatchService().apply_proposal(
        session,
        actor=actor,
        proposal_id=patch_id,
        document_id=document_id,
    )
    return success(request, doc)


@router.post(
    "/content-documents/{document_id}/patches/{patch_id}/reject",
    response_model=ApiResponse[AIProposalDetail],
)
async def reject_patch(
    document_id: UUID,
    patch_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[AIProposalDetail]:
    prop = await DocumentPatchService().reject_proposal(
        session,
        actor=actor,
        proposal_id=patch_id,
        document_id=document_id,
    )
    return success(request, AIProposalDetail.model_validate(prop))


@router.get(
    "/content-documents/{document_id}/seo-quality",
    response_model=ApiResponse[SEOQualityReport],
)
@router.get(
    "/content-documents/{document_id}/quality-check",
    response_model=ApiResponse[SEOQualityReport],
)
async def evaluate_document_quality(
    document_id: UUID,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ApiResponse[SEOQualityReport]:
    report = await SEOQualityService().evaluate_document(
        session,
        actor=actor,
        document_id=document_id,
    )
    return success(request, report)
