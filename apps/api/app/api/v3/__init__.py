from fastapi import APIRouter

from app.api.v1 import content_harness, crawling, pages
from app.api.v3 import (
    brand_kit,
    canvas,
    content_hub,
    demand,
    plan_lock,
    site_import,
    strategy_map,
)

router = APIRouter(prefix="/v3")

router.include_router(canvas.router)
router.include_router(brand_kit.router)
router.include_router(demand.router)
router.include_router(site_import.router)
router.include_router(strategy_map.router)
router.include_router(plan_lock.router)
router.include_router(content_hub.router)

# Migration facades: these routes intentionally reuse the established domain
# services and persistence.  Keeping one implementation prevents the V3 UI and
# the compatibility V1 UI from drifting while clients move to the V3 shell.
router.include_router(crawling.router)
router.include_router(pages.router)
router.include_router(content_harness.router)
