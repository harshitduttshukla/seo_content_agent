"""Deterministic SEO and Content Quality Evaluator."""

from uuid import UUID

from app.core.errors import ResourceNotFound
from app.db.session import set_actor_context, transactional_session
from app.domains.content.editor_models import ContentBrief, ContentDocument
from app.domains.projects.service import ProjectService
from app.domains.seo.models import SEOGuide
from app.security.principal import AuthenticatedUser, PermissionCode
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class QualityCheckItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    status: str = Field(description="PASS, WARNING, or FAIL")
    message: str
    recommendation: str = ""


class SEOQualityReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: UUID
    title: str
    word_count: int
    target_word_count: int
    score_percentage: int
    checks: list[QualityCheckItem]


class SEOQualityService:
    def __init__(self) -> None:
        self._projects = ProjectService()

    async def evaluate_document(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        document_id: UUID,
    ) -> SEOQualityReport:
        """Runs deterministic SEO and structural quality rules against a document."""
        async with transactional_session(session):
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

            # Fetch associated brief or guide
            brief: ContentBrief | None = None
            if document.brief_id:
                b_stmt = select(ContentBrief).where(ContentBrief.id == document.brief_id)
                b_res = await session.execute(b_stmt)
                brief = b_res.scalars().first()
            if not brief:
                b_stmt = (
                    select(ContentBrief)
                    .where(ContentBrief.page_id == document.page_id)
                    .order_by(ContentBrief.created_at.desc())
                )
                b_res = await session.execute(b_stmt)
                brief = b_res.scalars().first()

            guide_stmt = select(SEOGuide).where(SEOGuide.page_id == document.page_id)
            guide_res = await session.execute(guide_stmt)
            guide = guide_res.scalars().first()

            primary_kw = (
                (
                    brief.primary_keyword
                    if (brief and brief.primary_keyword)
                    else (guide.primary_keyword if guide else "")
                )
                .strip()
                .lower()
            )

            target_word_count = (
                brief.target_word_count
                if (brief and brief.target_word_count)
                else (guide.word_count_target if guide else 1500)
            )

            required_topics = (
                list(brief.required_topics)
                if (brief and brief.required_topics)
                else (list(guide.required_topics) if guide else [])
            )

            blocks = document.content_blocks or []
            checks: list[QualityCheckItem] = []

            # 1. H1 Presence
            h1_blocks = [
                b for b in blocks if b.get("type") == "DOCUMENT_TITLE" or b.get("level") == 1
            ]
            if len(h1_blocks) == 1:
                checks.append(
                    QualityCheckItem(
                        name="H1 Heading Presence",
                        status="PASS",
                        message="Document has exactly one primary H1 heading.",
                    )
                )
            elif len(h1_blocks) == 0:
                checks.append(
                    QualityCheckItem(
                        name="H1 Heading Presence",
                        status="FAIL",
                        message="Missing H1 heading.",
                        recommendation="Add an H1 heading at the beginning of the document.",
                    )
                )
            else:
                checks.append(
                    QualityCheckItem(
                        name="H1 Heading Presence",
                        status="WARNING",
                        message=f"Multiple H1 headings detected ({len(h1_blocks)}).",
                        recommendation="Ensure only one primary H1 heading exists per page.",
                    )
                )

            # 2. Primary Keyword in Title / H1
            h1_text = h1_blocks[0].get("text", "").lower() if h1_blocks else ""
            if primary_kw:
                if primary_kw in h1_text or primary_kw in document.title.lower():
                    checks.append(
                        QualityCheckItem(
                            name="Primary Keyword in H1",
                            status="PASS",
                            message=f"H1 contains target primary keyword '{primary_kw}'.",
                        )
                    )
                else:
                    checks.append(
                        QualityCheckItem(
                            name="Primary Keyword in H1",
                            status="WARNING",
                            message=f"Primary keyword '{primary_kw}' not found in H1 title.",
                            recommendation="Incorporate target primary keyword naturally into H1.",
                        )
                    )
            else:
                checks.append(
                    QualityCheckItem(
                        name="Primary Keyword Defined",
                        status="WARNING",
                        message="No primary target keyword defined in brief.",
                        recommendation="Define target keyword in Content Brief.",
                    )
                )

            # 3. Word Count Target Progress
            current_wc = document.word_count or 0
            if current_wc >= target_word_count:
                checks.append(
                    QualityCheckItem(
                        name="Word Count Target",
                        status="PASS",
                        message=f"Word count ({current_wc}) meets target ({target_word_count}).",
                    )
                )
            elif current_wc >= target_word_count * 0.7:
                needed = target_word_count - current_wc
                checks.append(
                    QualityCheckItem(
                        name="Word Count Target",
                        status="WARNING",
                        message=f"Word count ({current_wc}) is near target ({target_word_count}).",
                        recommendation=f"Add {needed} more words for comprehensive coverage.",
                    )
                )
            else:
                needed = target_word_count - current_wc
                checks.append(
                    QualityCheckItem(
                        name="Word Count Target",
                        status="FAIL",
                        message=f"Word count ({current_wc}) is below target ({target_word_count}).",
                        recommendation=f"Expand content by {needed} words.",
                    )
                )

            # 4. Primary Keyword in Introduction
            plain_words = (document.plain_text or "").lower().split()
            first_100_words = " ".join(plain_words[:100])
            if primary_kw and primary_kw in first_100_words:
                checks.append(
                    QualityCheckItem(
                        name="Primary Keyword in Intro",
                        status="PASS",
                        message="Primary keyword appears within the opening 100 words.",
                    )
                )
            elif primary_kw:
                checks.append(
                    QualityCheckItem(
                        name="Primary Keyword in Intro",
                        status="WARNING",
                        message="Primary keyword missing from introductory paragraph.",
                        recommendation="Introduce the primary keyword in the first 1-2 paragraphs.",
                    )
                )

            # 5. Required Topics Coverage
            if required_topics:
                doc_text_lower = (document.plain_text or "").lower()
                matched_topics = [
                    t
                    for t in required_topics
                    if any(term in doc_text_lower for term in t.lower().split()[:3])
                ]
                if len(matched_topics) == len(required_topics):
                    checks.append(
                        QualityCheckItem(
                            name="Required Topics Checklist",
                            status="PASS",
                            message=f"All {len(required_topics)} required topics covered.",
                        )
                    )
                else:
                    missing_count = len(required_topics) - len(matched_topics)
                    tot = len(required_topics)
                    checks.append(
                        QualityCheckItem(
                            name="Required Topics Checklist",
                            status="WARNING",
                            message=f"{missing_count} of {tot} topics not yet referenced.",
                            recommendation="Review the Content Brief checklist in sidebar.",
                        )
                    )

            # 6. Empty Blocks Audit
            empty_blocks = [
                b for b in blocks if not str(b.get("text", "")).strip() and not b.get("data")
            ]
            if empty_blocks:
                checks.append(
                    QualityCheckItem(
                        name="Empty Blocks Check",
                        status="WARNING",
                        message=f"{len(empty_blocks)} empty block(s) detected.",
                        recommendation="Fill in placeholder blocks or remove them.",
                    )
                )
            else:
                checks.append(
                    QualityCheckItem(
                        name="Empty Blocks Check",
                        status="PASS",
                        message="No blank or unwritten blocks found.",
                    )
                )

            # Calculate deterministic score
            pass_count = sum(1 for c in checks if c.status == "PASS")
            score = int((pass_count / max(len(checks), 1)) * 100)

            return SEOQualityReport(
                document_id=document.id,
                title=document.title,
                word_count=document.word_count or 0,
                target_word_count=target_word_count,
                score_percentage=score,
                checks=checks,
            )
