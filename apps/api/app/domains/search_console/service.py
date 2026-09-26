"""Read-only Google Search Console integration (Phase 6A).

connect → Google consent → callback (state checked, code exchanged, refresh token
encrypted) → list properties → map one to a website → sync (refresh access token,
page through searchAnalytics.query, validate, normalize, upsert) → read analytics.

Google calls never run inside a database transaction. A sync's rows are upserted in
one transaction, so a failure leaves earlier data as it was. Every sync writes a
``gsc_sync`` JobRun (website, property, range, row counts, outcome) and an audit
event; neither ever contains a credential.
"""

import hashlib
import logging
import secrets
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from app.config.settings import get_settings
from app.core.errors import ConflictError, DomainError, PermissionDenied, ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.audit.repository import AuditWriter
from app.domains.job_runs.models import JobRun, JobRunStatus
from app.domains.projects.models import Project
from app.domains.projects.service import ProjectService
from app.domains.search_console.coverage import property_covers_website
from app.domains.search_console.models import (
    GscConnection,
    GscConnectionStatus,
    GscProperty,
    GscSearchAnalyticsRow,
)
from app.domains.search_console.normalize import (
    AnalyticsRow,
    RejectedRow,
    TokenCipher,
    normalize_response,
)
from app.domains.search_console.schemas import (
    MAX_RANGE_DAYS,
    AnalyticsResponse,
    AnalyticsRowOut,
    AnalyticsSort,
    AnalyticsTotals,
    AvailableProperty,
    AvailablePropertyList,
    ConnectStartResponse,
    DateRange,
    MappedProperty,
    OAuthCallbackResponse,
    SearchConsoleStatus,
    SyncRun,
    WebsiteSearchConsole,
)
from app.domains.websites.models import Website
from app.domains.websites.service import WebsiteService
from app.integrations.google_search_console import (
    MAX_ROW_LIMIT,
    GoogleSearchConsoleClient,
    GSCError,
    GSCReauthRequired,
)
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy import and_, delete, desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

logger = logging.getLogger(__name__)

SYNC_JOB_TYPE = "gsc_sync"
SYNC_VERSION = "gsc.search_analytics.v1"
STATE_TTL = timedelta(minutes=10)
MAX_SYNC_ROWS = 250_000  # hard cap per sync; a truncated sync is recorded as such
UPSERT_CHUNK = 1_000
DATA_LAG_DAYS = 2


def _hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def resolve_range(requested: DateRange, today: date | None = None) -> tuple[date, date]:
    """Validate a date range against Search Console's limits (inclusive dates)."""
    today = today or datetime.now(UTC).date()
    if requested.start_date is None or requested.end_date is None:
        end = today - timedelta(days=DATA_LAG_DAYS)
        return end - timedelta(days=27), end
    start, end = requested.start_date, requested.end_date
    if start > end:
        raise DomainError("INVALID_DATE_RANGE", "start_date must be on or before end_date.", 422)
    if end > today:
        raise DomainError("INVALID_DATE_RANGE", "end_date cannot be in the future.", 422)
    if (today - start).days > MAX_RANGE_DAYS:
        raise DomainError(
            "INVALID_DATE_RANGE", "Search Console keeps about 16 months of data.", 422
        )
    return start, end


class SearchConsoleService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        client: GoogleSearchConsoleClient | None = None,
        cipher: TokenCipher | None = None,
    ) -> None:
        self._session = session
        self._projects = ProjectService()
        self._websites = WebsiteService()
        self._audit = AuditWriter()
        self._client_override = client
        self._cipher_override = cipher

    # ── configuration ────────────────────────────────────────────

    @staticmethod
    def configured() -> bool:
        s = get_settings()
        return bool(
            s.GSC_OAUTH_CLIENT_ID and s.GSC_OAUTH_CLIENT_SECRET and s.GSC_TOKEN_ENCRYPTION_KEY
        )

    def _client(self) -> GoogleSearchConsoleClient:
        if self._client_override is not None:
            return self._client_override
        if not self.configured():
            raise DomainError(
                "GSC_NOT_CONFIGURED",
                "Google Search Console is not configured on the server.",
                503,
            )
        s = get_settings()
        return GoogleSearchConsoleClient(
            client_id=s.GSC_OAUTH_CLIENT_ID,
            client_secret=s.GSC_OAUTH_CLIENT_SECRET,
            redirect_uri=s.GSC_OAUTH_REDIRECT_URI,
        )

    def _cipher(self) -> TokenCipher:
        if self._cipher_override is not None:
            return self._cipher_override
        key = get_settings().GSC_TOKEN_ENCRYPTION_KEY
        if not key:
            raise DomainError(
                "GSC_NOT_CONFIGURED", "Google Search Console is not configured on the server.", 503
            )
        return TokenCipher(key)

    # ── scoping helpers ──────────────────────────────────────────

    async def _project(
        self, project_id: UUID, actor: AuthenticatedUser, permission: PermissionCode
    ) -> Project:
        return await self._projects.get_model(
            self._session, actor=actor, project_id=project_id, permission=permission
        )

    async def _connection(
        self, organization_id: UUID, project_id: UUID, *, lock: bool = False
    ) -> GscConnection | None:
        stmt = select(GscConnection).where(
            GscConnection.organization_id == organization_id,
            GscConnection.project_id == project_id,
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _property(self, website: Website) -> GscProperty | None:
        return (
            await self._session.execute(
                select(GscProperty).where(
                    GscProperty.organization_id == website.organization_id,
                    GscProperty.project_id == website.project_id,
                    GscProperty.website_id == website.id,
                )
            )
        ).scalar_one_or_none()

    async def _may(
        self, project_id: UUID, actor: AuthenticatedUser, permission: PermissionCode
    ) -> bool:
        try:
            await self._project(project_id, actor, permission)
        except PermissionDenied:
            return False
        return True

    def _audit_event(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        project_id: UUID,
        action: str,
        resource_id: UUID,
        request_id: str,
        metadata: dict[str, object],
    ) -> None:
        self._audit.add(
            self._session,
            actor_user_id=actor.user_id,
            organization_id=organization_id,
            project_id=project_id,
            action=action,
            resource_type="search_console",
            resource_id=resource_id,
            request_id=request_id,
            metadata=metadata,
        )

    # ── status ───────────────────────────────────────────────────

    async def get_status(
        self, project_id: UUID, *, actor: AuthenticatedUser
    ) -> SearchConsoleStatus:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._project(project_id, actor, PermissionCode.WEBSITE_READ)
            connection = await self._connection(project.organization_id, project.id)
            websites = list(
                (
                    await self._session.execute(
                        select(Website)
                        .where(
                            Website.organization_id == project.organization_id,
                            Website.project_id == project.id,
                            Website.archived_at.is_(None),
                        )
                        .order_by(Website.name)
                    )
                ).scalars()
            )
            properties = {
                p.website_id: p
                for p in (
                    await self._session.execute(
                        select(GscProperty).where(
                            GscProperty.organization_id == project.organization_id,
                            GscProperty.project_id == project.id,
                        )
                    )
                ).scalars()
            }
            counts = dict(
                (
                    await self._session.execute(
                        select(GscSearchAnalyticsRow.property_id, func.count())
                        .where(
                            GscSearchAnalyticsRow.organization_id == project.organization_id,
                            GscSearchAnalyticsRow.project_id == project.id,
                        )
                        .group_by(GscSearchAnalyticsRow.property_id)
                    )
                )
                .tuples()
                .all()
            )
            last_runs = await self._last_syncs(project.organization_id, project.id)
            can_manage = await self._may(project.id, actor, PermissionCode.PROJECT_UPDATE)
            return SearchConsoleStatus(
                project_id=project.id,
                configured=self.configured(),
                state=connection.status if connection else "not_connected",
                google_account_email=connection.google_account_email if connection else None,
                connected_at=connection.connected_at if connection else None,
                last_error=connection.last_error if connection else None,
                can_manage=can_manage,
                websites=[
                    WebsiteSearchConsole(
                        website_id=w.id,
                        website_name=w.name,
                        base_url=w.base_url,
                        property=(
                            MappedProperty(
                                site_url=p.site_url,
                                permission_level=p.permission_level,
                                last_synced_at=p.last_synced_at,
                                last_sync_start=p.last_sync_start,
                                last_sync_end=p.last_sync_end,
                                stored_rows=int(counts.get(p.id, 0)),
                            )
                            if (p := properties.get(w.id))
                            else None
                        ),
                        last_sync=last_runs.get(w.id),
                    )
                    for w in websites
                ],
            )

    async def _last_syncs(self, organization_id: UUID, project_id: UUID) -> dict[UUID, SyncRun]:
        latest = (
            select(JobRun.entity_id, func.max(JobRun.created_at).label("at"))
            .where(
                JobRun.organization_id == organization_id,
                JobRun.project_id == project_id,
                JobRun.job_type == SYNC_JOB_TYPE,
            )
            .group_by(JobRun.entity_id)
            .subquery()
        )
        runs = (
            await self._session.execute(
                select(JobRun)
                .join(
                    latest,
                    and_(JobRun.entity_id == latest.c.entity_id, JobRun.created_at == latest.c.at),
                )
                .where(JobRun.job_type == SYNC_JOB_TYPE, JobRun.project_id == project_id)
            )
        ).scalars()
        return {r.entity_id: _sync_run(r) for r in runs if r.entity_id is not None}

    # ── OAuth ────────────────────────────────────────────────────

    async def start_connect(
        self, project_id: UUID, *, actor: AuthenticatedUser, request_id: str
    ) -> ConnectStartResponse:
        client = self._client()
        self._cipher()  # fail early when the key is missing
        state = secrets.token_urlsafe(32)
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._project(project_id, actor, PermissionCode.PROJECT_UPDATE)
            connection = await self._connection(project.organization_id, project.id, lock=True)
            if connection is None:
                connection = GscConnection(
                    id=uuid4(),
                    organization_id=project.organization_id,
                    project_id=project.id,
                    status=GscConnectionStatus.PENDING,
                    scopes="",
                )
                self._session.add(connection)
            elif connection.status in (GscConnectionStatus.DISCONNECTED,):
                connection.status = GscConnectionStatus.PENDING
            connection.oauth_state_hash = _hash(state)
            connection.oauth_state_expires_at = datetime.now(UTC) + STATE_TTL
            connection.oauth_started_by = actor.user_id
            await self._session.flush()
            self._audit_event(
                actor,
                project.organization_id,
                project.id,
                "gsc.connect_started",
                connection.id,
                request_id,
                {},
            )
        return ConnectStartResponse(authorization_url=client.authorization_url(state))

    async def complete_connect(
        self, code: str, state: str, *, actor: AuthenticatedUser, request_id: str
    ) -> OAuthCallbackResponse:
        client = self._client()
        cipher = self._cipher()
        state_hash = _hash(state)
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            connection = (
                await self._session.execute(
                    select(GscConnection).where(GscConnection.oauth_state_hash == state_hash)
                )
            ).scalar_one_or_none()
            if connection is None:
                raise DomainError(
                    "GSC_OAUTH_STATE_INVALID", "This Google sign-in link is not valid.", 400
                )
            # RLS already limits the row to projects the user can see; require manage rights too.
            await self._project(connection.project_id, actor, PermissionCode.PROJECT_UPDATE)
            if connection.oauth_started_by != actor.user_id:
                raise DomainError(
                    "GSC_OAUTH_STATE_INVALID",
                    "This Google sign-in was started by another user.",
                    400,
                )
            expires = connection.oauth_state_expires_at
            if expires is None or expires < datetime.now(UTC):
                raise DomainError(
                    "GSC_OAUTH_STATE_EXPIRED", "The Google sign-in expired. Start again.", 400
                )
            connection_id, organization_id, project_id = (
                connection.id,
                connection.organization_id,
                connection.project_id,
            )

        try:
            grant = await client.exchange_code(code)
        except GSCError as exc:
            raise DomainError(exc.code, exc.message, exc.status) from exc
        if not grant.refresh_token:
            raise DomainError(
                "GSC_NO_REFRESH_TOKEN",
                "Google did not grant offline access. Start the connection again.",
                400,
            )
        if "webmasters" not in grant.scope:
            raise DomainError(
                "GSC_SCOPE_DENIED",
                "Search Console access was not granted. Start again and allow it.",
                400,
            )
        email = await client.account_email(grant.access_token)

        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            connection = await self._connection(organization_id, project_id, lock=True)
            if (
                connection is None
                or connection.id != connection_id
                or connection.oauth_state_hash != state_hash
            ):
                raise ConflictError(
                    "GSC_OAUTH_STATE_INVALID", "The connection changed; start again."
                )
            connection.encrypted_refresh_token = cipher.encrypt(grant.refresh_token)
            connection.status = GscConnectionStatus.CONNECTED
            connection.scopes = grant.scope
            connection.google_account_email = email
            connection.connected_by = actor.user_id
            connection.connected_at = datetime.now(UTC)
            connection.last_error = None
            connection.oauth_state_hash = None
            connection.oauth_state_expires_at = None
            await self._session.flush()
            self._audit_event(
                actor,
                organization_id,
                project_id,
                "gsc.connected",
                connection.id,
                request_id,
                {"google_account": email or ""},
            )
        return OAuthCallbackResponse(
            project_id=project_id, state="connected", google_account_email=email
        )

    async def disconnect(
        self, project_id: UUID, *, actor: AuthenticatedUser, request_id: str
    ) -> None:
        token: str | None = None
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._project(project_id, actor, PermissionCode.PROJECT_UPDATE)
            connection = await self._connection(project.organization_id, project.id, lock=True)
            if connection is None:
                raise ResourceNotFound("gsc_connection")
            if connection.encrypted_refresh_token:
                try:
                    token = self._cipher().decrypt(connection.encrypted_refresh_token)
                except ValueError:
                    token = None
            connection.encrypted_refresh_token = None
            connection.status = GscConnectionStatus.DISCONNECTED
            connection.oauth_state_hash = None
            connection.last_error = None
            await self._session.flush()
            self._audit_event(
                actor,
                project.organization_id,
                project.id,
                "gsc.disconnected",
                connection.id,
                request_id,
                {},
            )
        if token:
            await self._client().revoke(token)

    # ── access token ─────────────────────────────────────────────

    async def _access_token(
        self,
        connection_id: UUID,
        organization_id: UUID,
        project_id: UUID,
        encrypted: str | None,
        actor: AuthenticatedUser,
    ) -> str:
        if not encrypted:
            raise DomainError("GSC_NOT_CONNECTED", "Connect Google Search Console first.", 409)
        try:
            refresh_token = self._cipher().decrypt(encrypted)
        except ValueError as exc:
            raise DomainError(
                "GSC_REAUTH_REQUIRED",
                "The stored Google credential is unusable. Reconnect Google.",
                409,
            ) from exc
        try:
            return (await self._client().refresh(refresh_token)).access_token
        except GSCReauthRequired as exc:
            await self._mark_reauth(organization_id, project_id, actor, exc.message)
            raise DomainError(exc.code, exc.message, exc.status) from exc
        except GSCError as exc:
            raise DomainError(exc.code, exc.message, exc.status) from exc

    async def _mark_reauth(
        self, organization_id: UUID, project_id: UUID, actor: AuthenticatedUser, message: str
    ) -> None:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            connection = await self._connection(organization_id, project_id, lock=True)
            if connection is not None:
                connection.status = GscConnectionStatus.REAUTH_REQUIRED
                connection.last_error = message

    async def _connected(self, organization_id: UUID, project_id: UUID) -> GscConnection:
        connection = await self._connection(organization_id, project_id)
        if (
            connection is None
            or connection.status in (GscConnectionStatus.PENDING, GscConnectionStatus.DISCONNECTED)
            or not connection.encrypted_refresh_token
        ):
            raise DomainError("GSC_NOT_CONNECTED", "Connect Google Search Console first.", 409)
        if connection.status == GscConnectionStatus.REAUTH_REQUIRED:
            raise DomainError(
                "GSC_REAUTH_REQUIRED",
                "Google access expired or was revoked. Reconnect Google.",
                409,
            )
        return connection

    # ── properties ───────────────────────────────────────────────

    async def list_properties(
        self, project_id: UUID, *, actor: AuthenticatedUser
    ) -> AvailablePropertyList:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            project = await self._project(project_id, actor, PermissionCode.PROJECT_UPDATE)
            connection = await self._connected(project.organization_id, project.id)
            args = (
                connection.id,
                project.organization_id,
                project.id,
                connection.encrypted_refresh_token,
            )
            mapped: dict[str, list[UUID]] = {}
            for prop in (
                await self._session.execute(
                    select(GscProperty).where(
                        GscProperty.organization_id == project.organization_id,
                        GscProperty.project_id == project.id,
                    )
                )
            ).scalars():
                mapped.setdefault(prop.site_url, []).append(prop.website_id)
        access = await self._access_token(*args, actor)
        try:
            sites = await self._client().list_sites(access)
        except GSCError as exc:
            raise DomainError(exc.code, exc.message, exc.status) from exc
        return AvailablePropertyList(
            items=[
                AvailableProperty(
                    site_url=s.site_url,
                    permission_level=s.permission_level,
                    mapped_website_ids=mapped.get(s.site_url, []),
                )
                for s in sorted(sites, key=lambda s: s.site_url)
                if s.permission_level != "siteUnverifiedUser"
            ]
        )

    async def map_property(
        self, website_id: UUID, site_url: str, *, actor: AuthenticatedUser, request_id: str
    ) -> MappedProperty:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            website = await self._websites.get_model(
                self._session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.PROJECT_UPDATE,
            )
            # The property must cover this website's own URL: one Google account can
            # legitimately read several clients' properties.
            if not property_covers_website(site_url, website.base_url):
                raise DomainError(
                    "GSC_PROPERTY_WEBSITE_MISMATCH",
                    f"{site_url} does not cover {website.base_url}. Choose the domain "
                    "property or URL-prefix property for this website.",
                    422,
                )
            connection = await self._connected(website.organization_id, website.project_id)
            args = (
                connection.id,
                website.organization_id,
                website.project_id,
                connection.encrypted_refresh_token,
            )
            organization_id, project_id = website.organization_id, website.project_id
        # Never trust the client's property: it must be one Google says this account can read.
        access = await self._access_token(*args, actor)
        try:
            sites = {s.site_url: s for s in await self._client().list_sites(access)}
        except GSCError as exc:
            raise DomainError(exc.code, exc.message, exc.status) from exc
        site = sites.get(site_url)
        if site is None or site.permission_level == "siteUnverifiedUser":
            raise DomainError(
                "GSC_PROPERTY_UNAVAILABLE",
                "The connected Google account cannot read that Search Console property.",
                403,
            )
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            website = await self._websites.get_model(
                self._session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.PROJECT_UPDATE,
            )
            # Re-checked against Google's own site_url and the website as it is now.
            if not property_covers_website(site.site_url, website.base_url):
                raise DomainError(
                    "GSC_PROPERTY_WEBSITE_MISMATCH",
                    f"{site.site_url} does not cover {website.base_url}.",
                    422,
                )
            prop = await self._property(website)
            if prop is None:
                prop = GscProperty(
                    id=uuid4(),
                    organization_id=organization_id,
                    project_id=project_id,
                    website_id=website.id,
                    connection_id=args[0],
                    site_url=site.site_url,
                )
                self._session.add(prop)
            elif prop.site_url != site.site_url:
                # Rows synced from the previous property belong to it, not to this one.
                await self._session.execute(
                    delete(GscSearchAnalyticsRow).where(
                        GscSearchAnalyticsRow.property_id == prop.id,
                        GscSearchAnalyticsRow.project_id == project_id,
                    )
                )
                prop.site_url = site.site_url
                prop.last_synced_at = prop.last_sync_start = prop.last_sync_end = None
            prop.connection_id = args[0]
            prop.permission_level = site.permission_level
            prop.mapped_by = actor.user_id
            await self._session.flush()
            self._audit_event(
                actor,
                organization_id,
                project_id,
                "gsc.property_mapped",
                website.id,
                request_id,
                {"site_url": site.site_url},
            )
            count = await self._session.scalar(
                select(func.count()).where(GscSearchAnalyticsRow.property_id == prop.id)
            )
            return MappedProperty(
                site_url=prop.site_url,
                permission_level=prop.permission_level,
                last_synced_at=prop.last_synced_at,
                last_sync_start=prop.last_sync_start,
                last_sync_end=prop.last_sync_end,
                stored_rows=int(count or 0),
            )

    # ── sync ─────────────────────────────────────────────────────

    async def sync(
        self, website_id: UUID, requested: DateRange, *, actor: AuthenticatedUser, request_id: str
    ) -> SyncRun:
        start, end = resolve_range(requested)
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            website = await self._websites.get_model(
                self._session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.PROJECT_UPDATE,
            )
            prop = await self._property(website)
            if prop is None:
                raise DomainError(
                    "GSC_PROPERTY_NOT_MAPPED",
                    "Map a Search Console property to this website first.",
                    409,
                )
            connection = await self._connected(website.organization_id, website.project_id)
            organization_id, project_id = website.organization_id, website.project_id
            property_id, site_url = prop.id, prop.site_url
            args = (connection.id, organization_id, project_id, connection.encrypted_refresh_token)

        started = datetime.now(UTC)
        rows: list[AnalyticsRow] = []
        rejected: list[RejectedRow] = []
        fetched = 0
        truncated = False
        error: DomainError | None = None
        try:
            access = await self._access_token(*args, actor)
            start_row = 0
            while True:
                payload = await self._client().query_search_analytics(
                    access, site_url, start_date=start, end_date=end, start_row=start_row
                )
                page_rows = payload.get("rows", [])
                count = len(page_rows) if isinstance(page_rows, list) else 0
                accepted, bad = normalize_response(payload, start, end)
                rows.extend(accepted)
                rejected.extend(bad)
                fetched += count
                if count < MAX_ROW_LIMIT:
                    break
                start_row += count
                if fetched >= MAX_SYNC_ROWS:
                    truncated = True
                    break
        except GSCError as exc:
            if isinstance(exc, GSCReauthRequired):
                await self._mark_reauth(organization_id, project_id, actor, exc.message)
            error = DomainError(exc.code, exc.message, exc.status)
        except DomainError as exc:
            error = exc
        completed = datetime.now(UTC)
        logger.info(
            "gsc sync fetched",
            extra={
                "website_id": str(website_id),
                "site_url": site_url,
                "rows": fetched,
                "rejected": len(rejected),
                "ok": error is None,
            },
        )

        run_id = uuid4()
        stored = 0
        try:
            async with transactional_session(self._session):
                await set_actor_context(self._session, actor.user_id)
                if error is None:
                    stored = await self._upsert(
                        organization_id,
                        project_id,
                        website_id,
                        property_id,
                        rows,
                        run_id,
                        completed,
                    )
                    prop = (
                        await self._session.execute(
                            select(GscProperty)
                            .where(GscProperty.id == property_id)
                            .with_for_update()
                        )
                    ).scalar_one()
                    prop.last_synced_at, prop.last_sync_start, prop.last_sync_end = (
                        completed,
                        start,
                        end,
                    )
                run = self._job(
                    run_id,
                    organization_id,
                    project_id,
                    website_id,
                    actor,
                    site_url,
                    start,
                    end,
                    fetched,
                    stored,
                    rejected,
                    truncated,
                    error,
                    started,
                    completed,
                )
                self._session.add(run)
                await self._session.flush()
                self._audit_event(
                    actor,
                    organization_id,
                    project_id,
                    "gsc.synced",
                    website_id,
                    request_id,
                    {
                        "site_url": site_url,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "rows": stored,
                        "ok": error is None,
                    },
                )
        except DomainError:
            raise
        except Exception as exc:  # database failure: nothing from this sync was kept
            logger.exception("gsc sync persistence failed", extra={"website_id": str(website_id)})
            raise DomainError(
                "GSC_SYNC_STORE_FAILED", "Synced data could not be saved; nothing was changed.", 500
            ) from exc
        if error is not None:
            raise error
        return _sync_run(run)

    async def _upsert(
        self,
        organization_id: UUID,
        project_id: UUID,
        website_id: UUID,
        property_id: UUID,
        rows: list[AnalyticsRow],
        run_id: UUID,
        synced_at: datetime,
    ) -> int:
        for i in range(0, len(rows), UPSERT_CHUNK):
            chunk = rows[i : i + UPSERT_CHUNK]
            stmt = insert(GscSearchAnalyticsRow).values(
                [
                    {
                        "id": uuid4(),
                        "organization_id": organization_id,
                        "project_id": project_id,
                        "website_id": website_id,
                        "property_id": property_id,
                        "date": r.date,
                        "query": r.query,
                        "page": r.page,
                        "clicks": r.clicks,
                        "impressions": r.impressions,
                        "ctr": r.ctr,
                        "position": r.position,
                        "synced_at": synced_at,
                        "job_run_id": run_id,
                    }
                    for r in chunk
                ]
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_gsc_search_analytics_row",
                set_={
                    "clicks": stmt.excluded.clicks,
                    "impressions": stmt.excluded.impressions,
                    "ctr": stmt.excluded.ctr,
                    "position": stmt.excluded.position,
                    "synced_at": stmt.excluded.synced_at,
                    "job_run_id": stmt.excluded.job_run_id,
                },
            )
            await self._session.execute(stmt)
        return len(rows)

    @staticmethod
    def _job(
        run_id: UUID,
        organization_id: UUID,
        project_id: UUID,
        website_id: UUID,
        actor: AuthenticatedUser,
        site_url: str,
        start: date,
        end: date,
        fetched: int,
        stored: int,
        rejected: list[RejectedRow],
        truncated: bool,
        error: DomainError | None,
        started: datetime,
        completed: datetime,
    ) -> JobRun:
        return JobRun(
            id=run_id,
            organization_id=organization_id,
            project_id=project_id,
            job_type=SYNC_JOB_TYPE,
            prompt_version=SYNC_VERSION,
            model="n/a",
            provider="google_search_console",
            status=JobRunStatus.COMPLETED if error is None else JobRunStatus.FAILED,
            triggered_by=str(actor.user_id),
            entity_type="website",
            entity_id=website_id,
            input_data={
                "site_url": site_url,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "dimensions": ["date", "query", "page"],
                "type": "web",
            },
            output_data={
                "rows_fetched": fetched,
                "rows_stored": stored,
                "rows_rejected": len(rejected),
                "rejected_samples": [{"reason": r.reason, "raw": r.raw} for r in rejected[:20]],
                "truncated": truncated,
            },
            error=f"{error.code}: {error.message}" if error else None,
            started_at=started,
            completed_at=completed,
            created_at=completed,
            updated_at=completed,
        )

    # ── read ─────────────────────────────────────────────────────

    async def analytics(
        self,
        website_id: UUID,
        requested: DateRange,
        *,
        actor: AuthenticatedUser,
        sort: AnalyticsSort = "clicks",
        limit: int = 50,
        offset: int = 0,
    ) -> AnalyticsResponse:
        async with transactional_session(self._session):
            await set_actor_context(self._session, actor.user_id)
            website = await self._websites.get_model(
                self._session,
                actor=actor,
                website_id=website_id,
                permission=PermissionCode.WEBSITE_READ,
            )
            prop = await self._property(website)
            if prop is None:
                raise DomainError(
                    "GSC_PROPERTY_NOT_MAPPED",
                    "Map a Search Console property to this website first.",
                    409,
                )
            if requested.start_date is None and prop.last_sync_start and prop.last_sync_end:
                start, end = prop.last_sync_start, prop.last_sync_end
            else:
                start, end = resolve_range(requested)
            T = GscSearchAnalyticsRow
            scope = (
                T.organization_id == website.organization_id,
                T.project_id == website.project_id,
                T.property_id == prop.id,
                T.date >= start,
                T.date <= end,
            )
            totals = (
                await self._session.execute(
                    select(
                        func.coalesce(func.sum(T.clicks), 0),
                        func.coalesce(func.sum(T.impressions), 0),
                        func.sum(T.position * T.impressions)
                        / func.nullif(func.sum(T.impressions), 0),
                        func.count(),
                        func.count(func.distinct(T.query)),
                        func.count(func.distinct(T.page)),
                    ).where(*scope)
                )
            ).one()
            order: list[ColumnElement[object]] = {
                "clicks": [desc(T.clicks), desc(T.impressions)],
                "impressions": [desc(T.impressions)],
                "ctr": [desc(T.ctr), desc(T.impressions)],
                "position": [T.position],
                "date": [desc(T.date), desc(T.clicks)],
            }[sort]  # type: ignore[assignment]
            result = (
                (
                    await self._session.execute(
                        select(T)
                        .where(*scope)
                        .order_by(*order, T.id)
                        .offset(offset)
                        .limit(limit + 1)
                    )
                )
                .scalars()
                .all()
            )
            clicks, impressions = int(totals[0]), int(totals[1])
            return AnalyticsResponse(
                website_id=website.id,
                site_url=prop.site_url,
                start_date=start,
                end_date=end,
                totals=AnalyticsTotals(
                    clicks=clicks,
                    impressions=impressions,
                    ctr=(clicks / impressions) if impressions else 0.0,
                    position=float(totals[2]) if totals[2] is not None else None,
                    rows=int(totals[3]),
                    queries=int(totals[4]),
                    pages=int(totals[5]),
                ),
                rows=[
                    AnalyticsRowOut(
                        date=r.date,
                        query=r.query,
                        page=r.page,
                        clicks=r.clicks,
                        impressions=r.impressions,
                        ctr=r.ctr,
                        position=r.position,
                    )
                    for r in result[:limit]
                ],
                next_offset=offset + limit if len(result) > limit else None,
            )


def _sync_run(run: JobRun) -> SyncRun:
    data, out = run.input_data or {}, run.output_data or {}

    def _date(value: object) -> date | None:
        return date.fromisoformat(value) if isinstance(value, str) else None

    def _int(value: object) -> int:
        return int(value) if isinstance(value, int) else 0

    return SyncRun(
        job_run_id=run.id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        start_date=_date(data.get("start_date")),
        end_date=_date(data.get("end_date")),
        rows_fetched=_int(out.get("rows_fetched")),
        rows_stored=_int(out.get("rows_stored")),
        rows_rejected=_int(out.get("rows_rejected")),
        truncated=out.get("truncated") is True,
        error=run.error,
    )
