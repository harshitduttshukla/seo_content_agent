"""Version 1 route assembly."""

from fastapi import APIRouter

from app.api.v1.organizations import router as organizations_router
from app.api.v1.projects import router as projects_router
from app.api.v1.users import router as users_router
from app.api.v1.websites import router as websites_router

router = APIRouter()
router.include_router(users_router)
router.include_router(organizations_router)
router.include_router(projects_router)
router.include_router(websites_router)
