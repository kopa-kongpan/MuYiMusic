"""SQLAlchemy models are registered from this package."""

from app.core.database import Base
from app.models.admin import AdminUser, Permission, Role, admin_user_stores
from app.models.appointment import (
    Appointment,
    AppointmentCancelledBy,
    AppointmentStatus,
    ConsumptionKind,
    ConsumptionStatus,
    LessonConsumption,
)
from app.models.audit import AuditLog
from app.models.franchise import FranchisePage
from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationOutbox,
    NotificationRecipientType,
    NotificationSubscription,
    SubscriptionStatus,
    TeacherAccount,
    TeacherBindCode,
)
from app.models.product import (
    Category,
    Product,
    ProductImage,
    ProductSku,
    ProductStatus,
    ProductVideoCourseBinding,
    VideoCourse,
    VideoCourseLesson,
)
from app.models.schedule import ClassSchedule, ScheduleStatus, Teacher
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
    "Appointment",
    "AppointmentCancelledBy",
    "AppointmentStatus",
    "ContentBlockStatus",
    "ContentBlockType",
    "ContentJumpType",
    "CourseEntitlement",
    "ConsumptionKind",
    "ConsumptionStatus",
    "EntitlementStatus",
    "FranchisePage",
    "AuditLog",
    "Base",
    "Category",
    "ClassSchedule",
    "Permission",
    "IdentityProvider",
    "LessonConsumption",
    "Notification",
    "NotificationChannel",
    "NotificationDeliveryStatus",
    "NotificationOutbox",
    "NotificationRecipientType",
    "NotificationSubscription",
    "Order",
    "OrderItem",
    "OrderStatus",
    "Product",
    "ProductImage",
    "ProductSku",
    "ProductStatus",
    "ProductVideoCourseBinding",
    "ProviderAccount",
    "Role",
    "ScheduleStatus",
    "Store",
    "StoreStatus",
    "StoreContentBlock",
    "SubscriptionStatus",
    "Teacher",
    "TeacherAccount",
    "TeacherBindCode",
    "User",
    "UserStatus",
    "VideoCourse",
    "VideoCourseLesson",
    "admin_user_stores",
]
