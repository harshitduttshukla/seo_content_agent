"""Version 1 route assembly."""

from fastapi import APIRouter

from app.api.v1.architecture import router as architecture_router
from app.api.v1.clusters import router as clusters_router
from app.api.v1.content_map import router as content_map_router
from app.api.v1.content_pages import router as content_pages_router
from app.api.v1.crawling import router as crawling_router
from app.api.v1.internal_linking import router as internal_linking_router
from app.api.v1.keywords import router as keywords_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.pages import router as pages_router
from app.api.v1.projects import router as projects_router
from app.api.v1.seo_guides import router as seo_guides_router
from app.api.v1.strategy import router as strategy_router
from app.api.v1.users import router as users_router
from app.api.v1.websites import router as websites_router

router = APIRouter()
router.include_router(users_router)
router.include_router(organizations_router)
router.include_router(projects_router)
router.include_router(websites_router)
router.include_router(crawling_router)
router.include_router(pages_router)
router.include_router(strategy_router)
router.include_router(keywords_router)
router.include_router(clusters_router)
router.include_router(architecture_router)
router.include_router(content_pages_router)
router.include_router(content_map_router)
router.include_router(seo_guides_router)
router.include_router(internal_linking_router)
