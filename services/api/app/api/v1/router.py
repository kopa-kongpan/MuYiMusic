from fastapi import APIRouter

from app.api.v1.admin.auth import router as admin_auth_router
from app.api.v1.admin.stores import router as admin_stores_router
from app.api.v1.app.stores import router as app_stores_router

router = APIRouter(prefix="/api/v1")

router.include_router(admin_auth_router, prefix="/admin")
router.include_router(admin_stores_router, prefix="/admin")
router.include_router(app_stores_router, prefix="/app")
