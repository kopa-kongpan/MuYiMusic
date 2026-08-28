from fastapi import APIRouter

from app.api.v1.admin.admin_users import router as admin_accounts_router
from app.api.v1.admin.appointments import router as admin_appointments_router
from app.api.v1.admin.auth import router as admin_auth_router
from app.api.v1.admin.franchise import router as admin_franchise_router
from app.api.v1.admin.media import router as admin_media_router
from app.api.v1.admin.notifications import router as admin_notifications_router
from app.api.v1.admin.products import router as admin_products_router
from app.api.v1.admin.schedules import router as admin_schedules_router
from app.api.v1.admin.store_content import router as admin_store_content_router
from app.api.v1.admin.stores import router as admin_stores_router
from app.api.v1.admin.users import router as admin_users_router
from app.api.v1.app.appointments import router as app_appointments_router
from app.api.v1.app.auth import router as app_auth_router
from app.api.v1.app.franchise import router as app_franchise_router
from app.api.v1.app.me import router as app_me_router
from app.api.v1.app.notifications import router as app_notifications_router
from app.api.v1.app.products import router as app_products_router
from app.api.v1.app.schedules import router as app_schedules_router
from app.api.v1.app.store_home import router as app_store_home_router
from app.api.v1.app.stores import router as app_stores_router
from app.api.v1.app.teacher_portal import router as app_teacher_portal_router

router = APIRouter(prefix="/api/v1")

router.include_router(admin_auth_router, prefix="/admin")
router.include_router(admin_franchise_router, prefix="/admin")
router.include_router(admin_appointments_router, prefix="/admin")
router.include_router(admin_accounts_router, prefix="/admin")
router.include_router(admin_media_router, prefix="/admin")
router.include_router(admin_notifications_router, prefix="/admin")
router.include_router(admin_products_router, prefix="/admin")
router.include_router(admin_schedules_router, prefix="/admin")
router.include_router(admin_store_content_router, prefix="/admin")
router.include_router(admin_stores_router, prefix="/admin")
router.include_router(admin_users_router, prefix="/admin")
router.include_router(app_auth_router, prefix="/app")
router.include_router(app_franchise_router, prefix="/app")
router.include_router(app_appointments_router, prefix="/app")
router.include_router(app_me_router, prefix="/app")
router.include_router(app_notifications_router, prefix="/app")
router.include_router(app_store_home_router, prefix="/app")
router.include_router(app_products_router, prefix="/app")
router.include_router(app_schedules_router, prefix="/app")
router.include_router(app_stores_router, prefix="/app")
router.include_router(app_teacher_portal_router, prefix="/app")
