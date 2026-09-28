"""Live-database tests for the saved demand CSV column mapping (V3 §4.2, §4.5 Ingest).

Runs as the non-owner ``seo_content_app`` role so RLS is enforced.
"""

from typing import Any

import pytest
from app.core.errors import PermissionDenied, ResourceNotFound
from app.domains.demand.schemas import DemandImportItem, DemandImportRequest
from app.domains.demand.service import DemandService
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration import test_v3_demand_plan as plan_tests

pytestmark = pytest.mark.integration

db_engine = plan_tests.db_engine
session_factory = plan_tests.session_factory
owner_factory = plan_tests.owner_factory
tenants = plan_tests.tenants

Factory = async_sessionmaker[AsyncSession]
Pair = tuple[dict[str, Any], dict[str, Any]]
MAPPING = {"text": "Keyword", "type": "Kind", "volume": "Avg. monthly searches"}


def _request(tenant: dict[str, Any], mapping: dict[str, str] | None) -> DemandImportRequest:
    item = DemandImportItem(text=f"{tenant['label']} mapped keyword", type="keyword", volume=90)
    return DemandImportRequest(items=[item], column_mapping=mapping)


async def _import(factory: Factory, tenant: dict[str, Any], mapping: dict[str, str] | None) -> None:
    async with factory() as session:
        await DemandService(session).import_nodes(
            tenant["org_id"], tenant["project_id"], _request(tenant, mapping), actor=tenant["actor"]
        )


async def _mapping(factory: Factory, tenant: dict[str, Any]) -> dict[str, str]:
    async with factory() as session:
        result = await DemandService(session).get_csv_mapping(
            tenant["org_id"], tenant["project_id"], tenant["actor"]
        )
    return result.column_mapping


@pytest.mark.asyncio
async def test_import_saves_the_mapping_and_keeps_other_workspace_config(
    session_factory: Factory, owner_factory: Factory, tenants: Pair
) -> None:
    alpha, bravo = tenants
    assert await _mapping(session_factory, alpha) == {}
    await _import(session_factory, alpha, MAPPING)

    assert await _mapping(session_factory, alpha) == MAPPING
    assert await _mapping(session_factory, bravo) == {}  # never shared across tenants
    async with owner_factory() as session:
        config = (
            await session.execute(
                text("SELECT workspace_config FROM projects WHERE id = :p"),
                {"p": alpha["project_id"]},
            )
        ).scalar_one()
    assert config["cluster_volume_floor"] == 300  # the rest of the config is untouched


@pytest.mark.asyncio
async def test_import_without_a_mapping_leaves_the_saved_one(
    session_factory: Factory, tenants: Pair
) -> None:
    alpha, _ = tenants
    await _import(session_factory, alpha, MAPPING)
    await _import(session_factory, alpha, None)
    assert await _mapping(session_factory, alpha) == MAPPING


@pytest.mark.asyncio
async def test_mapping_is_refused_for_another_tenants_project(
    session_factory: Factory, tenants: Pair
) -> None:
    alpha, bravo = tenants
    for organization_id in (bravo["org_id"], alpha["org_id"]):
        async with session_factory() as session:
            with pytest.raises((ResourceNotFound, PermissionDenied)):
                await DemandService(session).get_csv_mapping(
                    organization_id, bravo["project_id"], alpha["actor"]
                )


def test_unknown_mapping_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DemandImportRequest(
            items=[DemandImportItem(text="x", type="keyword")], column_mapping={"owner": "Owner"}
        )
