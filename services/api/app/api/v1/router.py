from fastapi import APIRouter

from app.api.v1.admin.auth import router as admin_auth_router
from app.api.v1.admin.media import router as admin_media_router
from app.api.v1.admin.products import router as admin_products_router
from app.api.v1.admin.store_content import router as admin_store_content_router
from app.api.v1.admin.stores import router as admin_stores_router
from app.api.v1.admin.users import router as admin_users_router
from app.api.v1.app.auth import router as app_auth_router
from app.api.v1.app.me import router as app_me_router
from app.api.v1.app.products import router as app_products_router
from app.api.v1.app.store_home import router as app_store_home_router
from app.api.v1.app.stores import router as app_stores_router

router = APIRouter(prefix="/api/v1")

router.include_router(admin_auth_router, prefix="/admin")
router.include_router(admin_media_router, prefix="/admin")
router.include_router(admin_products_router, prefix="/admin")
router.include_router(admin_store_content_router, prefix="/admin")
router.include_router(admin_stores_router, prefix="/admin")
router.include_router(admin_users_router, prefix="/admin")
router.include_router(app_auth_router, prefix="/app")
router.include_router(app_me_router, prefix="/app")
router.include_router(app_store_home_router, prefix="/app")
router.include_router(app_products_router, prefix="/app")
router.include_router(app_stores_router, prefix="/app")
