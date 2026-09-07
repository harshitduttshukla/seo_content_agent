"""API integration tests for Phase 5: Content Briefs, Documents, Chat,
Patches, and SEO Quality.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.domains.content.brief_schemas import ContentBriefDetail
from app.domains.content.document_schemas import (
    AIProposalDetail,
    BlockType,
    ChatMessageDetail,
    ContentBlock,
    ContentDocumentDetail,
)
from app.domains.content.editor_models import BriefStatus, ProposalStatus
from app.domains.seo.quality_service import QualityCheckItem, SEOQualityReport
from app.main import create_app
from app.security.oidc import IdentityClaims
from app.security.principal import AuthenticatedUser
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class MockTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://identity.example.com",
            subject="test-user-sub",
            email="tester@example.com",
            display_name="Tester",
        )


@pytest.fixture
def test_app() -> FastAPI:
    settings = Settings(
        _env_file=None,
        app_env="testing",
        jwt_secret_key="test-secret-key-that-is-at-least-32-chars",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        redis_url="redis://localhost:6379/0",
    )
    app = create_app(settings)
    app.state.token_verifier = MockTokenVerifier()
    return app


@pytest.fixture
def test_actor() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://identity.example.com",
        subject="test-user-sub",
        email="tester@example.com",
        display_name="Tester",
    )


# ---------------------------------------------------------------------------
# Content Briefs API Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_content_brief_api_flow(test_app: FastAPI, test_actor: AuthenticatedUser) -> None:
    project_id = uuid4()
    page_id = uuid4()
    brief_id = uuid4()
    org_id = uuid4()

    mock_brief = ContentBriefDetail(
        id=brief_id,
        organization_id=org_id,
        project_id=project_id,
        website_id=None,
        page_id=page_id,
        seo_guide_id=None,
        version=1,
        status=BriefStatus.DRAFT.value,
        primary_keyword="zero trust architecture",
        secondary_keywords=["microsegmentation", "least privilege"],
        search_intent="INFORMATIONAL",
        target_audience="Security Architects",
        business_goal="Position brand as authority",
        content_type="PILLAR_PAGE",
        recommended_title="Zero Trust Network Architecture",
        recommended_url="/zero-trust-architecture",
        meta_title="Zero Trust Network Architecture - Complete Guide",
        meta_description="Comprehensive guide to zero trust network architecture.",
        target_word_count=2000,
        required_topics=["NIST 800-207", "Zero Trust Pillars"],
        key_entities=["NIST", "IAM"],
        questions_to_answer=["What is Zero Trust?"],
        internal_link_targets=[],
        external_source_requirements=[],
        content_requirements=["Include comparison diagram"],
        brand_requirements={"tone": "authoritative"},
        created_by_id=test_actor.user_id,
        updated_by_id=test_actor.user_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
        return_value=test_actor,
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Get or create brief
            with patch(
                "app.domains.content.brief_service.ContentBriefService.get_or_create_brief",
                AsyncMock(return_value=mock_brief),
            ):
                resp = await client.get(
                    f"/api/v1/content-pages/{page_id}/brief",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
                data = resp.json()["data"]
                assert data["recommended_title"] == "Zero Trust Network Architecture"
                assert data["primary_keyword"] == "zero trust architecture"

            # 2. Update brief
            mock_updated = mock_brief.model_copy(update={"target_word_count": 2500, "version": 2})
            with patch(
                "app.domains.content.brief_service.ContentBriefService.update_brief_endpoint",
                AsyncMock(return_value=mock_updated),
            ):
                resp = await client.put(
                    f"/api/v1/content-briefs/{brief_id}",
                    headers={"Authorization": "Bearer test-token"},
                    json={"target_word_count": 2500},
                )
                assert resp.status_code == 200
                assert resp.json()["data"]["target_word_count"] == 2500

            # 3. Approve brief
            mock_approved = mock_updated.model_copy(
                update={"status": BriefStatus.APPROVED.value, "version": 3}
            )
            with patch(
                "app.domains.content.brief_service.ContentBriefService.approve_brief_endpoint",
                AsyncMock(return_value=mock_approved),
            ):
                resp = await client.post(
                    f"/api/v1/content-briefs/{brief_id}/approve",
                    headers={"Authorization": "Bearer test-token"},
                    json={"change_summary": "Ready for writing"},
                )
                assert resp.status_code == 200
                assert resp.json()["data"]["status"] == "APPROVED"


# ---------------------------------------------------------------------------
# Content Documents API Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_content_document_api_flow(test_app: FastAPI, test_actor: AuthenticatedUser) -> None:
    project_id = uuid4()
    page_id = uuid4()
    doc_id = uuid4()
    org_id = uuid4()
    proposal_id = uuid4()

    mock_doc = ContentDocumentDetail(
        id=doc_id,
        organization_id=org_id,
        project_id=project_id,
        website_id=None,
        page_id=page_id,
        brief_id=None,
        title="Zero Trust Architecture",
        slug="zero-trust-architecture",
        status="DRAFT",
        current_version=1,
        lock_version=1,
        word_count=450,
        plain_text="Zero Trust Architecture\nZero trust assumes breach.",
        target_word_count=2000,
        content_blocks=[
            ContentBlock(
                id="b1",
                type=BlockType.DOCUMENT_TITLE,
                text="Zero Trust Architecture",
            ),
            ContentBlock(
                id="b2",
                type=BlockType.PARAGRAPH,
                text="Zero trust assumes breach.",
            ),
        ],
        created_by_id=test_actor.user_id,
        updated_by_id=test_actor.user_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch(
        "app.domains.users.service.UserService.resolve_identity",
        new_callable=AsyncMock,
        return_value=test_actor,
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Get or create document
            with patch(
                "app.domains.content.document_service.ContentDocumentService.get_or_create_document",
                AsyncMock(return_value=mock_doc),
            ):
                resp = await client.get(
                    f"/api/v1/content-pages/{page_id}/document",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
                assert resp.json()["data"]["title"] == "Zero Trust Architecture"

            # 2. Update document
            mock_updated = mock_doc.model_copy(update={"lock_version": 2, "word_count": 500})
            with patch(
                "app.domains.content.document_service.ContentDocumentService.update_document",
                AsyncMock(return_value=mock_updated),
            ):
                resp = await client.put(
                    f"/api/v1/content-documents/{doc_id}",
                    headers={"Authorization": "Bearer test-token"},
                    json={
                        "lock_version": 1,
                        "content_blocks": [
                            {
                                "id": "b1",
                                "type": "DOCUMENT_TITLE",
                                "text": "Zero Trust Architecture",
                            },
                            {
                                "id": "b2",
                                "type": "PARAGRAPH",
                                "text": "Zero trust assumes breach. Never trust, verify.",
                            },
                        ],
                    },
                )
                assert resp.status_code == 200
                assert resp.json()["data"]["lock_version"] == 2

            # 3. AI Chat Turn
            mock_proposal = AIProposalDetail(
                id=proposal_id,
                document_id=doc_id,
                chat_message_id=None,
                status=ProposalStatus.PROPOSED.value,
                operation_type="replace_block",
                target_block_ids=["b2"],
                old_content={"text": "Zero trust assumes breach."},
                proposed_content={"text": "Expanded and authoritative intro paragraph."},
                diff_summary={"type": "replacement"},
                reason="Refine intro",
                ai_provider="mock",
                model="mock-gpt4",
                reviewed_at=None,
                reviewed_by_id=None,
                applied_at=None,
                applied_version=None,
                created_at=datetime.now(UTC),
            )
            mock_chat_message = ChatMessageDetail(
                id=uuid4(),
                session_id=uuid4(),
                document_id=doc_id,
                role="assistant",
                content="I have proposed an expanded introduction block.",
                context_snapshot={},
                token_usage={"prompt_tokens": 100, "completion_tokens": 50},
                created_at=datetime.now(UTC),
                proposal=mock_proposal,
            )

            with patch(
                "app.domains.content.document_service.ContentDocumentService.chat_and_propose",
                AsyncMock(return_value=mock_chat_message),
            ):
                resp = await client.post(
                    f"/api/v1/content-documents/{doc_id}/chat",
                    headers={"Authorization": "Bearer test-token"},
                    json={"message": "Please expand the intro"},
                )
                assert resp.status_code == 200
                data = resp.json()["data"]
                assert data["content"] == "I have proposed an expanded introduction block."
                assert data["proposal"]["id"] == str(proposal_id)

            # 4. Apply Proposal
            mock_applied_doc = mock_doc.model_copy(update={"current_version": 2, "lock_version": 3})
            with patch(
                "app.domains.content.patch_service.DocumentPatchService.apply_proposal",
                AsyncMock(return_value=mock_applied_doc),
            ):
                resp = await client.post(
                    f"/api/v1/content-documents/{doc_id}/patches/{proposal_id}/apply",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
                assert resp.json()["data"]["current_version"] == 2

            # 5. SEO Quality Report
            mock_report = SEOQualityReport(
                document_id=doc_id,
                title="Zero Trust Architecture",
                word_count=500,
                target_word_count=2000,
                score_percentage=88,
                checks=[
                    QualityCheckItem(
                        name="H1 Heading Presence",
                        status="PASS",
                        message="Document has exactly one primary H1 heading.",
                    ),
                    QualityCheckItem(
                        name="Primary Keyword in H1",
                        status="PASS",
                        message="H1 contains target primary keyword.",
                    ),
                ],
            )
            with patch(
                "app.domains.seo.quality_service.SEOQualityService.evaluate_document",
                AsyncMock(return_value=mock_report),
            ):
                resp = await client.get(
                    f"/api/v1/content-documents/{doc_id}/seo-quality",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
                assert resp.json()["data"]["score_percentage"] == 88
                assert resp.json()["data"]["checks"][0]["status"] == "PASS"
