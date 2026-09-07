"""Verification service for validating write mutations and ensuring document integrity."""

from uuid import UUID

from app.domains.content.editor_models import AIEditProposal, ContentDocument
from app.domains.orchestrator.exceptions import VerificationFailedError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class VerificationService:
    async def verify_patch_applied(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        proposal: AIEditProposal,
        expected_version: int,
    ) -> bool:
        """Verifies that an approved proposal was correctly and consistently
        applied to the document.
        """
        stmt = select(ContentDocument).where(ContentDocument.id == document_id)
        res = await session.execute(stmt)
        document = res.scalars().first()

        if not document:
            raise VerificationFailedError(
                tool_name=proposal.operation_type,
                reason=f"Document {document_id} disappeared during verification.",
            )

        # 1. Verify Version Bump
        if document.current_version < expected_version:
            raise VerificationFailedError(
                tool_name=proposal.operation_type,
                reason=(
                    f"Document version did not advance to expected {expected_version} "
                    f"(currently {document.current_version})."
                ),
            )

        blocks = document.content_blocks or []
        block_map = {b.get("id"): b for b in blocks if b.get("id")}

        # 2. Verify Block-Level Content
        target_ids = proposal.target_block_ids or []
        for tid in target_ids:
            if proposal.operation_type == "delete_block":
                if tid in block_map:
                    raise VerificationFailedError(
                        tool_name=proposal.operation_type,
                        reason=f"Target block '{tid}' was not deleted.",
                    )
            elif proposal.operation_type == "insert_link":
                target = block_map.get(tid)
                if not target:
                    raise VerificationFailedError(
                        tool_name=proposal.operation_type,
                        reason=f"Block '{tid}' with inserted link was not found.",
                    )
                data = target.get("data") or {}
                if not data.get("link_url"):
                    raise VerificationFailedError(
                        tool_name=proposal.operation_type,
                        reason=f"Block '{tid}' does not contain expected link_url.",
                    )
            elif proposal.operation_type in (
                "replace_block",
                "rewrite_section",
                "expand_section",
                "shorten_section",
            ):
                target = block_map.get(tid)
                if not target:
                    raise VerificationFailedError(
                        tool_name=proposal.operation_type,
                        reason=f"Modified block '{tid}' does not exist in document.",
                    )

        return True
