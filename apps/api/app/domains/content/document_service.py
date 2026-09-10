"""Service layer for Structured Content Documents, Autosave, Versioning, Chat, and Proposals."""

from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import ConflictError, ResourceNotFound
from app.db.session import set_actor_context
from app.domains.ai.context_builder import ContextBuilderService
from app.domains.ai.service import ContentAIService
from app.domains.audit.repository import AuditWriter
from app.domains.content.document_schemas import (
    AIProposalDetail,
    BlockType,
    ChatMessageDetail,
    ChatMessageRequest,
    ChatSessionDetail,
    ContentBlock,
    ContentDocumentDetail,
    ContentDocumentUpdate,
    ContentDocumentVersionDetail,
    ContentDocumentVersionList,
    OperationType,
)
from app.domains.content.editor_models import (
    AIEditProposal,
    ContentBrief,
    ContentChatMessage,
    ContentChatSession,
    ContentDocument,
    ContentDocumentVersion,
    DocumentChangeType,
    DocumentStatus,
    ProposalStatus,
)
from app.domains.content.models import PlannedContentPage
from app.domains.content.patch_service import DocumentPatchService
from app.domains.projects.service import ProjectService
from app.domains.seo.models import SEOGuide
from app.security.principal import AuthenticatedUser, PermissionCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ContentDocumentService:
    def __init__(self) -> None:
        self._audit = AuditWriter()
        self._projects = ProjectService()
        self._patch_service = DocumentPatchService()
        self._context_builder = ContextBuilderService()
        self._ai_service = ContentAIService()

    def _generate_initial_blocks(
        self,
        title: str,
        guide: SEOGuide | None = None,
        brief: ContentBrief | None = None,
    ) -> list[dict[str, object]]:
        blocks: list[dict[str, object]] = []
        b_idx = 1

        # 1. Document Title
        blocks.append(
            ContentBlock(
                id=f"block_{b_idx:03d}",
                type=BlockType.DOCUMENT_TITLE,
                level=1,
                text=title,
            ).model_dump()
        )
        b_idx += 1

        # 2. Introduction Paragraph
        default_intro = f"Overview and strategic guide for {title}."
        intro_text = (
            f"An authoritative, practical guide to {brief.primary_keyword or title}. "
            "Explore core architectural concepts and strategic best practices."
            if brief
            else default_intro
        )
        blocks.append(
            ContentBlock(
                id=f"block_{b_idx:03d}",
                type=BlockType.PARAGRAPH,
                text=intro_text,
            ).model_dump()
        )
        b_idx += 1

        # 3. Outline Headings from SEO Guide or Brief
        outline = (guide.outline if guide else []) or []
        if outline:
            for h in outline:
                lvl = int(h.get("level", 2))
                h_text = str(h.get("title") or h.get("text") or "Section")
                if lvl == 1:
                    continue  # Title already added
                blocks.append(
                    ContentBlock(
                        id=f"block_{b_idx:03d}",
                        type=BlockType.HEADING,
                        level=lvl,
                        text=h_text,
                    ).model_dump()
                )
                b_idx += 1
                # Supporting placeholder paragraph
                placeholder = f"Detailed practical analysis regarding {h_text.lower()}."
                blocks.append(
                    ContentBlock(
                        id=f"block_{b_idx:03d}",
                        type=BlockType.PARAGRAPH,
                        text=placeholder,
                    ).model_dump()
                )
                b_idx += 1
        else:
            # Fallback sections
            default_sections = [
                "Understanding the Fundamentals",
                "Step-by-Step Implementation",
                "Best Practices and Guidelines",
                "Common Challenges & Solutions",
            ]
            for sec in default_sections:
                blocks.append(
                    ContentBlock(
                        id=f"block_{b_idx:03d}",
                        type=BlockType.HEADING,
                        level=2,
                        text=sec,
                    ).model_dump()
                )
                b_idx += 1
                blocks.append(
                    ContentBlock(
                        id=f"block_{b_idx:03d}",
                        type=BlockType.PARAGRAPH,
                        text=f"Core considerations and key points regarding {sec.lower()}.",
                    ).model_dump()
                )
                b_idx += 1

        return blocks

    async def get_or_create_document(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        page_id: UUID,
    ) -> ContentDocumentDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            # 1. Fetch Planned Page
            page_stmt = select(PlannedContentPage).where(PlannedContentPage.id == page_id)
            page_res = await session.execute(page_stmt)
            page = page_res.scalars().first()
            if not page:
                raise ResourceNotFound(f"Planned page {page_id} not found")

            # 2. Permission Check
            await self._projects.get_model(
                session,
                actor=actor,
                project_id=page.project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            # 3. Check for existing document
            doc_stmt = select(ContentDocument).where(ContentDocument.page_id == page_id)
            doc_res = await session.execute(doc_stmt)
            existing = doc_res.scalars().first()
            if existing:
                return ContentDocumentDetail.model_validate(existing)

            # 4. Fetch Brief and SEO Guide to initialize outline
            brief_stmt = (
                select(ContentBrief)
                .where(ContentBrief.page_id == page_id)
                .order_by(ContentBrief.created_at.desc())
            )
            brief_res = await session.execute(brief_stmt)
            brief = brief_res.scalars().first()

            guide_stmt = select(SEOGuide).where(SEOGuide.page_id == page_id)
            guide_res = await session.execute(guide_stmt)
            guide = guide_res.scalars().first()

            guide_title = (
                guide.recommended_title if (guide and guide.recommended_title) else page.title
            )
            doc_title = (
                brief.recommended_title if (brief and brief.recommended_title) else guide_title
            )
            initial_blocks = self._generate_initial_blocks(doc_title, guide, brief)
            plain_text = " ".join(str(b.get("text", "")) for b in initial_blocks if b.get("text"))
            word_count = len(plain_text.split()) if plain_text else 0

            # 5. Create ContentDocument
            document = ContentDocument(
                organization_id=page.organization_id,
                project_id=page.project_id,
                website_id=page.website_id,
                page_id=page_id,
                brief_id=brief.id if brief else None,
                title=doc_title,
                slug=page.slug,
                status=DocumentStatus.DRAFT,
                current_version=1,
                lock_version=1,
                content_blocks=initial_blocks,
                plain_text=plain_text,
                word_count=word_count,
                created_by_id=actor.user_id,
                updated_by_id=actor.user_id,
            )
            session.add(document)
            await session.flush()

            # 6. Create Initial Version Snapshot (v1)
            v1 = ContentDocumentVersion(
                organization_id=document.organization_id,
                project_id=document.project_id,
                document_id=document.id,
                version=1,
                content_blocks=initial_blocks,
                plain_text=plain_text,
                word_count=word_count,
                change_type=DocumentChangeType.INITIAL,
                change_summary="Initial document outline initialized",
                created_by_id=actor.user_id,
                created_at=datetime.now(UTC),
            )
            session.add(v1)
            await session.flush()

            await self._audit.log_event(
                session=session,
                organization_id=document.organization_id,
                project_id=document.project_id,
                user_id=actor.user_id,
                action="document.created",
                resource_type="content_document",
                resource_id=document.id,
                metadata={"page_id": str(page_id), "version": 1},
            )

            return ContentDocumentDetail.model_validate(document)

    async def update_document(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        document_id: UUID,
        payload: ContentDocumentUpdate,
    ) -> ContentDocumentDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            doc_stmt = select(ContentDocument).where(ContentDocument.id == document_id)
            doc_res = await session.execute(doc_stmt)
            document = doc_res.scalars().first()
            if not document:
                raise ResourceNotFound(f"Document {document_id} not found")

            # Permission check
            await self._projects.get_model(
                session,
                actor=actor,
                project_id=document.project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            # Optimistic Locking check
            if document.lock_version != payload.lock_version:
                raise ConflictError(
                    "The document was updated in another session (lock version conflict). "
                    "Please reload the document to merge the latest changes."
                )

            if payload.title is not None:
                document.title = payload.title
            if payload.slug is not None:
                document.slug = payload.slug
            if payload.status is not None:
                document.status = payload.status

            if payload.content_blocks is not None:
                blocks_dump = [b.model_dump() for b in payload.content_blocks]
                document.content_blocks = blocks_dump
                plain_text = " ".join(str(b.get("text", "")) for b in blocks_dump if b.get("text"))
                document.plain_text = plain_text
                document.word_count = len(plain_text.split()) if plain_text else 0

            document.lock_version += 1
            document.updated_by_id = actor.user_id
            document.updated_at = datetime.now(UTC)

            # Check if an explicit immutable version snapshot was requested
            if payload.create_version_snapshot:
                document.current_version += 1
                version_record = ContentDocumentVersion(
                    organization_id=document.organization_id,
                    project_id=document.project_id,
                    document_id=document.id,
                    version=document.current_version,
                    content_blocks=document.content_blocks,
                    plain_text=document.plain_text,
                    word_count=document.word_count,
                    change_type=DocumentChangeType.MANUAL_EDIT,
                    change_summary=payload.change_summary,
                    created_by_id=actor.user_id,
                    created_at=datetime.now(UTC),
                )
                session.add(version_record)

            await session.flush()

            await self._audit.log_event(
                session=session,
                organization_id=document.organization_id,
                project_id=document.project_id,
                user_id=actor.user_id,
                action="document.updated",
                resource_type="content_document",
                resource_id=document.id,
                metadata={
                    "version": document.current_version,
                    "lock_version": document.lock_version,
                    "created_snapshot": payload.create_version_snapshot,
                },
            )

            return ContentDocumentDetail.model_validate(document)

    async def list_versions(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        document_id: UUID,
    ) -> ContentDocumentVersionList:
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            doc_stmt = select(ContentDocument).where(ContentDocument.id == document_id)
            doc_res = await session.execute(doc_stmt)
            document = doc_res.scalars().first()
            if not document:
                raise ResourceNotFound(f"Document {document_id} not found")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=document.project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            v_stmt = (
                select(ContentDocumentVersion)
                .where(ContentDocumentVersion.document_id == document_id)
                .order_by(ContentDocumentVersion.version.desc())
            )
            v_res = await session.execute(v_stmt)
            versions = v_res.scalars().all()

            return ContentDocumentVersionList(
                items=[ContentDocumentVersionDetail.model_validate(v) for v in versions]
            )

    async def get_version(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        document_id: UUID,
        version_num: int,
    ) -> ContentDocumentVersionDetail:
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            doc_stmt = select(ContentDocument).where(ContentDocument.id == document_id)
            doc_res = await session.execute(doc_stmt)
            document = doc_res.scalars().first()
            if not document:
                raise ResourceNotFound(f"Document {document_id} not found")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=document.project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            v_stmt = select(ContentDocumentVersion).where(
                ContentDocumentVersion.document_id == document_id,
                ContentDocumentVersion.version == version_num,
            )
            v_res = await session.execute(v_stmt)
            version_obj = v_res.scalars().first()
            if not version_obj:
                raise ResourceNotFound(
                    f"Version {version_num} not found for document {document_id}"
                )

            return ContentDocumentVersionDetail.model_validate(version_obj)

    async def restore_version(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        document_id: UUID,
        version_num: int,
        change_summary: str = "Restored from previous version",
    ) -> ContentDocumentDetail:
        """Restores a historical version non-destructively as a NEW version snapshot."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            doc_stmt = select(ContentDocument).where(ContentDocument.id == document_id)
            doc_res = await session.execute(doc_stmt)
            document = doc_res.scalars().first()
            if not document:
                raise ResourceNotFound(f"Document {document_id} not found")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=document.project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            v_stmt = select(ContentDocumentVersion).where(
                ContentDocumentVersion.document_id == document_id,
                ContentDocumentVersion.version == version_num,
            )
            v_res = await session.execute(v_stmt)
            target_v = v_res.scalars().first()
            if not target_v:
                raise ResourceNotFound(
                    f"Version {version_num} not found for document {document_id}"
                )

            # Bump version numbers
            document.current_version += 1
            document.lock_version += 1
            document.content_blocks = target_v.content_blocks
            document.plain_text = target_v.plain_text
            document.word_count = target_v.word_count
            document.updated_by_id = actor.user_id
            document.updated_at = datetime.now(UTC)

            # Create new version record preserving all previous versions
            new_v = ContentDocumentVersion(
                organization_id=document.organization_id,
                project_id=document.project_id,
                document_id=document.id,
                version=document.current_version,
                content_blocks=target_v.content_blocks,
                plain_text=target_v.plain_text,
                word_count=target_v.word_count,
                change_type=DocumentChangeType.RESTORE,
                change_summary=f"Restored from v{version_num}: {change_summary}",
                created_by_id=actor.user_id,
                created_at=datetime.now(UTC),
            )
            session.add(new_v)
            await session.flush()

            await self._audit.log_event(
                session=session,
                organization_id=document.organization_id,
                project_id=document.project_id,
                user_id=actor.user_id,
                action="document_version.restored",
                resource_type="content_document",
                resource_id=document.id,
                metadata={
                    "restored_from_version": version_num,
                    "new_version": document.current_version,
                },
            )

            return ContentDocumentDetail.model_validate(document)

    async def chat_and_propose(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        document_id: UUID,
        payload: ChatMessageRequest,
    ) -> ChatMessageDetail:
        """Processes a chat turn, assembles context, generates AI proposal, and validates patch."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            # 1. Fetch document
            doc_stmt = select(ContentDocument).where(ContentDocument.id == document_id)
            doc_res = await session.execute(doc_stmt)
            document = doc_res.scalars().first()
            if not document:
                raise ResourceNotFound(f"Document {document_id} not found")

            # 2. Permission check
            await self._projects.get_model(
                session,
                actor=actor,
                project_id=document.project_id,
                permission=PermissionCode.CONTENT_WRITE,
            )

            # 3. Find or create Chat Session
            sess_stmt = (
                select(ContentChatSession)
                .where(ContentChatSession.document_id == document_id)
                .order_by(ContentChatSession.created_at.desc())
            )
            sess_res = await session.execute(sess_stmt)
            chat_session = sess_res.scalars().first()
            if not chat_session:
                chat_session = ContentChatSession(
                    organization_id=document.organization_id,
                    project_id=document.project_id,
                    document_id=document_id,
                    title="Document Assistant",
                    created_by_id=actor.user_id,
                )
                session.add(chat_session)
                await session.flush()

            # 4. Fetch recent messages
            rec_stmt = (
                select(ContentChatMessage)
                .where(ContentChatMessage.session_id == chat_session.id)
                .order_by(ContentChatMessage.created_at.asc())
            )
            rec_res = await session.execute(rec_stmt)
            recent_msgs = list(rec_res.scalars().all())

            # 5. Record User Message
            user_msg = ContentChatMessage(
                session_id=chat_session.id,
                document_id=document_id,
                role="USER",
                content=payload.message,
                context_snapshot={},
                token_usage={},
                created_at=datetime.now(UTC),
            )
            session.add(user_msg)
            await session.flush()

            # 6. Build Context Bundle
            messages, context_snapshot = await self._context_builder.build_context(
                session,
                document=document,
                user_message=payload.message,
                selected_block_id=payload.selected_block_id,
                selected_text=payload.selected_text,
                recent_messages=recent_msgs,
            )

            # 7. Generate Structured AI Output
            ai_response = await self._ai_service.generate_edit_proposal(messages)

            # 8. If operations proposed, validate against active blocks
            proposal: AIEditProposal | None = None
            if ai_response.operations:
                try:
                    self._patch_service.validate_operations(
                        document.content_blocks or [],
                        ai_response.operations,
                    )
                    target_ids = [
                        op.block_id or op.target_block_id
                        for op in ai_response.operations
                        if (op.block_id or op.target_block_id)
                    ]
                    op_type = (
                        ai_response.operations[0].operation.value
                        if len(ai_response.operations) == 1
                        else OperationType.BATCH_OPERATIONS.value
                    )
                    ops_dump = [o.model_dump() for o in ai_response.operations]

                    # Extract previous content from operations or active blocks
                    old_text = ""
                    new_text = ""
                    if ai_response.operations:
                        first_op = ai_response.operations[0]
                        if first_op.old_content:
                            old_text = first_op.old_content
                        elif first_op.block_id or first_op.target_block_id:
                            target_id = first_op.block_id or first_op.target_block_id
                            for b in document.content_blocks or []:
                                if isinstance(b, dict) and b.get("id") == target_id:
                                    old_text = str(b.get("text", ""))
                                    break

                        if first_op.new_content:
                            new_text = first_op.new_content
                        elif first_op.anchor_text and first_op.url:
                            new_text = f"[{first_op.anchor_text}]({first_op.url})"

                    proposal = AIEditProposal(
                        document_id=document_id,
                        chat_message_id=None,  # updated after assistant msg is created
                        status=ProposalStatus.PROPOSED,
                        operation_type=op_type,
                        target_block_ids=target_ids,
                        old_content={"text": old_text},
                        proposed_content={"text": new_text, "operations": ops_dump},
                        diff_summary=ai_response.diff_summary,
                        reason=ai_response.reason,
                        ai_provider=ai_response.provider or "gemini",
                        model=ai_response.model or "gemini-flash-latest",
                        created_at=datetime.now(UTC),
                    )
                    session.add(proposal)
                    await session.flush()
                except Exception as ex:
                    # Invalid operations from model: notify without persisting broken patch
                    ai_response.message += f"\n[Notice: Proposal could not be validated: {ex}]"
                    ai_response.operations = []

            # 9. Record Assistant Message
            assistant_msg = ContentChatMessage(
                session_id=chat_session.id,
                document_id=document_id,
                role="ASSISTANT",
                content=ai_response.message,
                context_snapshot=context_snapshot,
                token_usage={"input_tokens": 300, "output_tokens": 150},
                created_at=datetime.now(UTC),
            )
            session.add(assistant_msg)
            await session.flush()

            if proposal:
                proposal.chat_message_id = assistant_msg.id
                await session.flush()

                await self._audit.log_event(
                    session=session,
                    organization_id=document.organization_id,
                    project_id=document.project_id,
                    user_id=actor.user_id,
                    action="ai_proposal.created",
                    resource_type="ai_edit_proposal",
                    resource_id=proposal.id,
                    metadata={
                        "document_id": str(document.id),
                        "operation_type": proposal.operation_type,
                    },
                )

            detail = ChatMessageDetail(
                id=assistant_msg.id,
                session_id=assistant_msg.session_id,
                document_id=assistant_msg.document_id,
                role=assistant_msg.role,
                content=assistant_msg.content,
                context_snapshot=assistant_msg.context_snapshot,
                token_usage=assistant_msg.token_usage,
                created_at=assistant_msg.created_at,
                proposal=AIProposalDetail.model_validate(proposal) if proposal else None,
            )

            return detail

    async def get_chat_session(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        document_id: UUID,
    ) -> ChatSessionDetail:
        """Fetches the current chat session and recent conversation turns."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)

            doc_stmt = select(ContentDocument).where(ContentDocument.id == document_id)
            doc_res = await session.execute(doc_stmt)
            document = doc_res.scalars().first()
            if not document:
                raise ResourceNotFound(f"Document {document_id} not found")

            await self._projects.get_model(
                session,
                actor=actor,
                project_id=document.project_id,
                permission=PermissionCode.CONTENT_READ,
            )

            sess_stmt = (
                select(ContentChatSession)
                .where(ContentChatSession.document_id == document_id)
                .order_by(ContentChatSession.created_at.desc())
            )
            sess_res = await session.execute(sess_stmt)
            chat_session = sess_res.scalars().first()

            if not chat_session:
                chat_session = ContentChatSession(
                    organization_id=document.organization_id,
                    project_id=document.project_id,
                    document_id=document_id,
                    title="Document Assistant",
                    created_by_id=actor.user_id,
                )
                session.add(chat_session)
                await session.flush()

            msg_stmt = (
                select(ContentChatMessage)
                .where(ContentChatMessage.session_id == chat_session.id)
                .order_by(ContentChatMessage.created_at.asc())
            )
            msg_res = await session.execute(msg_stmt)
            messages = list(msg_res.scalars().all())

            # Load any active proposals
            prop_stmt = select(AIEditProposal).where(AIEditProposal.document_id == document_id)
            prop_res = await session.execute(prop_stmt)
            proposals_by_msg = {
                p.chat_message_id: p for p in prop_res.scalars().all() if p.chat_message_id
            }

            msg_details = [
                ChatMessageDetail(
                    id=m.id,
                    session_id=m.session_id,
                    document_id=m.document_id,
                    role=m.role,
                    content=m.content,
                    context_snapshot=m.context_snapshot,
                    token_usage=m.token_usage,
                    created_at=m.created_at,
                    proposal=AIProposalDetail.model_validate(proposals_by_msg[m.id])
                    if m.id in proposals_by_msg
                    else None,
                )
                for m in messages
            ]

            return ChatSessionDetail(
                id=chat_session.id,
                organization_id=chat_session.organization_id,
                project_id=chat_session.project_id,
                document_id=chat_session.document_id,
                title=chat_session.title,
                created_by_id=chat_session.created_by_id,
                created_at=chat_session.created_at,
                updated_at=chat_session.updated_at,
                messages=msg_details,
            )
