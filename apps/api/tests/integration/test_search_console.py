"""Integration tests for the read-only GSC integration (Phase 6A).

PostgreSQL as the non-superuser application role, so RLS applies. Google is replaced
by FakeGoogle, a test double implementing the adapter's methods: nothing here calls
Google or uses real credentials.
"""

import json
from datetime import date
from typing import Any
from uuid import UUID

import pytest
from app.core.errors import DomainError, PermissionDenied, ResourceNotFound
from app.domains.search_console import service as gsc_service
from app.domains.search_console.normalize import TokenCipher
from app.domains.search_console.schemas import DateRange
from app.domains.search_console.service import SearchConsoleService
from app.integrations.google_search_console import (
    GSCReauthRequired,
    GSCUnavailable,
    SiteEntry,
    TokenGrant,
)
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration import test_v3_card_workflow as phase2
from tests.integration import test_v3_plan_lock as lock_tests

pytestmark = pytest.mark.integration

db_engine = phase2.db_engine
session_factory = phase2.session_factory
owner_factory = phase2.owner_factory
pair = phase2.pair

Factory = async_sessionmaker[AsyncSession]
Pair = tuple[dict[str, Any], dict[str, Any]]
SITE = "sc-domain:alpha.test"
REFRESH = "1//refresh-token-never-stored-in-plaintext"
CIPHER = TokenCipher(Fernet.generate_key().decode())
START, END = date(2026, 8, 27), date(2026, 9, 23)


def api_row(
    day: str, query: str, page: str, clicks: int, impressions: int, position: float
) -> dict[str, Any]:
    return {
        "keys": [day, query, page],
        "clicks": clicks,
        "impressions": impressions,
        "ctr": clicks / impressions,
        "position": position,
    }


class FakeGoogle:
    """Test double for GoogleSearchConsoleClient."""

    def __init__(self, pages: list[list[dict[str, Any]]] | None = None) -> None:
        self.pages = pages or [
            [
                api_row("2026-09-01", "landed cost", "https://alpha.test/landed-cost", 3, 120, 7.4),
                api_row("2026-09-02", "landed cost", "https://alpha.test/landed-cost", 1, 90, 8.1),
                api_row("2026-09-02", "", "https://alpha.test/", 0, 15, 22.0),
            ]
        ]
        self.sites = [
            SiteEntry(SITE, "siteOwner"),
            SiteEntry("https://other.test/", "siteUnverifiedUser"),
        ]
        self.fail_refresh: Exception | None = None
        self.fail_on_page: int | None = None
        self.revoked: list[str] = []
        self.queries: list[dict[str, Any]] = []

    def authorization_url(self, state: str) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    async def exchange_code(self, code: str) -> TokenGrant:
        assert code == "good-code"
        return TokenGrant(
            "access",
            REFRESH,
            "openid email https://www.googleapis.com/auth/webmasters.readonly",
            3599,
        )

    async def refresh(self, refresh_token: str) -> TokenGrant:
        assert refresh_token == REFRESH
        if self.fail_refresh:
            raise self.fail_refresh
        return TokenGrant("access", None, "", 3599)

    async def revoke(self, token: str) -> None:
        self.revoked.append(token)

    async def account_email(self, access_token: str) -> str | None:
        return "owner@alpha.test"

    async def list_sites(self, access_token: str) -> list[SiteEntry]:
        return self.sites

    async def query_search_analytics(
        self,
        access_token: str,
        site_url: str,
        *,
        start_date: date,
        end_date: date,
        start_row: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        index = len(self.queries)
        self.queries.append(
            {"site": site_url, "start": start_date, "end": end_date, "row": start_row}
        )
        if self.fail_on_page == index:
            raise GSCUnavailable("Search Console is unavailable (503).")
        return {"rows": self.pages[index]} if index < len(self.pages) else {}


def svc(session: AsyncSession, google: FakeGoogle) -> SearchConsoleService:
    return SearchConsoleService(session, client=google, cipher=CIPHER)  # type: ignore[arg-type]


async def _connect(sf: Factory, t: dict[str, Any], google: FakeGoogle) -> None:
    async with sf() as session:
        start = await svc(session, google).start_connect(
            t["project_id"], actor=t["actor"], request_id="r"
        )
    state = start.authorization_url.split("state=", 1)[1]
    async with sf() as session:
        await svc(session, google).complete_connect(
            "good-code", state, actor=t["actor"], request_id="r"
        )


async def _mapped(sf: Factory, t: dict[str, Any], google: FakeGoogle) -> None:
    await _connect(sf, t, google)
    async with sf() as session:
        await svc(session, google).map_property(
            t["site_id"], SITE, actor=t["actor"], request_id="r"
        )


async def _sync(sf: Factory, t: dict[str, Any], google: FakeGoogle, **kw: Any) -> Any:
    async with sf() as session:
        return await svc(session, google).sync(
            kw.get("website", t["site_id"]),
            DateRange(start_date=START, end_date=END),
            actor=kw.get("actor", t["actor"]),
            request_id="r",
        )


async def _analytics(sf: Factory, t: dict[str, Any], **kw: Any) -> Any:
    async with sf() as session:
        return await svc(session, FakeGoogle()).analytics(
            kw.get("website", t["site_id"]),
            DateRange(start_date=START, end_date=END),
            actor=kw.get("actor", t["actor"]),
            sort=kw.get("sort", "clicks"),
        )


async def _one(factory: Factory, sql: str, **params: Any) -> Any:
    async with factory() as session:
        return (await session.execute(text(sql), params)).first()


# ── Connection ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_oauth_connect_stores_only_an_encrypted_token(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    google = FakeGoogle()
    await _connect(session_factory, alpha, google)

    row = await _one(
        owner_factory,
        "SELECT status, encrypted_refresh_token, google_account_email, "
        "oauth_state_hash FROM gsc_connections WHERE project_id = :p",
        p=alpha["project_id"],
    )
    assert row.status == "connected" and row.google_account_email == "owner@alpha.test"
    assert (
        REFRESH not in row.encrypted_refresh_token
        and CIPHER.decrypt(row.encrypted_refresh_token) == REFRESH
    )
    assert row.oauth_state_hash is None  # a state can be used once
    async with session_factory() as session:
        status = await svc(session, google).get_status(alpha["project_id"], actor=alpha["actor"])
    dumped = json.dumps(status.model_dump(mode="json"))
    assert status.state == "connected" and status.can_manage
    assert REFRESH not in dumped and "encrypted" not in dumped
    audit = await _one(
        owner_factory,
        "SELECT count(*) FROM audit_logs WHERE project_id = :p AND "
        "action = 'gsc.connected' AND metadata::text NOT LIKE :t",
        p=alpha["project_id"],
        t=f"%{REFRESH}%",
    )
    assert audit[0] == 1


@pytest.mark.asyncio
async def test_oauth_state_must_be_valid_unused_own_and_fresh(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    google = FakeGoogle()
    async with session_factory() as session:
        start = await svc(session, google).start_connect(
            alpha["project_id"], actor=alpha["actor"], request_id="r"
        )
    state = start.authorization_url.split("state=", 1)[1]

    for actor, code in ((alpha["actor"], "x" * 20), (bravo["actor"], state)):
        async with session_factory() as session:
            with pytest.raises(DomainError) as raised:
                await svc(session, google).complete_connect(
                    "good-code", code, actor=actor, request_id="r"
                )
        assert (
            raised.value.code == "GSC_OAUTH_STATE_INVALID"
        )  # unknown state; another tenant's state

    async with owner_factory() as session:
        await session.execute(
            text(
                "UPDATE gsc_connections SET oauth_state_expires_at = now() - interval "
                "'1 minute' WHERE project_id = :p"
            ),
            {"p": alpha["project_id"]},
        )
        await session.commit()
    async with session_factory() as session:
        with pytest.raises(DomainError) as expired:
            await svc(session, google).complete_connect(
                "good-code", state, actor=alpha["actor"], request_id="r"
            )
    assert expired.value.code == "GSC_OAUTH_STATE_EXPIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [lock_tests.WRITER_ROLE_ID, lock_tests.VIEWER_ROLE_ID])
async def test_only_project_managers_connect_map_and_sync(
    role: UUID, session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    google = FakeGoogle()
    await _mapped(session_factory, alpha, google)
    await lock_tests._set_role(owner_factory, alpha, role)
    async with session_factory() as session:
        with pytest.raises(PermissionDenied):
            await svc(session, google).start_connect(
                alpha["project_id"], actor=alpha["actor"], request_id="r"
            )
    with pytest.raises(PermissionDenied):
        await _sync(session_factory, alpha, google)
    async with session_factory() as session:  # reading stays allowed (website.read)
        status = await svc(session, google).get_status(alpha["project_id"], actor=alpha["actor"])
    assert status.state == "connected" and not status.can_manage


# ── Properties ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_properties_come_from_google_and_mapping_is_verified(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    google = FakeGoogle()
    await _connect(session_factory, alpha, google)
    async with session_factory() as session:
        listed = await svc(session, google).list_properties(
            alpha["project_id"], actor=alpha["actor"]
        )
    assert [p.site_url for p in listed.items] == [SITE]  # unverified access is hidden

    # Covering the website is not enough: the account must be able to read the property.
    google.sites.append(SiteEntry("https://alpha.test/blog/", "siteOwner"))
    for site, code in (
        ("https://alpha.test/", "GSC_PROPERTY_UNAVAILABLE"),
        ("https://alpha.test/blog/", "GSC_PROPERTY_WEBSITE_MISMATCH"),  # narrower than the site
        ("https://other.test/", "GSC_PROPERTY_WEBSITE_MISMATCH"),
        ("sc-domain:not-in-account.test", "GSC_PROPERTY_WEBSITE_MISMATCH"),
    ):
        async with session_factory() as session:
            with pytest.raises(DomainError) as raised:
                await svc(session, google).map_property(
                    alpha["site_id"], site, actor=alpha["actor"], request_id="r"
                )
        assert raised.value.code == code, site
    async with session_factory() as session:  # another tenant's website
        with pytest.raises(ResourceNotFound):
            await svc(session, google).map_property(
                alpha["site_id"], SITE, actor=bravo["actor"], request_id="r"
            )
    async with session_factory() as session:
        mapped = await svc(session, google).map_property(
            alpha["site_id"], SITE, actor=alpha["actor"], request_id="r"
        )
    assert mapped.site_url == SITE and mapped.permission_level == "siteOwner"


# ── Sync ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_pages_through_stores_and_is_idempotent(
    session_factory: Factory, owner_factory: Factory, pair: Pair, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha, _ = pair
    monkeypatch.setattr(gsc_service, "MAX_ROW_LIMIT", 2)  # force pagination
    google = FakeGoogle()
    google.pages = [google.pages[0][:2], [*google.pages[0][2:], {"keys": ["bad"]}]]
    await _mapped(session_factory, alpha, google)

    run = await _sync(session_factory, alpha, google)

    assert (run.status, run.rows_fetched, run.rows_stored, run.rows_rejected) == (
        "completed",
        4,
        3,
        1,
    )
    # Two full pages, then an empty one ends the paging.
    assert [q["row"] for q in google.queries] == [0, 2, 4]
    assert google.queries[0]["start"] == START and google.queries[0]["end"] == END
    stored = await _one(
        owner_factory,
        "SELECT count(*), sum(clicks), sum(impressions) FROM "
        "gsc_search_analytics WHERE website_id = :w",
        w=alpha["site_id"],
    )
    assert tuple(stored) == (3, 4, 225)

    # Re-sync the same range with changed numbers: updated in place, no duplicates.
    google2 = FakeGoogle()
    google2.pages = [
        [api_row("2026-09-01", "landed cost", "https://alpha.test/landed-cost", 5, 150, 6.0)]
    ]
    await _sync(session_factory, alpha, google2)
    again = await _one(
        owner_factory,
        "SELECT count(*), max(clicks) FILTER (WHERE date = '2026-09-01') "
        "FROM gsc_search_analytics WHERE website_id = :w",
        w=alpha["site_id"],
    )
    assert tuple(again) == (3, 5)
    job = await _one(
        owner_factory,
        "SELECT status, provider, input_data, output_data FROM job_runs "
        "WHERE entity_id = :w AND job_type = 'gsc_sync' ORDER BY created_at LIMIT 1",
        w=alpha["site_id"],
    )
    assert job.status == "completed" and job.provider == "google_search_console"
    assert job.input_data["site_url"] == SITE and job.output_data["rows_rejected"] == 1
    assert job.output_data["rejected_samples"][0]["reason"] == "keys must be [date, query, page]"


@pytest.mark.asyncio
async def test_analytics_are_real_stored_rows_with_weighted_totals(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, bravo = pair
    google = FakeGoogle()
    await _mapped(session_factory, alpha, google)
    await _sync(session_factory, alpha, google)
    result = await _analytics(session_factory, alpha)
    t = result.totals
    assert (t.clicks, t.impressions, t.rows, t.queries, t.pages) == (4, 225, 3, 2, 2)
    assert t.ctr == pytest.approx(4 / 225)
    assert t.position == pytest.approx((7.4 * 120 + 8.1 * 90 + 22.0 * 15) / 225)
    assert result.rows[0].clicks == 3 and result.rows[0].query == "landed cost"
    assert (await _analytics(session_factory, alpha, sort="date")).rows[0].date == date(2026, 9, 2)
    with pytest.raises(ResourceNotFound):
        await _analytics(session_factory, alpha, actor=bravo["actor"])
    with pytest.raises(ResourceNotFound):
        await _sync(session_factory, alpha, google, actor=bravo["actor"])


@pytest.mark.asyncio
async def test_revoked_access_marks_reconnect_and_keeps_data(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    google = FakeGoogle()
    await _mapped(session_factory, alpha, google)
    await _sync(session_factory, alpha, google)
    google.fail_refresh = GSCReauthRequired(
        "Google access was revoked or expired. Reconnect Google."
    )
    with pytest.raises(DomainError) as raised:
        await _sync(session_factory, alpha, google)
    assert raised.value.code == "GSC_REAUTH_REQUIRED"
    row = await _one(
        owner_factory,
        "SELECT status, last_error FROM gsc_connections WHERE project_id = :p",
        p=alpha["project_id"],
    )
    assert row.status == "reauth_required" and "Reconnect" in row.last_error
    assert (await _analytics(session_factory, alpha)).totals.rows == 3
    failed = await _one(
        owner_factory,
        "SELECT count(*) FROM job_runs WHERE entity_id = :w AND "
        "job_type = 'gsc_sync' AND status = 'failed'",
        w=alpha["site_id"],
    )
    assert failed[0] == 1


@pytest.mark.asyncio
async def test_a_failed_sync_changes_no_stored_rows(
    session_factory: Factory, owner_factory: Factory, pair: Pair, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha, _ = pair
    google = FakeGoogle()
    await _mapped(session_factory, alpha, google)
    await _sync(session_factory, alpha, google)
    before = await _one(
        owner_factory,
        "SELECT sum(clicks), max(synced_at) FROM gsc_search_analytics WHERE website_id = :w",
        w=alpha["site_id"],
    )

    monkeypatch.setattr(gsc_service, "MAX_ROW_LIMIT", 1)
    failing = FakeGoogle()
    failing.pages = [
        [api_row("2026-09-01", "landed cost", "https://alpha.test/landed-cost", 9, 99, 2.0)]
    ]
    failing.fail_on_page = 1  # Google fails on the second page
    with pytest.raises(DomainError) as raised:
        await _sync(session_factory, alpha, failing)
    assert raised.value.code == "GSC_UNAVAILABLE"

    async def broken(*_: Any, **__: Any) -> int:
        raise RuntimeError("database down")

    monkeypatch.setattr(SearchConsoleService, "_upsert", broken)
    with pytest.raises(DomainError) as stored:
        await _sync(session_factory, alpha, FakeGoogle())
    assert stored.value.code == "GSC_SYNC_STORE_FAILED"
    after = await _one(
        owner_factory,
        "SELECT sum(clicks), max(synced_at) FROM gsc_search_analytics WHERE website_id = :w",
        w=alpha["site_id"],
    )
    assert tuple(after) == tuple(before)


@pytest.mark.asyncio
async def test_disconnect_removes_the_token_and_keeps_synced_data(
    session_factory: Factory, owner_factory: Factory, pair: Pair
) -> None:
    alpha, _ = pair
    google = FakeGoogle()
    await _mapped(session_factory, alpha, google)
    await _sync(session_factory, alpha, google)
    async with session_factory() as session:
        await svc(session, google).disconnect(
            alpha["project_id"], actor=alpha["actor"], request_id="r"
        )
    assert google.revoked == [REFRESH]
    row = await _one(
        owner_factory,
        "SELECT status, encrypted_refresh_token FROM gsc_connections WHERE project_id = :p",
        p=alpha["project_id"],
    )
    assert (row.status, row.encrypted_refresh_token) == ("disconnected", None)
    assert (await _analytics(session_factory, alpha)).totals.rows == 3
    with pytest.raises(DomainError) as raised:
        await _sync(session_factory, alpha, google)
    assert raised.value.code == "GSC_NOT_CONNECTED"
