"""SQLAlchemy models are registered from this package."""

from app.core.database import Base
from app.models.admin import AdminUser, Permission, Role, admin_user_stores
from app.models.audit import AuditLog
from app.models.product import (
    Category,
    Product,
    ProductImage,
    ProductSku,
    ProductStatus,
)
from app.models.store import Store, StoreStatus
from app.models.store_content import (
    ContentBlockStatus,
    ContentBlockType,
    ContentJumpType,
    StoreContentBlock,
)
from app.models.user import (
    CourseEntitlement,
    EntitlementStatus,
    IdentityProvider,
    Order,
    OrderItem,
    OrderStatus,
    ProviderAccount,
    User,
    UserStatus,
)

__all__ = [
    "AdminUser",
    "ContentBlockStatus",
    "ContentBlockType",
    "ContentJumpType",
    "CourseEntitlement",
    "EntitlementStatus",
    "AuditLog",
    "Base",
    "Category",
    "Permission",
    "IdentityProvider",
    "Order",
    "OrderItem",
    "OrderStatus",
    "Product",
    "ProductImage",
    "ProductSku",
    "ProductStatus",
    "ProviderAccount",
    "Role",
    "Store",
    "StoreStatus",
    "StoreContentBlock",
    "User",
    "UserStatus",
    "admin_user_stores",
]
