"""Live-database tests for creating product-tree areas on a canvas (V3 §3.1, §4.4).

Runs as the non-owner ``seo_content_app`` role so RLS is enforced.
"""

from typing import Any

import pytest
from app.core.errors import BadRequestError, ConflictError, ResourceNotFound
from app.domains.canvas.schemas import AreaCreateRequest
from app.domains.canvas.service import CanvasService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration import test_v3_strategy_map_isolation as isolation

pytestmark = pytest.mark.integration

db_engine = isolation.db_engine
session_factory = isolation.session_factory
two_tenants = isolation.two_tenants

Factory = async_sessionmaker[AsyncSession]
Pair = tuple[dict[str, Any], dict[str, Any]]


async def _create(factory: Factory, tenant: dict[str, Any], **fields: Any) -> Any:
    async with factory() as session:
        return await CanvasService(session).create_area(
            tenant["org_id"],
            tenant["project_id"],
            fields.pop("canvas_id", tenant["canvas_id"]),
            AreaCreateRequest(**fields),
            actor=tenant["actor"],
        )


@pytest.mark.asyncio
async def test_creates_root_and_sub_area_that_list_returns(
    session_factory: Factory, two_tenants: Pair
) -> None:
    alpha, _ = two_tenants
    root = await _create(session_factory, alpha, name="  Leak repairs  ")
    child = await _create(
        session_factory,
        alpha,
        name="Tap leaks",
        parent_id=root.id,
        default_argument_id=alpha["argument_id"],
    )
    assert root.name == "Leak repairs" and root.parent_id is None
    assert child.parent_id == root.id and child.default_argument_id == alpha["argument_id"]

    async with session_factory() as session:
        areas = await CanvasService(session).list_areas(
            alpha["org_id"], alpha["project_id"], canvas_id=None, actor=alpha["actor"]
        )
    assert {"Leak repairs", "Tap leaks"} <= {area.name for area in areas}


@pytest.mark.asyncio
async def test_area_names_are_unique_per_project_ignoring_case(
    session_factory: Factory, two_tenants: Pair
) -> None:
    alpha, bravo = two_tenants
    with pytest.raises(ConflictError):
        await _create(session_factory, alpha, name=alpha["area_name"].upper())
    # The same name in another tenant's project is fine.
    created = await _create(session_factory, bravo, name=alpha["area_name"])
    assert created.name == alpha["area_name"]


@pytest.mark.asyncio
async def test_cannot_create_areas_across_tenants(
    session_factory: Factory, two_tenants: Pair
) -> None:
    alpha, bravo = two_tenants
    with pytest.raises(ResourceNotFound):
        await _create(session_factory, alpha, name="Foreign canvas", canvas_id=bravo["canvas_id"])
    with pytest.raises(BadRequestError):
        await _create(session_factory, alpha, name="Foreign parent", parent_id=bravo["area_id"])
    with pytest.raises(BadRequestError):
        await _create(
            session_factory,
            alpha,
            name="Foreign argument",
            default_argument_id=bravo["argument_id"],
        )


def test_blank_area_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        AreaCreateRequest(name="   ")
