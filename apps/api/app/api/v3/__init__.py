from fastapi import APIRouter

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
