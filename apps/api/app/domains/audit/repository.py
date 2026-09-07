"""Append-only audit/outbox helpers and atomic idempotency claims."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.errors import ConflictError
from app.domains.audit.models import AuditLog, IdempotencyRecord, OutboxEvent
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession


class AuditWriter:
    def add(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        request_id: str,
        organization_id: UUID | None = None,
        project_id: UUID | None = None,
        outcome: str = "success",
        metadata: dict[str, object] | None = None,
    ) -> None:
        session.add(
            AuditLog(
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                project_id=project_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                request_id=request_id,
                metadata_json=metadata or {},
                occurred_at=datetime.now(UTC),
            )
        )

    async def log_event(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID | None = None,
        user_id: UUID | None = None,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        organization_id: UUID | None = None,
        project_id: UUID | None = None,
        outcome: str = "success",
        metadata: dict[str, object] | None = None,
        request_id: str = "system",
    ) -> None:
        effective_actor_id = actor_user_id or user_id or UUID(int=0)
        self.add(
            session,
            actor_user_id=effective_actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            organization_id=organization_id,
            project_id=project_id,
            outcome=outcome,
            metadata=metadata,
        )


class OutboxWriter:
    def add(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        project_id: UUID | None,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        session.add(
            OutboxEvent(
                organization_id=organization_id,
                project_id=project_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload or {},
                occurred_at=datetime.now(UTC),
            )
        )


def request_fingerprint(payload: dict[str, object]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(body).hexdigest()


class IdempotencyRepository:
    async def claim(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID | None,
        actor_user_id: UUID,
        route: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[IdempotencyRecord, bool]:
        now = datetime.now(UTC)
        record_id = await session.scalar(
            insert(IdempotencyRecord)
            .values(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                route=route,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                created_at=now,
                expires_at=now + timedelta(hours=24),
            )
            .on_conflict_do_nothing(index_elements=["actor_user_id", "route", "idempotency_key"])
            .returning(IdempotencyRecord.id)
        )
        if record_id is not None:
            record = await session.get(IdempotencyRecord, record_id)
            if record is None:
                raise RuntimeError("Idempotency claim disappeared")
            return record, True

        record = await session.scalar(
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.actor_user_id == actor_user_id,
                IdempotencyRecord.route == route,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )
        if record is None:
            raise RuntimeError("Idempotency record could not be resolved")
        if record.request_hash != request_hash:
            raise ConflictError(
                "IDEMPOTENCY_KEY_REUSED",
                "The Idempotency-Key was already used with a different request.",
            )
        if record.response_data is None:
            raise ConflictError(
                "REQUEST_IN_PROGRESS", "A request with this Idempotency-Key is still in progress."
            )
        return record, False

    def complete(
        self, record: IdempotencyRecord, response_data: dict[str, object], status_code: int
    ) -> None:
        record.response_data = response_data
        record.status_code = status_code
