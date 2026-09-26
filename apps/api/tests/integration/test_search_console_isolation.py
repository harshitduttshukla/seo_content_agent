"""GSC multi-tenant isolation: runtime role, FORCEd RLS, same-tenant foreign keys,
property↔website coverage and cross-tenant HTTP access.

Two tenants (Alpha, Bravo) are each connected, mapped and synced through the real
service. Runtime access uses the non-owner ``seo_content_app`` role, so RLS applies;
constraint tests write as the owner (superuser, RLS bypassed) so that only the
database constraints stand in the way. Google is FakeGoogle, a test double.
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.api.dependencies import get_current_user
from app.config.settings import Settings
from app.core.errors import DomainError
from app.db.runtime_role import (
    UnsafeDatabaseRole,
    assert_runtime_role_enforces_rls,
    inspect_runtime_role,
)
from app.db.session import set_actor_context
from app.domains.search_console.service import SearchConsoleService
from app.integrations.google_search_console import SiteEntry
from app.main import create_app
from app.security.principal import AuthenticatedUser
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.api.test_v3_demand_api import MockTokenVerifier
from tests.integration import test_search_console as gsc
from tests.integration import test_v3_card_workflow as phase2

pytestmark = pytest.mark.integration

db_engine = phase2.db_engine
session_factory = phase2.session_factory
owner_factory = phase2.owner_factory
pair = phase2.pair

Factory = async_sessionmaker[AsyncSession]
Pair = tuple[dict[str, Any], dict[str, Any]]
GSC_TABLES = ("gsc_connections", "gsc_properties", "gsc_search_analytics")
ALPHA_SITE, BRAVO_SITE = "sc-domain:alpha.test", "sc-domain:bravo.test"


def shared_account() -> gsc.FakeGoogle:
    """One Google account that can read both clients' properties."""
    google = gsc.FakeGoogle()
    google.sites = [SiteEntry(ALPHA_SITE, "siteOwner"), SiteEntry(BRAVO_SITE, "siteOwner")]
    return google


async def _map(sf: Factory, t: dict[str, Any], google: gsc.FakeGoogle, site: str) -> Any:
    async with sf() as session:
        return await gsc.svc(session, google).map_property(
            t["site_id"], site, actor=t["actor"], request_id="r"
        )


@pytest_asyncio.fixture
async def synced(session_factory: Factory, owner_factory: Factory, pair: Pair) -> Pair:
    """Alpha and Bravo each connected, mapped to their own property and synced."""
    alpha, bravo = pair
    for tenant, site in ((alpha, ALPHA_SITE), (bravo, BRAVO_SITE)):
        google = shared_account()
        host = tenant["label"].lower()
        google.pages = [
            [gsc.api_row("2026-09-01", f"{host} q", f"https://{host}.test/", 2, 50, 3.0)]
        ]
        await gsc._connect(session_factory, tenant, google)
        await _map(session_factory, tenant, google, site)
        await gsc._sync(session_factory, tenant, google)
        async with owner_factory() as session:
            ids = (
                await session.execute(
                    text(
                        "SELECT c.id AS connection_id, p.id AS property_id FROM gsc_properties p "
                        "JOIN gsc_connections c ON c.id = p.connection_id WHERE p.project_id = :p"
                    ),
                    {"p": tenant["project_id"]},
                )
            ).one()
        tenant["connection_id"], tenant["property_id"] = ids.connection_id, ids.property_id
    return alpha, bravo


# ── A. Runtime role and RLS ───────────────────────────────────────


@pytest.mark.asyncio
async def test_runtime_role_cannot_bypass_rls(db_engine: AsyncEngine) -> None:
    role = await inspect_runtime_role(db_engine)
    assert role.name == "seo_content_app"
    assert not role.superuser and not role.bypass_rls and role.owned_rls_tables == ()
    await assert_runtime_role_enforces_rls(db_engine)  # does not raise


@pytest.mark.asyncio
async def test_startup_guard_rejects_the_owner_role(owner_factory: Factory) -> None:
    engine = owner_factory.kw["bind"]
    with pytest.raises(UnsafeDatabaseRole) as raised:
        await assert_runtime_role_enforces_rls(engine)
    message = str(raised.value)
    assert "superuser" in message and "postgres:" not in message  # no credentials


@pytest.mark.asyncio
async def test_startup_guard_runs_when_the_app_owns_its_engine(
    owner_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import main

    owner_engine = owner_factory.kw["bind"]
    monkeypatch.setattr(main, "build_engine", lambda _settings: owner_engine)
    app = create_app(Settings(_env_file=None, APP_ENV="test"), token_verifier=MockTokenVerifier())
    with pytest.raises(UnsafeDatabaseRole):
        async with app.router.lifespan_context(app):
            pass


@pytest.mark.asyncio
async def test_gsc_tables_force_rls(owner_factory: Factory) -> None:
    async with owner_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname = ANY(:t) AND relkind = 'r'"
                ),
                {"t": list(GSC_TABLES)},
            )
        ).all()
    assert sorted(rows) == [(t, True, True) for t in GSC_TABLES]


async def _visible(sf: Factory, user_id: UUID | None) -> dict[str, set[UUID]]:
    async with sf() as session, session.begin():
        if user_id is not None:
            await set_actor_context(session, user_id)
        return {
            table: set(
                (await session.execute(text(f"SELECT DISTINCT project_id FROM {table}"))).scalars()
            )
            for table in GSC_TABLES
        }


@pytest.mark.asyncio
async def test_runtime_role_sees_only_its_own_projects_gsc_rows(
    session_factory: Factory, synced: Pair
) -> None:
    alpha, bravo = synced
    for tenant, other in ((alpha, bravo), (bravo, alpha)):
        visible = await _visible(session_factory, tenant["user_id"])
        for table, projects in visible.items():
            assert tenant["project_id"] in projects, table
            assert other["project_id"] not in projects, table
    anonymous = await _visible(session_factory, None)
    assert all(not projects for projects in anonymous.values())


@pytest.mark.asyncio
async def test_runtime_role_cannot_write_another_projects_gsc_rows(
    session_factory: Factory, synced: Pair
) -> None:
    alpha, bravo = synced
    async with session_factory() as session, session.begin():
        await set_actor_context(session, alpha["user_id"])
        for statement in (
            "UPDATE gsc_properties SET site_url = 'sc-domain:evil.test' WHERE project_id = :p",
            "UPDATE gsc_connections SET status = 'disconnected' WHERE project_id = :p",
            "DELETE FROM gsc_search_analytics WHERE project_id = :p",
        ):
            result = await session.execute(text(statement), {"p": bravo["project_id"]})
            assert result.rowcount == 0, statement  # type: ignore[attr-defined]
    async with session_factory() as session:
        with pytest.raises(DBAPIError, match="row-level security"):
            async with session.begin():
                await set_actor_context(session, alpha["user_id"])
                await session.execute(
                    text(
                        "INSERT INTO gsc_search_analytics (id, organization_id, project_id, "
                        "website_id, property_id, date, query, page, clicks, impressions, ctr, "
                        "position, synced_at) VALUES (:id, :o, :p, :w, :prop, '2026-09-01', "
                        "'x', 'https://bravo.test/', 1, 1, 1, 1, now())"
                    ),
                    {
                        "id": uuid4(),
                        "o": bravo["org_id"],
                        "p": bravo["project_id"],
                        "w": bravo["site_id"],
                        "prop": bravo["property_id"],
                    },
                )
    assert (await _visible(session_factory, bravo["user_id"]))["gsc_properties"] == {
        bravo["project_id"]
    }


# ── B. Same-tenant foreign keys (checked as the owner: RLS is not involved) ──


async def _insert_fails(owner_factory: Factory, sql: str, constraint: str, **params: Any) -> None:
    async with owner_factory() as session:
        with pytest.raises(IntegrityError, match=constraint):
            async with session.begin():
                await session.execute(text(sql), params)


PROPERTY_SQL = (
    "INSERT INTO gsc_properties (id, organization_id, project_id, website_id, connection_id, "
    "site_url) VALUES (:id, :o, :p, :w, :c, 'sc-domain:x.test')"
)
ANALYTICS_SQL = (
    "INSERT INTO gsc_search_analytics (id, organization_id, project_id, website_id, "
    "property_id, date, query, page, clicks, impressions, ctr, position, synced_at) "
    "VALUES (:id, :o, :p, :w, :prop, '2026-09-01', 'q', 'https://x.test/', 1, 1, 1, 1, now())"
)


async def _unmapped_website(
    owner_factory: Factory, tenant: dict[str, Any], subdomain: str = "two"
) -> UUID:
    """Another website of the tenant, with no property yet (one property per website)."""
    website_id, host = uuid4(), f"{subdomain}.{tenant['label'].lower()}.test"
    async with owner_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO websites (id, organization_id, project_id, name, base_url, "
                "normalized_host) VALUES (:id, :o, :p, 'Second', :url, :host)"
            ),
            {
                "id": website_id,
                "o": tenant["org_id"],
                "p": tenant["project_id"],
                "url": f"https://{host}",
                "host": host,
            },
        )
    return website_id


@pytest.mark.asyncio
async def test_property_cannot_reference_another_tenants_website_or_connection(
    owner_factory: Factory, synced: Pair
) -> None:
    alpha, bravo = synced
    alpha_2 = await _unmapped_website(owner_factory, alpha)
    bravo_2 = await _unmapped_website(owner_factory, bravo)
    scope = {"id": uuid4(), "o": alpha["org_id"], "p": alpha["project_id"]}
    # Org A + Project A + Website B
    await _insert_fails(
        owner_factory, PROPERTY_SQL, "fk_gsc_properties_org_proj_website",
        **scope, w=bravo_2, c=alpha["connection_id"],
    )  # fmt: skip
    # Org A + Project A + Connection B
    await _insert_fails(
        owner_factory, PROPERTY_SQL, "fk_gsc_properties_org_proj_connection",
        **scope, w=alpha_2, c=bravo["connection_id"],
    )  # fmt: skip
    # A valid property on Alpha's second website is accepted …
    async with owner_factory() as session, session.begin():
        await session.execute(
            text(PROPERTY_SQL), {**scope, "w": alpha_2, "c": alpha["connection_id"]}
        )
    # … but it cannot be moved to another tenant's website afterwards.
    await _insert_fails(
        owner_factory,
        "UPDATE gsc_properties SET website_id = :w WHERE id = :prop",
        "fk_gsc_properties_org_proj_website",
        w=bravo_2,
        prop=scope["id"],
    )
    # A property that has rows cannot move at all: its rows keep it on its website.
    await _insert_fails(
        owner_factory,
        "UPDATE gsc_properties SET website_id = :w WHERE id = :prop",
        "fk_gsc_search_analytics_org_proj_website_property",
        w=await _unmapped_website(owner_factory, alpha, "three"),
        prop=alpha["property_id"],
    )


@pytest.mark.asyncio
async def test_analytics_row_cannot_reference_another_tenants_property(
    owner_factory: Factory, synced: Pair
) -> None:
    alpha, bravo = synced
    alpha_2 = await _unmapped_website(owner_factory, alpha)
    fk = "fk_gsc_search_analytics_org_proj_website_property"
    scope = {"id": uuid4(), "o": alpha["org_id"], "p": alpha["project_id"]}
    # Org A + Project A + Property B (with B's or A's website)
    await _insert_fails(
        owner_factory, ANALYTICS_SQL, fk, **scope, w=bravo["site_id"], prop=bravo["property_id"]
    )
    await _insert_fails(
        owner_factory, ANALYTICS_SQL, fk, **scope, w=alpha["site_id"], prop=bravo["property_id"]
    )
    # Same tenant, but a website other than the property's.
    await _insert_fails(
        owner_factory, ANALYTICS_SQL, fk, **scope, w=alpha_2, prop=alpha["property_id"]
    )
    # The valid combination is accepted, so the failures above are the constraint's doing.
    async with owner_factory() as session, session.begin():
        await session.execute(
            text(ANALYTICS_SQL), {**scope, "w": alpha["site_id"], "prop": alpha["property_id"]}
        )


# ── E. One Google account, several clients' properties ────────────


@pytest.mark.asyncio
async def test_shared_account_cannot_map_another_clients_property(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    google = shared_account()  # the account can read Alpha's and Bravo's properties
    google.sites.append(SiteEntry("https://www.bravo.test/", "siteOwner"))
    await gsc._connect(session_factory, alpha, google)
    for site in (BRAVO_SITE, "https://www.bravo.test/"):
        with pytest.raises(DomainError) as raised:
            await _map(session_factory, alpha, google, site)
        assert raised.value.code == "GSC_PROPERTY_WEBSITE_MISMATCH"
        assert raised.value.status_code == 422
    async with owner_factory() as session:
        mapped = await session.scalar(
            text("SELECT count(*) FROM gsc_properties WHERE project_id = :p"),
            {"p": alpha["project_id"]},
        )
    assert mapped == 0
    assert (await _map(session_factory, alpha, google, ALPHA_SITE)).site_url == ALPHA_SITE


# ── D. Cross-tenant HTTP access ───────────────────────────────────


@pytest_asyncio.fixture
async def http(
    db_engine: AsyncEngine,
    session_factory: Factory,
    synced: Pair,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    """The real app on the application-role engine; the bearer token names the tenant."""
    google = shared_account()
    monkeypatch.setattr(SearchConsoleService, "_client", lambda self: google)
    monkeypatch.setattr(SearchConsoleService, "_cipher", lambda self: gsc.CIPHER)
    alpha, bravo = synced
    actors = {"alpha": alpha["actor"], "bravo": bravo["actor"]}

    async def current_user(request: Request) -> AuthenticatedUser:
        return actors[request.headers["authorization"].removeprefix("Bearer ")]

    app = create_app(
        Settings(_env_file=None, APP_ENV="test"),
        engine=db_engine,
        session_factory=session_factory,
        token_verifier=MockTokenVerifier(),
    )
    app.dependency_overrides[get_current_user] = current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def as_user(name: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {name}"}


@pytest.mark.asyncio
async def test_user_b_cannot_reach_user_a_gsc_resources_over_http(
    http: AsyncClient, synced: Pair
) -> None:
    alpha, bravo = synced
    p, w = alpha["project_id"], alpha["site_id"]
    attempts = [
        ("GET", f"/api/v1/projects/{p}/search-console", None),  # status + sync history
        ("POST", f"/api/v1/projects/{p}/search-console/connect", None),
        ("GET", f"/api/v1/projects/{p}/search-console/properties", None),
        ("DELETE", f"/api/v1/projects/{p}/search-console/connection", None),
        ("PUT", f"/api/v1/websites/{w}/search-console/property", {"site_url": BRAVO_SITE}),
        ("POST", f"/api/v1/websites/{w}/search-console/sync", {}),
        ("GET", f"/api/v1/websites/{w}/search-console/analytics", None),
        # Client-supplied tenant ids are not accepted as a way in.
        (
            "GET",
            f"/api/v1/websites/{w}/search-console/analytics?organization_id={alpha['org_id']}",
            None,
        ),
    ]
    for method, path, body in attempts:
        response = await http.request(method, path, json=body, headers=as_user("bravo"))
        assert response.status_code == 404, (method, path, response.text)
        for secret in (ALPHA_SITE, "alpha q", str(alpha["site_id"])):
            assert secret not in response.text, (method, path)

    # Alpha's connection, mapping, sync history and rows are untouched.
    status = await http.get(f"/api/v1/projects/{p}/search-console", headers=as_user("alpha"))
    data = status.json()["data"]
    assert data["state"] == "connected"
    [site] = data["websites"]
    assert site["property"]["site_url"] == ALPHA_SITE
    assert site["last_sync"]["status"] == "completed"
    rows = await http.get(
        f"/api/v1/websites/{w}/search-console/analytics?start_date=2026-08-27&end_date=2026-09-23",
        headers=as_user("alpha"),
    )
    assert rows.json()["data"]["totals"]["rows"] == 1

    # Bravo's own status lists only Bravo's website and history.
    own = await http.get(
        f"/api/v1/projects/{bravo['project_id']}/search-console", headers=as_user("bravo")
    )
    assert [s["website_id"] for s in own.json()["data"]["websites"]] == [str(bravo["site_id"])]
    assert ALPHA_SITE not in own.text and str(alpha["site_id"]) not in own.text


@pytest.mark.asyncio
async def test_oauth_state_cannot_be_completed_by_another_tenant_over_http(
    http: AsyncClient, synced: Pair
) -> None:
    alpha, _ = synced
    start = await http.post(
        f"/api/v1/projects/{alpha['project_id']}/search-console/connect", headers=as_user("alpha")
    )
    assert start.status_code == 200, start.text
    state = start.json()["data"]["authorization_url"].split("state=", 1)[1]
    stolen = await http.post(
        "/api/v1/search-console/oauth/callback",
        json={"code": "good-code", "state": state},
        headers=as_user("bravo"),
    )
    assert stolen.status_code == 400
    assert stolen.json()["errors"][0]["code"] == "GSC_OAUTH_STATE_INVALID"
    # The rightful user can still finish with the same state.
    done = await http.post(
        "/api/v1/search-console/oauth/callback",
        json={"code": "good-code", "state": state},
        headers=as_user("alpha"),
    )
    assert done.status_code == 200, done.text


@pytest.mark.asyncio
async def test_mapping_another_clients_property_is_rejected_over_http(
    http: AsyncClient, synced: Pair
) -> None:
    _, bravo = synced
    response = await http.put(
        f"/api/v1/websites/{bravo['site_id']}/search-console/property",
        json={"site_url": ALPHA_SITE},
        headers=as_user("bravo"),
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "GSC_PROPERTY_WEBSITE_MISMATCH"
