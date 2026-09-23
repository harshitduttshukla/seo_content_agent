from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.brand_kit.schemas import (
    BrandKitDetailResponse,
    BrandKitResponse,
    SocialProofResponse,
    VoiceSnippetResponse,
)
from app.main import create_app
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from httpx import ASGITransport, AsyncClient


class MockTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://identity.example.com",
            subject="brand",
            email="brand@example.com",
            display_name="Brand",
        )


@pytest.mark.asyncio
async def test_brand_kit_routes_expose_project_scoped_read_and_writes() -> None:
    organization_id, project_id, user_id = uuid4(), uuid4(), uuid4()
    actor = AuthenticatedUser(
        user_id=user_id,
        issuer="https://identity.example.com",
        subject="brand",
        email="brand@example.com",
        display_name="Brand",
    )
    now = datetime.now(UTC)
    kit = BrandKitResponse(
        id=uuid4(),
        spelling="en-GB",
        banned_words=[],
        style="Short",
        vocabulary="",
        tone_profile="",
        profile_provisional=True,
        revision=1,
        updated_at=now,
    )
    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=AsyncMock(),
        token_verifier=MockTokenVerifier(),
    )
    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity", AsyncMock(return_value=actor)
        ),
        patch(
            "app.domains.brand_kit.service.BrandKitService.get",
            AsyncMock(
                return_value=BrandKitDetailResponse(
                    brand_kit=kit, voice_snippets=[], social_proofs=[]
                )
            ),
        ),
        patch(
            "app.domains.brand_kit.service.BrandKitService.upsert", AsyncMock(return_value=kit)
        ) as upsert,
        patch(
            "app.domains.brand_kit.service.BrandKitService.create_voice_snippet",
            AsyncMock(
                return_value=VoiceSnippetResponse(
                    id=uuid4(),
                    source_type="call",
                    source_name="Rodier",
                    captured_on=date(2026, 9, 4),
                    content="Direct",
                    area_id=None,
                    created_at=now,
                )
            ),
        ),
        patch(
            "app.domains.brand_kit.service.BrandKitService.create_social_proof",
            AsyncMock(
                return_value=SocialProofResponse(
                    id=uuid4(),
                    label="Rodier",
                    proof_type="case study",
                    area_ids=[],
                    markets=[],
                    approved=True,
                    created_at=now,
                )
            ),
        ),
    ):
        query = f"organization_id={organization_id}&project_id={project_id}"
        headers = {"Authorization": "Bearer token"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            read = await client.get(f"/api/v3/brand-kit?{query}", headers=headers)
            saved = await client.put(
                f"/api/v3/brand-kit?{query}", headers=headers, json={"spelling": "en-GB"}
            )
            voice = await client.post(
                f"/api/v3/brand-kit/voice-snippets?{query}",
                headers=headers,
                json={
                    "source_type": "call",
                    "source_name": "Rodier",
                    "captured_on": "2026-09-04",
                    "content": "Direct",
                },
            )
            proof = await client.post(
                f"/api/v3/brand-kit/social-proofs?{query}",
                headers=headers,
                json={"label": "Rodier", "proof_type": "case study", "approved": True},
            )
    assert read.status_code == 200
    assert saved.status_code == 200
    assert voice.status_code == 201
    assert proof.status_code == 201
    upsert.assert_awaited_once()
