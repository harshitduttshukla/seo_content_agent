"""Document Patch Engine for validating, previewing, and atomically applying AI proposals."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import BadRequestError, ConflictError, ResourceNotFound
from app.db.session import set_actor_context
from app.domains.audit.repository import AuditWriter
from app.domains.content.document_schemas import (
    AIOperation,
    ContentBlock,
    ContentDocumentDetail,
    OperationType,
)
from app.domains.content.editor_models import (
    AIEditProposal,
    ContentDocument,
    ContentDocumentVersion,
    DocumentChangeType,
    ProposalStatus,
)
from app.domains.projects.service import ProjectService
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class DocumentPatchService:
    def __init__(self) -> None:
        self._audit = AuditWriter()
        self._projects = ProjectService()

    def validate_operations(
        self,
        current_blocks: list[dict[str, object]],
        operations: list[AIOperation],
    ) -> None:
        """Strictly validates proposed operations against active document blocks."""
        existing_ids = {b.get("id") for b in current_blocks if b.get("id")}

        for op in operations:
            if op.operation in (
                OperationType.REPLACE_BLOCK,
                OperationType.DELETE_BLOCK,
                OperationType.INSERT_LINK,
            ):
                target_id = op.block_id or op.target_block_id
                if not target_id:
                    raise BadRequestError(f"Operation {op.operation} missing required block_id")
                if target_id not in existing_ids:
                    raise BadRequestError(
                        f"Target block '{target_id}' does not exist in the document."
                    )

            elif op.operation == OperationType.INSERT_BLOCK:
                if op.target_block_id and op.target_block_id not in existing_ids:
                    raise BadRequestError(
                        f"Target anchor block '{op.target_block_id}' does not exist for insertion."
                    )
                if not op.block and not op.new_content:
                    raise BadRequestError("Insert operation must provide block content.")

    def apply_operations_in_memory(
        self,
        current_blocks: list[dict[str, object]],
        operations: list[AIOperation],
    ) -> list[dict[str, object]]:
        """Applies operations to a block list, returning the modified list."""
        self.validate_operations(current_blocks, operations)

        # Deep copy to ensure mutation safety
        blocks: list[dict[str, object]] = [dict(b) for b in current_blocks]

        for op in operations:
            if op.operation == OperationType.REPLACE_BLOCK:
                target_id = op.block_id or op.target_block_id
                for b in blocks:
                    if b.get("id") == target_id:
                        if op.new_content is not None:
                            b["text"] = op.new_content
                        if op.block:
                            b.update(op.block.model_dump())
                        break

            elif op.operation == OperationType.INSERT_BLOCK:
                if op.block:
                    new_b = op.block.model_dump()
                else:
                    new_id = f"b_{len(blocks) + 1:03d}"
                    new_b = ContentBlock(id=new_id, text=op.new_content or "").model_dump()

                if op.target_block_id:
                    target_idx = next(
                        (i for i, b in enumerate(blocks) if b.get("id") == op.target_block_id),
                        len(blocks),
                    )
                    insert_idx = target_idx + 1 if op.position == "after" else target_idx
                    blocks.insert(insert_idx, new_b)
                else:
                    blocks.append(new_b)

            elif op.operation == OperationType.DELETE_BLOCK:
                target_id = op.block_id or op.target_block_id
                blocks = [b for b in blocks if b.get("id") != target_id]

            elif op.operation == OperationType.INSERT_LINK:
                target_id = op.block_id or op.target_block_id
                for b in blocks:
                    if b.get("id") == target_id:
                        data = dict(b.get("data") or {})
                        data["link_url"] = op.url or ""
                        data["link_anchor"] = op.anchor_text or ""
                        b["data"] = data
                        break

            elif op.operation == OperationType.UPDATE_TITLE:
                for b in blocks:
                    if b.get("type") == "DOCUMENT_TITLE" or b.get("level") == 1:
                        b["text"] = op.new_content or b.get("text", "")
                        break

        return blocks

    async def apply_proposal(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        proposal_id: UUID,
    ) -> ContentDocumentDetail:
        """Atomically validates, applies patch, bumps version, and records audit history."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            # 1. Fetch proposal
            prop_stmt = select(AIEditProposal).where(AIEditProposal.id == proposal_id)
            prop_res = await session.execute(prop_stmt)
            proposal = prop_res.scalars().first()
            if not proposal:
                raise ResourceNotFound(f"Proposal {proposal_id} not found")

            # 2. Check idempotency
            if proposal.status == ProposalStatus.APPLIED:
                doc_stmt = select(ContentDocument).where(ContentDocument.id == proposal.document_id)
                doc_res = await session.execute(doc_stmt)
                document = doc_res.scalars().first()
                if document:
                    return ContentDocumentDetail.model_validate(document)
                raise ConflictError("This AI proposal has already been applied.")
            if (
                proposal.status != ProposalStatus.PROPOSED
                and proposal.status != ProposalStatus.APPROVED
            ):
                raise ConflictError(f"Cannot apply proposal in status '{proposal.status}'")

            # 3. Fetch target document
            doc_stmt = select(ContentDocument).where(ContentDocument.id == proposal.document_id)
            doc_res = await session.execute(doc_stmt)
            document = doc_res.scalars().first()
            if not document:
                raise ResourceNotFound(f"Document {proposal.document_id} not found")

            # 4. Check project write permission
            await self._projects.get_model(
                session,
                actor=actor,
                project_id=document.project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            # 5. Parse operations from proposal
            ops_data = proposal.proposed_content
            operations: list[AIOperation] = []
            if isinstance(ops_data, dict) and "operations" in ops_data:
                operations = [AIOperation.model_validate(o) for o in ops_data["operations"]]
            elif isinstance(ops_data, list):
                operations = [AIOperation.model_validate(o) for o in ops_data]
            else:
                target_block = proposal.target_block_ids[0] if proposal.target_block_ids else None
                new_text = str(
                    proposal.proposed_content.get("text", "")
                    if isinstance(proposal.proposed_content, dict)
                    else ""
                )
                operations = [
                    AIOperation(
                        operation=OperationType(proposal.operation_type),
                        block_id=target_block,
                        new_content=new_text,
                        reason=proposal.reason,
                    )
                ]

            # 6. Apply patch in memory
            updated_blocks = self.apply_operations_in_memory(
                document.content_blocks or [], operations
            )

            # 7. Compute plain text and word count
            plain_text = " ".join(str(b.get("text", "")) for b in updated_blocks if b.get("text"))
            word_count = len(plain_text.split()) if plain_text else 0

            # 8. Bump version & lock_version
            document.current_version += 1
            document.lock_version += 1
            document.content_blocks = updated_blocks
            document.plain_text = plain_text
            document.word_count = word_count
            document.updated_by_id = actor.user_id
            document.updated_at = datetime.now(UTC)

            # 9. Create ContentDocumentVersion
            version_record = ContentDocumentVersion(
                organization_id=document.organization_id,
                project_id=document.project_id,
                document_id=document.id,
                version=document.current_version,
                content_blocks=updated_blocks,
                plain_text=plain_text,
                word_count=word_count,
                change_type=DocumentChangeType.AI_PATCH,
                change_summary=proposal.reason or f"Applied AI proposal {proposal.operation_type}",
                created_by_id=actor.user_id,
                created_at=datetime.now(UTC),
            )
            session.add(version_record)

            # 10. Mark proposal as APPLIED
            proposal.status = ProposalStatus.APPLIED
            proposal.reviewed_by_id = actor.user_id
            proposal.reviewed_at = datetime.now(UTC)
            proposal.applied_at = datetime.now(UTC)
            proposal.applied_version = document.current_version

            await session.flush()

            # 11. Audit Logging
            await self._audit.log_event(
                session=session,
                organization_id=document.organization_id,
                project_id=document.project_id,
                user_id=actor.user_id,
                action="ai_proposal.applied",
                resource_type="ai_edit_proposal",
                resource_id=proposal.id,
                metadata={
                    "document_id": str(document.id),
                    "version_created": document.current_version,
                    "operation_type": proposal.operation_type,
                },
            )

            return ContentDocumentDetail.model_validate(document)

    async def reject_proposal(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        proposal_id: UUID,
    ) -> AIEditProposal:
        """Marks a proposed patch as rejected."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            prop_stmt = select(AIEditProposal).where(AIEditProposal.id == proposal_id)
            prop_res = await session.execute(prop_stmt)
            proposal = prop_res.scalars().first()
            if not proposal:
                raise ResourceNotFound(f"Proposal {proposal_id} not found")

            doc_stmt = select(ContentDocument).where(ContentDocument.id == proposal.document_id)
            doc_res = await session.execute(doc_stmt)
            document = doc_res.scalars().first()
            if not document:
                raise ResourceNotFound(f"Document {proposal.document_id} not found")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=document.project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            proposal.status = ProposalStatus.REJECTED
            proposal.reviewed_by_id = actor.user_id
            proposal.reviewed_at = datetime.now(UTC)

            await session.flush()

            await self._audit.log_event(
                session=session,
                organization_id=document.organization_id,
                project_id=document.project_id,
                user_id=actor.user_id,
                action="ai_proposal.rejected",
                resource_type="ai_edit_proposal",
                resource_id=proposal.id,
                metadata={"document_id": str(document.id)},
            )

            return proposal
