"""Integration tests for V3 Canvas/Demand/SiteImport RLS Actor Context setup."""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.core.errors import ResourceNotFound
from app.domains.auth.models import OrganizationMember, ProjectMember
from app.domains.canvas.models import Area, Canvas, Claim
from app.domains.canvas.service import CanvasService
from app.domains.content_cards.service import SiteImportService
from app.domains.demand.models import DemandNode, DemandNodeOrigin, DemandNodeStatus
from app.domains.demand.service import DemandService
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
    area_id = uuid4()
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
        session.add(Organization(id=org_id, name="Org Test", slug=f"org-test-{org_id.hex[:8]}"))
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

        session.add(
            Area(
                id=area_id,
                organization_id=org_id,
                project_id=proj_id,
                canvas_id=canvas_id,
                parent_id=None,
                name="International sales",
                default_argument_id=None,
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
        "area_id": area_id,
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
async def test_area_list_service_rls_actor_context(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_fixture: dict[str, Any],
) -> None:
    async with session_factory() as session:
        result = await CanvasService(session).list_areas(
            tenant_fixture["org_id"],
            tenant_fixture["proj_id"],
            canvas_id=tenant_fixture["canvas_id"],
            actor=tenant_fixture["actor"],
        )
    assert [(area.id, area.name) for area in result] == [
        (tenant_fixture["area_id"], "International sales")
    ]


@pytest.mark.asyncio
async def test_area_list_denies_actor_without_project_membership(
    session_factory: async_sessionmaker[AsyncSession], tenant_fixture: dict[str, Any]
) -> None:
    outsider = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://test.identity.example",
        subject="area-outsider",
        email="area-outsider@example.test",
        display_name="Area Outsider",
    )
    async with session_factory() as session:
        with pytest.raises(ResourceNotFound):
            await CanvasService(session).list_areas(
                tenant_fixture["org_id"],
                tenant_fixture["proj_id"],
                canvas_id=None,
                actor=outsider,
            )


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
async def test_demand_service_denies_actor_without_project_membership(
    session_factory: async_sessionmaker[AsyncSession], tenant_fixture: dict[str, Any]
) -> None:
    outsider = AuthenticatedUser(
        user_id=uuid4(),
        issuer="https://test.identity.example",
        subject="outsider",
        email="outsider@example.test",
        display_name="Outsider",
    )
    async with session_factory() as session:
        with pytest.raises(ResourceNotFound):
            await DemandService(session).list_nodes(
                tenant_fixture["org_id"],
                tenant_fixture["proj_id"],
                status=None,
                page=1,
                page_size=10,
                actor=outsider,
            )


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


@pytest.mark.asyncio
async def test_cross_tenant_approve_denied(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verifies that Tenant A cannot approve a Claim belonging to Tenant B.

    Exercises:
    1. Cross-org attempt with Tenant B's org/proj -> denied with ResourceNotFound("project").
    2. Cross-org attempt with Tenant A's org/proj but Tenant B's claim_id -> denied.
    3. Confirms Tenant B's claim remains unapproved in the database.
    4. Confirms Tenant B's member can legitimately approve the claim.
    """
    setup_engine = create_async_engine(DATABASE_URL, echo=False)
    setup_factory = async_sessionmaker(setup_engine, expire_on_commit=False)

    org_a = uuid4()
    user_a = uuid4()
    proj_a = uuid4()
    canvas_a = uuid4()
    claim_a = uuid4()

    org_b = uuid4()
    user_b = uuid4()
    proj_b = uuid4()
    canvas_b = uuid4()
    claim_b = uuid4()

    actor_a = AuthenticatedUser(
        user_id=user_a,
        issuer="https://test.identity.example",
        subject=f"sub-a-{user_a.hex[:8]}",
        email=f"a-{user_a.hex[:8]}@example.test",
        display_name="User A",
    )
    actor_b = AuthenticatedUser(
        user_id=user_b,
        issuer="https://test.identity.example",
        subject=f"sub-b-{user_b.hex[:8]}",
        email=f"b-{user_b.hex[:8]}@example.test",
        display_name="User B",
    )

    async with setup_factory() as session:
        # Tenant A
        session.add(Organization(id=org_a, name="Org A", slug=f"org-a-{org_a.hex[:8]}"))
        session.add(
            User(
                id=user_a,
                email=actor_a.email,
                normalized_email=actor_a.email,
                identity_issuer=actor_a.issuer,
                identity_subject=actor_a.subject,
                display_name=actor_a.display_name,
            )
        )
        await session.flush()
        session.add(
            OrganizationMember(
                organization_id=org_a,
                user_id=user_a,
                role_id=MEMBER_ROLE_ID,
                status="active",
                joined_at=datetime.now(UTC),
            )
        )
        session.add(
            Project(
                id=proj_a,
                organization_id=org_a,
                name="Proj A",
                slug=f"proj-a-{proj_a.hex[:8]}",
            )
        )
        await session.flush()
        session.add(
            ProjectMember(
                organization_id=org_a,
                project_id=proj_a,
                user_id=user_a,
                role_id=MEMBER_ROLE_ID,
            )
        )
        session.add(
            Canvas(
                id=canvas_a,
                organization_id=org_a,
                project_id=proj_a,
                product_line=None,
            )
        )
        session.add(
            Claim(
                id=claim_a,
                organization_id=org_a,
                project_id=proj_a,
                canvas_id=canvas_a,
                argument_id=None,
                row="pitch",
                text="Pitch A",
                evidence="",
                approved=False,
                version=1,
            )
        )

        # Tenant B
        session.add(Organization(id=org_b, name="Org B", slug=f"org-b-{org_b.hex[:8]}"))
        session.add(
            User(
                id=user_b,
                email=actor_b.email,
                normalized_email=actor_b.email,
                identity_issuer=actor_b.issuer,
                identity_subject=actor_b.subject,
                display_name=actor_b.display_name,
            )
        )
        await session.flush()
        session.add(
            OrganizationMember(
                organization_id=org_b,
                user_id=user_b,
                role_id=MEMBER_ROLE_ID,
                status="active",
                joined_at=datetime.now(UTC),
            )
        )
        session.add(
            Project(
                id=proj_b,
                organization_id=org_b,
                name="Proj B",
                slug=f"proj-b-{proj_b.hex[:8]}",
            )
        )
        await session.flush()
        session.add(
            ProjectMember(
                organization_id=org_b,
                project_id=proj_b,
                user_id=user_b,
                role_id=MEMBER_ROLE_ID,
            )
        )
        session.add(
            Canvas(
                id=canvas_b,
                organization_id=org_b,
                project_id=proj_b,
                product_line=None,
            )
        )
        session.add(
            Claim(
                id=claim_b,
                organization_id=org_b,
                project_id=proj_b,
                canvas_id=canvas_b,
                argument_id=None,
                row="pitch",
                text="Pitch B",
                evidence="Evidence B",
                approved=False,
                version=1,
            )
        )

        await session.flush()
        await session.commit()

    await setup_engine.dispose()

    # Step 1: User A tries to approve Claim B using Tenant B's org and proj -> denied
    async with session_factory() as session:
        service = CanvasService(session)
        with pytest.raises(ResourceNotFound):
            await service.approve_claim(org_b, proj_b, claim_b, actor=actor_a)

    # Step 2: User A tries to approve Claim B using Tenant A's org and proj -> denied
    async with session_factory() as session:
        service = CanvasService(session)
        with pytest.raises(ResourceNotFound):
            await service.approve_claim(org_a, proj_a, claim_b, actor=actor_a)

    # Step 3: Verify Claim B remains unapproved in the database
    async with session_factory() as session:
        service = CanvasService(session)
        canvas_b_data = await service.get_canvas(org_b, proj_b, canvas_b, actor=actor_b)
        assert canvas_b_data.pitch_claim is not None
        assert canvas_b_data.pitch_claim.approved is False

    # Step 4: User B can legitimately approve Claim B
    async with session_factory() as session:
        service = CanvasService(session)
        approved_b = await service.approve_claim(org_b, proj_b, claim_b, actor=actor_b)
        assert approved_b.id == claim_b
        assert approved_b.approved is True
        assert approved_b.approved_by == user_b
