from fastapi import APIRouter

from app.api.v3 import canvas, demand, site_import

router = APIRouter(prefix="/v3")

router.include_router(canvas.router)
router.include_router(demand.router)
router.include_router(site_import.router)
