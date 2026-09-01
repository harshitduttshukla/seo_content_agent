"""API route integration tests for crawling and content endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config.settings import Settings
from app.core.pagination import PageResult
from app.domains.content.schemas import (
    ContentPageDetail,
    ContentPageSummary,
    PageLinkDetail,
)
from app.domains.crawling.schemas import (
    CrawlJobDetail,
    CrawlStatusSummary,
    WebsiteVerificationDetail,
)
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
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
    )
    engine = AsyncMock()
    return create_app(settings, engine=engine, token_verifier=MockTokenVerifier())


@pytest.mark.asyncio
async def test_website_verification_endpoints(test_app: FastAPI) -> None:
    user_id = uuid4()
    website_id = uuid4()

    mock_verification = WebsiteVerificationDetail(
        website_id=website_id,
        verification_status="verified",
        verified_at=datetime.now(UTC),
        verification_token="ag-verify-abc123456",
        meta_tag_snippet='<meta name="antigravity-verification" content="ag-verify-abc123456">',
        file_snippet="ag-verify-abc123456",
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.domains.crawling.service.CrawlService.get_verification_info",
            new_callable=AsyncMock,
        ) as mock_info,
        patch(
            "app.domains.crawling.service.CrawlService.verify_website",
            new_callable=AsyncMock,
        ) as mock_verify,
    ):
        mock_resolve.return_value = AuthenticatedUser(
            user_id=user_id,
            issuer="https://identity.example.com",
            subject="test-user-sub",
            email="tester@example.com",
            display_name="Tester",
        )
        mock_info.return_value = mock_verification
        mock_verify.return_value = mock_verification

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            # 1. GET /verification
            res_info = await client.get(
                f"/api/v1/websites/{website_id}/verification",
                headers={"Authorization": "Bearer token"},
            )
            assert res_info.status_code == 200
            assert res_info.json()["data"]["verification_status"] == "verified"
            assert res_info.json()["data"]["verification_token"] == "ag-verify-abc123456"

            # 2. POST /verify
            res_verify = await client.post(
                f"/api/v1/websites/{website_id}/verify",
                headers={"Authorization": "Bearer token"},
                json={"method": "http_meta"},
            )
            assert res_verify.status_code == 200
            assert res_verify.json()["data"]["verification_status"] == "verified"


@pytest.mark.asyncio
async def test_crawl_job_routes(test_app: FastAPI) -> None:
    user_id = uuid4()
    org_id = uuid4()
    proj_id = uuid4()
    website_id = uuid4()
    job_id = uuid4()

    mock_job = CrawlJobDetail(
        id=job_id,
        organization_id=org_id,
        project_id=proj_id,
        website_id=website_id,
        status="queued",
        configuration={"max_pages": 100, "max_depth": 3, "respect_robots": True},
        pages_discovered=0,
        pages_crawled=0,
        pages_failed=0,
        pages_skipped=0,
        error_count=0,
        started_at=None,
        completed_at=None,
        requested_by_id=user_id,
        error_summary=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_summary = CrawlStatusSummary(
        website_id=website_id,
        verification_status="verified",
        active_job=mock_job,
        last_job=None,
        total_indexed_pages=42,
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.domains.crawling.service.CrawlService.get_crawl_status",
            new_callable=AsyncMock,
        ) as mock_status,
        patch(
            "app.domains.crawling.service.CrawlService.start_crawl",
            new_callable=AsyncMock,
        ) as mock_start,
        patch(
            "app.domains.crawling.service.CrawlService.get_crawl_job",
            new_callable=AsyncMock,
        ) as mock_get_job,
        patch(
            "app.domains.crawling.service.CrawlService.cancel_crawl",
            new_callable=AsyncMock,
        ) as mock_cancel,
    ):
        mock_resolve.return_value = AuthenticatedUser(
            user_id=user_id,
            issuer="https://identity.example.com",
            subject="test-user-sub",
            email="tester@example.com",
            display_name="Tester",
        )
        mock_status.return_value = mock_summary
        mock_start.return_value = mock_job
        mock_get_job.return_value = mock_job
        mock_cancel.return_value = mock_job

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            # 1. GET /crawl-status
            res_status = await client.get(
                f"/api/v1/websites/{website_id}/crawl-status",
                headers={"Authorization": "Bearer token"},
            )
            assert res_status.status_code == 200
            assert res_status.json()["data"]["total_indexed_pages"] == 42

            # 2. POST /crawl
            res_start = await client.post(
                f"/api/v1/websites/{website_id}/crawl",
                headers={"Authorization": "Bearer token"},
                json={"configuration": {"max_pages": 50, "max_depth": 2}},
            )
            assert res_start.status_code == 202
            assert res_start.json()["data"]["id"] == str(job_id)

            # 3. GET /crawl-jobs/{id}
            res_get = await client.get(
                f"/api/v1/crawl-jobs/{job_id}",
                headers={"Authorization": "Bearer token"},
            )
            assert res_get.status_code == 200
            assert res_get.json()["data"]["status"] == "queued"

            # 4. POST /crawl-jobs/{id}/cancel
            res_cancel = await client.post(
                f"/api/v1/crawl-jobs/{job_id}/cancel",
                headers={"Authorization": "Bearer token"},
            )
            assert res_cancel.status_code == 200


@pytest.mark.asyncio
async def test_page_inventory_routes(test_app: FastAPI) -> None:
    user_id = uuid4()
    org_id = uuid4()
    proj_id = uuid4()
    website_id = uuid4()
    page_id = uuid4()

    mock_summary = ContentPageSummary(
        id=page_id,
        website_id=website_id,
        url="https://example.com/products",
        normalized_url="https://example.com/products",
        canonical_url="https://example.com/products",
        title="Products Catalog",
        http_status=200,
        content_status="indexed",
        word_count=450,
        last_crawled_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    mock_detail = ContentPageDetail(
        id=page_id,
        organization_id=org_id,
        project_id=proj_id,
        website_id=website_id,
        url="https://example.com/products",
        normalized_url="https://example.com/products",
        canonical_url="https://example.com/products",
        title="Products Catalog",
        meta_description="Browse our collection of software tools.",
        language="en",
        http_status=200,
        content_type="text/html",
        word_count=450,
        content_hash="abc123hash",
        content_status="indexed",
        cleaned_content="Products Catalog\nSoftware tools for SEO.",
        structured_content={"type": "document", "blocks": []},
        metadata={"robots": "index, follow"},
        headings=[{"level": 1, "text": "Products Catalog", "order": 1}],
        images=[{"src": "https://example.com/img.png", "alt": "Logo", "title": None}],
        first_seen_at=datetime.now(UTC),
        last_crawled_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_link = PageLinkDetail(
        id=uuid4(),
        website_id=website_id,
        source_page_id=page_id,
        target_url="https://example.com/pricing",
        normalized_target_url="https://example.com/pricing",
        target_page_id=None,
        anchor_text="Pricing",
        rel=None,
        is_internal=True,
        nofollow=False,
        ugc=False,
        sponsored=False,
        discovered_at=datetime.now(UTC),
    )

    with (
        patch(
            "app.domains.users.service.UserService.resolve_identity",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.domains.content.service.ContentService.list_pages",
            new_callable=AsyncMock,
        ) as mock_list_pages,
        patch(
            "app.domains.content.service.ContentService.get_page",
            new_callable=AsyncMock,
        ) as mock_get_page,
        patch(
            "app.domains.content.service.ContentService.list_links",
            new_callable=AsyncMock,
        ) as mock_list_links,
    ):
        mock_resolve.return_value = AuthenticatedUser(
            user_id=user_id,
            issuer="https://identity.example.com",
            subject="test-user-sub",
            email="tester@example.com",
            display_name="Tester",
        )
        mock_list_pages.return_value = PageResult(
            items=[mock_summary], next_cursor=None, has_more=False
        )
        mock_get_page.return_value = mock_detail
        mock_list_links.return_value = [mock_link]

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            # 1. GET /pages
            res_pages = await client.get(
                f"/api/v1/websites/{website_id}/pages?status=indexed&search=products",
                headers={"Authorization": "Bearer token"},
            )
            assert res_pages.status_code == 200
            assert len(res_pages.json()["data"]["items"]) == 1
            assert res_pages.json()["data"]["items"][0]["title"] == "Products Catalog"

            # 2. GET /pages/{id}
            res_detail = await client.get(
                f"/api/v1/websites/{website_id}/pages/{page_id}",
                headers={"Authorization": "Bearer token"},
            )
            assert res_detail.status_code == 200
            assert (
                res_detail.json()["data"]["meta_description"]
                == "Browse our collection of software tools."
            )
            assert len(res_detail.json()["data"]["headings"]) == 1

            # 3. GET /links
            res_links = await client.get(
                f"/api/v1/websites/{website_id}/links",
                headers={"Authorization": "Bearer token"},
            )
            assert res_links.status_code == 200
            assert len(res_links.json()["data"]["items"]) == 1
            assert (
                res_links.json()["data"]["items"][0]["target_url"] == "https://example.com/pricing"
            )
