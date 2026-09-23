"""Authorization-aware application service for Brand Kit operations."""

from uuid import UUID, uuid4

from app.core.errors import BadRequestError
from app.db.session import set_actor_context, transactional_session
from app.domains.brand_kit.models import BrandKit, SocialProof, VoiceSnippet
from app.domains.brand_kit.repository import BrandKitRepository
from app.domains.brand_kit.schemas import (
    BrandKitDetailResponse,
    BrandKitResponse,
    BrandKitUpsertRequest,
    SocialProofCreateRequest,
    SocialProofResponse,
    VoiceSnippetCreateRequest,
    VoiceSnippetResponse,
)
from app.security.authorization import AuthorizationService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy.ext.asyncio import AsyncSession


class BrandKitService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.repository = BrandKitRepository(session)
        from app.domains.auth.repository import AuthorizationRepository

        self._authorization = AuthorizationService(AuthorizationRepository())

    async def _authorize(
        self,
        organization_id: UUID,
        project_id: UUID,
        actor: AuthenticatedUser,
        permission: PermissionCode,
    ) -> None:
        await set_actor_context(self._session, actor.user_id)
        await self._authorization.require_project(
            self._session,
            user_id=actor.user_id,
            organization_id=organization_id,
            project_id=project_id,
            permission=permission,
        )

    async def get(
        self, organization_id: UUID, project_id: UUID, *, actor: AuthenticatedUser
    ) -> BrandKitDetailResponse:
        async with transactional_session(self._session):
            await self._authorize(organization_id, project_id, actor, PermissionCode.STRATEGY_READ)
            kit = await self.repository.get(organization_id, project_id)
            snippets = await self.repository.list_voice_snippets(organization_id, project_id)
            proofs = await self.repository.list_social_proofs(organization_id, project_id)
        return BrandKitDetailResponse(
            brand_kit=BrandKitResponse.model_validate(kit) if kit else None,
            voice_snippets=[VoiceSnippetResponse.model_validate(item) for item in snippets],
            social_proofs=[SocialProofResponse.model_validate(item) for item in proofs],
        )

    async def upsert(
        self,
        organization_id: UUID,
        project_id: UUID,
        payload: BrandKitUpsertRequest,
        *,
        actor: AuthenticatedUser,
    ) -> BrandKitResponse:
        async with transactional_session(self._session):
            await self._authorize(organization_id, project_id, actor, PermissionCode.STRATEGY_WRITE)
            kit = await self.repository.get(organization_id, project_id)
            values = payload.model_dump()
            if kit is None:
                kit = BrandKit(
                    id=uuid4(), organization_id=organization_id, project_id=project_id, **values
                )
                self.repository.add(kit)
            else:
                for field, value in values.items():
                    setattr(kit, field, value)
                kit.revision += 1
            await self._session.flush()
        return BrandKitResponse.model_validate(kit)

    async def create_voice_snippet(
        self,
        organization_id: UUID,
        project_id: UUID,
        payload: VoiceSnippetCreateRequest,
        *,
        actor: AuthenticatedUser,
    ) -> VoiceSnippetResponse:
        async with transactional_session(self._session):
            await self._authorize(organization_id, project_id, actor, PermissionCode.STRATEGY_WRITE)
            if payload.area_id and not await self.repository.area_exists(
                organization_id, project_id, payload.area_id
            ):
                raise BadRequestError(
                    "The selected area does not belong to this project.", field="area_id"
                )
            snippet = VoiceSnippet(
                id=uuid4(),
                organization_id=organization_id,
                project_id=project_id,
                **payload.model_dump(),
            )
            self.repository.add(snippet)
            await self._session.flush()
        return VoiceSnippetResponse.model_validate(snippet)

    async def create_social_proof(
        self,
        organization_id: UUID,
        project_id: UUID,
        payload: SocialProofCreateRequest,
        *,
        actor: AuthenticatedUser,
    ) -> SocialProofResponse:
        async with transactional_session(self._session):
            await self._authorize(organization_id, project_id, actor, PermissionCode.STRATEGY_WRITE)
            for area_id in payload.area_ids:
                if not await self.repository.area_exists(organization_id, project_id, area_id):
                    raise BadRequestError(
                        "A selected area does not belong to this project.", field="area_ids"
                    )
            values = payload.model_dump()
            values["area_ids"] = [str(area_id) for area_id in payload.area_ids]
            proof = SocialProof(
                id=uuid4(), organization_id=organization_id, project_id=project_id, **values
            )
            self.repository.add(proof)
            await self._session.flush()
        return SocialProofResponse.model_validate(proof)
