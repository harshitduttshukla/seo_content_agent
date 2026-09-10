import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from app.config.settings import Settings
from app.main import create_app
from app.security.oidc import IdentityClaims
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


class DeterministicTokenVerifier:
    async def verify(self, token: str) -> IdentityClaims:
        return IdentityClaims(
            issuer="https://test-identity.example/",
            subject=token,
            email=f"{token}@example.test",
            display_name=f"User {token.upper()}",
        )


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    migration_url = os.environ.get("TEST_DATABASE_MIGRATION_URL")
    application_url = os.environ.get("TEST_DATABASE_URL")
    if not migration_url or not application_url:
        pytest.skip("PostgreSQL integration URLs are required")

    previous_url = os.environ.get("DATABASE_MIGRATION_URL")
    os.environ["DATABASE_MIGRATION_URL"] = migration_url
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=application_url,
        DATABASE_MIGRATION_URL=migration_url,
    )
    engine = create_async_engine(application_url, pool_pre_ping=True)
    app = create_app(settings, engine=engine, token_verifier=DeterministicTokenVerifier())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as result:
        yield result
    await engine.dispose()
    if previous_url is None:
        os.environ.pop("DATABASE_MIGRATION_URL", None)
    else:
        os.environ["DATABASE_MIGRATION_URL"] = previous_url


def auth(user: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user}"}


def mutation_headers(user: str, key: str) -> dict[str, str]:
    return auth(user) | {"Idempotency-Key": key}


@pytest.mark.asyncio
async def test_organization_creation_bootstraps_admin_membership(
    client: AsyncClient,
) -> None:
    me = await client.get("/api/v1/users/me", headers=auth("creator"))
    assert me.status_code == 200, me.text

    headers = mutation_headers("creator", "create-bootstrap-org")
    organization = await client.post(
        "/api/v1/organizations",
        headers=headers,
        json={"name": "Bootstrap Organization"},
    )
    assert organization.status_code == 201, organization.text
    organization_id = organization.json()["data"]["id"]

    repeated = await client.post(
        "/api/v1/organizations",
        headers=headers,
        json={"name": "Bootstrap Organization"},
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["data"]["id"] == organization_id

    members = await client.get(
        f"/api/v1/organizations/{organization_id}/members",
        headers=auth("creator"),
    )
    assert members.status_code == 200, members.text
    member_items = members.json()["data"]["items"]
    assert len(member_items) == 1
    assert member_items[0]["user_id"] == me.json()["data"]["id"]
    assert member_items[0]["role"] == "admin"
    assert member_items[0]["status"] == "active"


@pytest.mark.asyncio
async def test_user_cannot_cross_organization_api_or_rls(client: AsyncClient) -> None:
    user_ids: dict[str, str] = {}
    resources: dict[str, dict[str, object]] = {}
    for user in ("a", "b"):
        me = await client.get("/api/v1/users/me", headers=auth(user))
        assert me.status_code == 200, me.text
        user_ids[user] = me.json()["data"]["id"]

        organization = await client.post(
            "/api/v1/organizations",
            headers=mutation_headers(user, f"create-org-{user}"),
            json={"name": f"Organization {user.upper()}"},
        )
        assert organization.status_code == 201, organization.text
        organization_data = organization.json()["data"]

        project = await client.post(
            "/api/v1/projects",
            headers=mutation_headers(user, f"create-project-{user}"),
            json={
                "organization_id": organization_data["id"],
                "name": f"Project {user.upper()}",
            },
        )
        assert project.status_code == 201, project.text
        project_data = project.json()["data"]

        website = await client.post(
            f"/api/v1/projects/{project_data['id']}/websites",
            headers=mutation_headers(user, f"create-website-{user}"),
            json={"name": f"Website {user.upper()}", "url": f"https://{user}.example.test"},
        )
        assert website.status_code == 201, website.text
        resources[user] = {
            "organization": organization_data,
            "project": project_data,
            "website": website.json()["data"],
        }

    foreign_project = resources["b"]["project"]
    assert isinstance(foreign_project, dict)
    foreign_website = resources["b"]["website"]
    assert isinstance(foreign_website, dict)

    read_project = await client.get(f"/api/v1/projects/{foreign_project['id']}", headers=auth("a"))
    update_project = await client.put(
        f"/api/v1/projects/{foreign_project['id']}",
        headers=auth("a"),
        json={
            "name": foreign_project["name"],
            "slug": foreign_project["slug"],
            "description": foreign_project["description"],
            "status": foreign_project["status"],
            "default_locale": foreign_project["default_locale"],
            "default_country": foreign_project["default_country"],
            "revision": foreign_project["revision"],
        },
    )
    delete_project = await client.delete(
        f"/api/v1/projects/{foreign_project['id']}", headers=auth("a")
    )
    read_website = await client.get(f"/api/v1/websites/{foreign_website['id']}", headers=auth("a"))

    for response in (read_project, update_project, delete_project, read_website):
        assert response.status_code == 404, response.text

    application_url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(application_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.user_id', :user_id, true)"),
            {"user_id": user_ids["a"]},
        )
        visible = await connection.scalar(
            text("SELECT count(*) FROM projects WHERE id = :project_id"),
            {"project_id": foreign_project["id"]},
        )
    await engine.dispose()
    assert visible == 0
