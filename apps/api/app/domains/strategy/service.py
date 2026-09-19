import json
from uuid import UUID

from app.ai.provider import AIMessage, GenerationRequest
from app.core.errors import DomainError, ResourceNotFound
from app.db.session import set_actor_context
from app.domains.ai.service import get_ai_provider
from app.domains.audit.repository import AuditWriter, OutboxWriter
from app.domains.crawling.models import CrawlJob, CrawlUrl
from app.domains.projects.service import ProjectService
from app.domains.strategy.models import StrategyStatus
from app.domains.strategy.repository import SEOStrategyRepository
from app.domains.strategy.schemas import (
    StrategyDataSchema,
    StrategyResponse,
    StrategyUpdateRequest,
    StrategyVersionListResponse,
    StrategyVersionResponse,
)
from app.domains.websites.models import Website, WebsiteStatus
from app.security.principal import AuthenticatedUser, PermissionCode
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class SEOStrategyService:
    def __init__(self) -> None:
        self._repository = SEOStrategyRepository()
        self._projects = ProjectService()
        self._audit = AuditWriter()
        self._outbox = OutboxWriter()

    async def get_or_create_strategy(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        request_id: str = "",
    ) -> StrategyResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            strategy = await self._repository.get_by_project_id(
                session, project_id=project.id, organization_id=project.organization_id
            )
            if strategy is None:
                strategy = await self._repository.create_strategy(
                    session,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    current_version=1,
                    status=StrategyStatus.ACTIVE,
                )
                default_data = StrategyDataSchema()
                v1 = await self._repository.create_version(
                    session,
                    strategy_id=strategy.id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    version=1,
                    created_by_id=actor.user_id,
                    change_summary="Initial strategy template initialized",
                    strategy_data=default_data.model_dump(mode="json"),
                )
                self._audit.add(
                    session,
                    actor_user_id=actor.user_id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    action="strategy.created",
                    resource_type="seo_strategy",
                    resource_id=strategy.id,
                    request_id=request_id,
                )
                await session.flush()
                await session.refresh(strategy)
                return StrategyResponse(
                    id=strategy.id,
                    organization_id=strategy.organization_id,
                    project_id=strategy.project_id,
                    current_version=strategy.current_version,
                    status=strategy.status,
                    strategy_data=default_data,
                    change_summary=v1.change_summary,
                    created_at=strategy.created_at,
                    updated_at=strategy.updated_at,
                )

            latest_version = await self._repository.get_latest_version(
                session, strategy_id=strategy.id
            )
            strategy_data = (
                StrategyDataSchema.model_validate(latest_version.strategy_data)
                if latest_version
                else StrategyDataSchema()
            )
            return StrategyResponse(
                id=strategy.id,
                organization_id=strategy.organization_id,
                project_id=strategy.project_id,
                current_version=strategy.current_version,
                status=strategy.status,
                strategy_data=strategy_data,
                change_summary=latest_version.change_summary if latest_version else "",
                created_at=strategy.created_at,
                updated_at=strategy.updated_at,
            )

    async def update_strategy(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        payload: StrategyUpdateRequest,
        request_id: str = "",
    ) -> StrategyResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_WRITE,
            )
            strategy = await self._repository.get_by_project_id(
                session,
                project_id=project.id,
                organization_id=project.organization_id,
                for_update=True,
            )
            is_first_save = False
            latest_version = None
            if strategy is None:
                strategy = await self._repository.create_strategy(
                    session,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    current_version=1,
                    status=StrategyStatus.ACTIVE,
                )
                new_version_no = 1
                is_first_save = True
            else:
                latest_version = await self._repository.get_latest_version(
                    session, strategy_id=strategy.id
                )
                if (
                    strategy.current_version == 1
                    and latest_version
                    and latest_version.change_summary == "Initial strategy template initialized"
                ):
                    new_version_no = 1
                    strategy.status = StrategyStatus.ACTIVE
                    is_first_save = True
                else:
                    max_ver = max(
                        strategy.current_version,
                        latest_version.version if latest_version else 0,
                    )
                    new_version_no = max_ver + 1
                    strategy.current_version = new_version_no
                    strategy.revision += 1
                    strategy.status = StrategyStatus.ACTIVE

            default_summary = (
                "Initial strategy creation"
                if is_first_save
                else f"Updated to version {new_version_no}"
            )
            summary = payload.change_summary.strip() or default_summary

            if is_first_save and latest_version:
                latest_version.change_summary = summary
                latest_version.strategy_data = payload.strategy_data.model_dump(mode="json")
                latest_version.created_by_id = actor.user_id
                version = latest_version
            else:
                version = await self._repository.create_version(
                    session,
                    strategy_id=strategy.id,
                    organization_id=project.organization_id,
                    project_id=project.id,
                    version=new_version_no,
                    created_by_id=actor.user_id,
                    change_summary=summary,
                    strategy_data=payload.strategy_data.model_dump(mode="json"),
                )

            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="strategy.created" if is_first_save else "strategy.updated",
                resource_type="seo_strategy",
                resource_id=strategy.id,
                request_id=request_id,
                metadata={
                    "version": new_version_no,
                    "change_summary": version.change_summary,
                },
            )
            self._outbox.add(
                session,
                organization_id=project.organization_id,
                project_id=project.id,
                aggregate_type="seo_strategy",
                aggregate_id=strategy.id,
                event_type="strategy.version_created",
                payload={"version": new_version_no},
            )
            await session.flush()
            await session.refresh(strategy)
            return StrategyResponse(
                id=strategy.id,
                organization_id=strategy.organization_id,
                project_id=strategy.project_id,
                current_version=strategy.current_version,
                status=strategy.status,
                strategy_data=payload.strategy_data,
                change_summary=version.change_summary,
                created_at=strategy.created_at,
                updated_at=strategy.updated_at,
            )

    async def generate_initial_strategy_draft(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        request_id: str = "",
    ) -> StrategyDataSchema:
        """Generate a draft initial SEO strategy using AI and available project/website data."""
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_WRITE,
            )

            # 1. Project details
            project_info = {
                "name": project.name,
                "description": project.description,
                "default_locale": project.default_locale,
                "default_country": project.default_country or "Global",
            }

            # 2. Associated websites
            website_stmt = (
                select(Website)
                .where(
                    Website.organization_id == project.organization_id,
                    Website.project_id == project.id,
                    Website.status == WebsiteStatus.ACTIVE,
                )
                .limit(5)
            )
            websites = list((await session.execute(website_stmt)).scalars().all())
            website_info = [
                {"name": w.name, "base_url": w.base_url, "host": w.normalized_host}
                for w in websites
            ]

            # 3. Discovered / Crawled URLs (sample up to 25)
            crawl_stmt = (
                select(CrawlUrl.url)
                .join(CrawlJob, CrawlJob.id == CrawlUrl.crawl_job_id)
                .where(
                    CrawlJob.organization_id == project.organization_id,
                    CrawlJob.project_id == project.id,
                )
                .limit(25)
            )
            crawl_urls = list((await session.execute(crawl_stmt)).scalars().all())

            # 4. Existing keywords (removed legacy domain)
            kw_info = []

            # 5. Existing strategy draft (if any)
            strategy = await self._repository.get_by_project_id(session, project_id=project.id)
            existing_data: dict[str, object] = {}
            if strategy:
                latest = await self._repository.get_latest_version(session, strategy_id=strategy.id)
                if latest and latest.strategy_data:
                    existing_data = latest.strategy_data

        # Construct anti-injection, fenced prompt
        system_prompt = (
            "You are an expert enterprise SEO Strategist. Your task is to generate a\n"
            "comprehensive, practical INITIAL SEO STRATEGY (Version 1 draft) based on context.\n\n"
            "CRITICAL RULES:\n"
            "1. Ground recommendations strictly in provided project, website, and keyword data.\n"
            "2. DO NOT invent fictitious business facts, addresses, or fabricated metrics.\n"
            "3. If specific details (e.g. competitors or personas) are not established,\n"
            "provide realistic industry recommendations labeled '[Needs confirmation]'.\n"
            "4. Focus on topical authority, intent alignment, and high-value positioning.\n"
            "5. Return ONLY a valid JSON object matching the requested schema. No preamble.\n\n"
            "JSON Schema keys required:\n"
            "- business_context: { business_name: str, description: str, "
            "industry: str, locations: list[str] }\n"
            "- audience: { segments: list[str], personas: [{ name: str, description: str, "
            "problems: list[str], goals: list[str], funnel_stage: str }], "
            "needs: list[str], buying_stages: list[str] }\n"
            "- products: [{ name: str, description: str, category: str, "
            "url: str | null, priority: int }]\n"
            "- services: [{ name: str, description: str, category: str, "
            "url: str | null, priority: int }]\n"
            "- markets: [{ name: str, code: str, is_primary: bool }]\n"
            "- goals: [{ type: str, description: str, priority: int }]\n"
            "- competitors: [{ name: str, domain: str, strengths: list[str] }]\n"
            "- seo_objectives: list[str]\n"
            "- content_objectives: list[str]\n"
            "- priority_topics: list[str]\n"
        )

        context_lines = [
            f"Project Name: {project_info['name']}",
            f"Project Description: {project_info['description'] or 'Not provided'}",
            (
                f"Default Locale / Country: {project_info['default_locale']} / "
                f"{project_info['default_country']}"
            ),
        ]
        if website_info:
            context_lines.append(f"Websites: {json.dumps(website_info)}")
        if crawl_urls:
            context_lines.append(f"Sample Website URLs: {json.dumps(crawl_urls)}")
        if kw_info:
            context_lines.append(f"Known Keywords: {json.dumps(kw_info)}")
        if existing_data:
            context_lines.append(f"Existing Partial Strategy Data: {json.dumps(existing_data)}")

        user_prompt = (
            "<STRATEGY_CONTEXT>\n" + "\n".join(context_lines) + "\n</STRATEGY_CONTEXT>\n\n"
            "Generate the initial SEO Strategy Version 1 draft JSON for this project."
        )

        messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="user", content=user_prompt),
        ]

        provider = get_ai_provider()
        try:
            res = await provider.generate(
                GenerationRequest(
                    messages=messages,
                    temperature=0.2,
                    max_output_tokens=4000,
                )
            )
        except Exception as exc:
            raise DomainError(
                "AI_GENERATION_FAILED",
                f"Failed to generate strategy draft: {exc}",
            ) from exc

        clean_text = res.text.strip()
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()

        try:
            validated = StrategyDataSchema.model_validate_json(clean_text)
        except ValidationError as val_err:
            raise DomainError(
                "MALFORMED_AI_OUTPUT",
                f"The AI generated response did not match the strategy schema: {val_err.errors()}",
            ) from val_err
        except Exception as exc:
            raise DomainError(
                "MALFORMED_AI_OUTPUT",
                f"Failed to parse AI strategy response: {exc}",
            ) from exc

        if not validated.business_context.business_name:
            validated.business_context.business_name = project_info["name"]

        # Log audit event
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            self._audit.add(
                session,
                actor_user_id=actor.user_id,
                organization_id=project.organization_id,
                project_id=project.id,
                action="strategy.ai_draft_generated",
                resource_type="seo_strategy",
                resource_id=strategy.id if strategy else None,
                request_id=request_id,
                outcome="success",
                metadata={"provider": res.provider, "model": res.model},
            )

        return validated

    async def list_versions(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
    ) -> StrategyVersionListResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            strategy = await self._repository.get_by_project_id(
                session, project_id=project.id, organization_id=project.organization_id
            )
            if strategy is None:
                return StrategyVersionListResponse(items=[])

            versions = await self._repository.list_versions(session, strategy_id=strategy.id)
            items = [
                StrategyVersionResponse(
                    id=v.id,
                    strategy_id=v.strategy_id,
                    organization_id=v.organization_id,
                    project_id=v.project_id,
                    version=v.version,
                    created_by_id=v.created_by_id,
                    change_summary=v.change_summary,
                    strategy_data=StrategyDataSchema.model_validate(v.strategy_data),
                    created_at=v.created_at,
                )
                for v in versions
            ]
            return StrategyVersionListResponse(items=items)

    async def get_version(
        self,
        session: AsyncSession,
        *,
        actor: AuthenticatedUser,
        project_id: UUID,
        version: int,
    ) -> StrategyVersionResponse:
        async with session.begin():
            await set_actor_context(session, actor.user_id)
            project = await self._projects.get_model(
                session,
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.STRATEGY_READ,
            )
            strategy = await self._repository.get_by_project_id(
                session, project_id=project.id, organization_id=project.organization_id
            )
            if strategy is None:
                raise ResourceNotFound("seo_strategy")

            v = await self._repository.get_version_by_number(
                session, strategy_id=strategy.id, version=version
            )
            if v is None:
                raise ResourceNotFound("seo_strategy_version")

            return StrategyVersionResponse(
                id=v.id,
                strategy_id=v.strategy_id,
                organization_id=v.organization_id,
                project_id=v.project_id,
                version=v.version,
                created_by_id=v.created_by_id,
                change_summary=v.change_summary,
                strategy_data=StrategyDataSchema.model_validate(v.strategy_data),
                created_at=v.created_at,
            )
