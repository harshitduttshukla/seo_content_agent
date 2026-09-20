"""Integration tests for V3 Canvas/Demand/SiteImport RLS Actor Context setup."""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.domains.auth.models import OrganizationMember, ProjectMember
from app.domains.canvas.models import Canvas
from app.domains.canvas.service import CanvasService
from app.domains.demand.models import DemandNode, DemandNodeOrigin, DemandNodeStatus
from app.domains.demand.service import DemandService
from app.domains.content_cards.models import ContentCard, ContentCardKind, ContentCardOrigin
from app.domains.content_cards.service import SiteImportService
from app.domains.job_runs.models import JobRun, JobRunStatus
from app.domains.organizations.models import Organization
from app.domains.projects.models import Project
from app.domains.users.models import User
from app.security.principal import AuthenticatedUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.integration

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/seo_content",
)

# Phase 1 UUIDs for roles
ADMIN_ROLE_ID = UUID("00000000-0000-0000-0000-000000000001")
MEMBER_ROLE_ID = UUID("00000000-0000-0000-0000-000000000002")

@pytest_asyncio.fixture
async def db_engine():
    # Use non-superuser application role to properly test RLS
    test_db_url = DATABASE_URL.replace("postgres:postgres", "seo_content_app:seo_content_app")
    engine = create_async_engine(test_db_url, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def tenant_fixture(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[dict[str, Any]]:
    """Seeds a test tenant with a non-admin user and relevant V3 domain objects."""
    # We must seed as postgres superuser to bypass RLS during setup
    setup_engine = create_async_engine(DATABASE_URL, echo=False)
    setup_factory = async_sessionmaker(setup_engine, expire_on_commit=False)
    
    org_id = uuid4()
    user_id = uuid4()
    proj_id = uuid4()
    canvas_id = uuid4()
    demand_id = uuid4()
    job_run_id = uuid4()
    
    actor = AuthenticatedUser(
        user_id=user_id,
        issuer="https://test.identity.example",
        subject=f"sub-test-{user_id.hex[:8]}",
        email=f"test-{user_id.hex[:8]}@example.test",
        display_name="User Test",
    )

    async with setup_factory() as session:
        # Org + User
        session.add(
            Organization(
                id=org_id, name="Org Test", slug=f"org-test-{org_id.hex[:8]}"
            )
        )
        session.add(
            User(
                id=user_id,
                email=actor.email,
                normalized_email=actor.email,
                identity_issuer=actor.issuer,
                identity_subject=actor.subject,
                display_name=actor.display_name,
            )
        )
        await session.flush()

        # Org membership (MEMBER, not admin)
        session.add(
            OrganizationMember(
                organization_id=org_id,
                user_id=user_id,
                role_id=MEMBER_ROLE_ID,
                status="active",
                joined_at=datetime.now(UTC),
            )
        )
        await session.flush()

        # Project
        session.add(
            Project(
                id=proj_id,
                organization_id=org_id,
                name="Project Test",
                slug=f"proj-test-{proj_id.hex[:8]}",
            )
        )
        await session.flush()

        # Project membership (MEMBER, not admin)
        session.add(
            ProjectMember(
                organization_id=org_id,
                project_id=proj_id,
                user_id=user_id,
                role_id=MEMBER_ROLE_ID,
            )
        )
        await session.flush()
        
        # V3 Canvas
        session.add(
            Canvas(
                id=canvas_id,
                organization_id=org_id,
                project_id=proj_id,
                product_line=None,
            )
        )
        await session.flush()
        
        # V3 Demand Node
        session.add(
            DemandNode(
                id=demand_id,
                organization_id=org_id,
                project_id=proj_id,
                type="keyword",
                text="test keyword",
                status=DemandNodeStatus.PENDING_CLASSIFY,
                origin=DemandNodeOrigin.UPLOAD,
            )
        )
        await session.flush()
        
        # V3 Site Import Job Run
        session.add(
            JobRun(
                id=job_run_id,
                organization_id=org_id,
                project_id=proj_id,
                job_type="site_import",
                prompt_version="v3.site-import.v1",
                model="deterministic",
                provider="internal",
                status=JobRunStatus.COMPLETED,
                triggered_by=str(user_id),
                entity_type="project",
                entity_id=proj_id,
                input_data={"url": "https://example.com"},
            )
        )
        await session.flush()
        await session.commit()
    
    await setup_engine.dispose()
    
    yield {
        "org_id": org_id,
        "proj_id": proj_id,
        "user_id": user_id,
        "actor": actor,
        "canvas_id": canvas_id,
        "demand_id": demand_id,
        "job_run_id": job_run_id,
    }

@pytest.mark.asyncio
async def test_canvas_service_rls_actor_context(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_fixture: dict[str, Any],
) -> None:
    """Verifies that CanvasService properly configures RLS to allow non-admin members."""
    org_id = tenant_fixture["org_id"]
    proj_id = tenant_fixture["proj_id"]
    actor = tenant_fixture["actor"]
    
    async with session_factory() as session:
        service = CanvasService(session)
        # Should not raise ResourceNotFound("project")
        result = await service.list_canvases(org_id, proj_id, actor=actor)
        assert result.company_canvas is not None
        assert result.company_canvas.id == tenant_fixture["canvas_id"]


@pytest.mark.asyncio
async def test_demand_service_rls_actor_context(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_fixture: dict[str, Any],
) -> None:
    """Verifies that DemandService properly configures RLS to allow non-admin members."""
    org_id = tenant_fixture["org_id"]
    proj_id = tenant_fixture["proj_id"]
    actor = tenant_fixture["actor"]
    
    async with session_factory() as session:
        service = DemandService(session)
        # Should not raise ResourceNotFound("project")
        result = await service.list_nodes(
            org_id, proj_id, status=None, page=1, page_size=10, actor=actor
        )
        assert len(result.items) == 1
        assert result.items[0].id == tenant_fixture["demand_id"]


@pytest.mark.asyncio
async def test_site_import_service_rls_actor_context(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_fixture: dict[str, Any],
) -> None:
    """Verifies that SiteImportService properly configures RLS to allow non-admin members."""
    org_id = tenant_fixture["org_id"]
    proj_id = tenant_fixture["proj_id"]
    job_run_id = tenant_fixture["job_run_id"]
    actor = tenant_fixture["actor"]
    
    async with session_factory() as session:
        service = SiteImportService(session)
        # Should not raise ResourceNotFound("project")
        result = await service.get_import_status(org_id, proj_id, job_run_id, actor=actor)
        assert result.job_run_id == job_run_id
        assert result.status == JobRunStatus.COMPLETED
