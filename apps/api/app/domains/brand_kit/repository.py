"""Scoped query helpers for Brand Kit records."""

from collections.abc import Sequence
from uuid import UUID

from app.domains.brand_kit.models import BrandKit, SocialProof, VoiceSnippet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class BrandKitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID, project_id: UUID) -> BrandKit | None:
        result = await self._session.execute(
            select(BrandKit).where(
                BrandKit.organization_id == organization_id, BrandKit.project_id == project_id
            )
        )
        return result.scalar_one_or_none()

    async def list_voice_snippets(
        self, organization_id: UUID, project_id: UUID
    ) -> Sequence[VoiceSnippet]:
        result = await self._session.execute(
            select(VoiceSnippet)
            .where(
                VoiceSnippet.organization_id == organization_id,
                VoiceSnippet.project_id == project_id,
            )
            .order_by(VoiceSnippet.captured_on.desc(), VoiceSnippet.created_at.desc())
        )
        return result.scalars().all()

    async def list_social_proofs(
        self, organization_id: UUID, project_id: UUID
    ) -> Sequence[SocialProof]:
        result = await self._session.execute(
            select(SocialProof)
            .where(
                SocialProof.organization_id == organization_id,
                SocialProof.project_id == project_id,
            )
            .order_by(SocialProof.created_at.desc())
        )
        return result.scalars().all()

    async def area_exists(self, organization_id: UUID, project_id: UUID, area_id: UUID) -> bool:
        from app.domains.canvas.models import Area

        result = await self._session.execute(
            select(Area.id).where(
                Area.organization_id == organization_id,
                Area.project_id == project_id,
                Area.id == area_id,
            )
        )
        return result.scalar_one_or_none() is not None

    def add(self, record: object) -> None:
        self._session.add(record)
