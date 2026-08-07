from datetime import datetime

from app.models.user import CourseEntitlement, EntitlementStatus


def sync_entitlement_status(
    entitlement: CourseEntitlement,
    now: datetime,
) -> None:
    """按课时与有效期同步权益状态。

    视频课程权益（total_lessons == 0）只表达观看权，不参与课时消耗，
    因此不会进入 EXHAUSTED，只在 active 与 expired 之间转换。
    """
    if entitlement.remaining_lessons == 0 and entitlement.total_lessons > 0:
        entitlement.status = EntitlementStatus.EXHAUSTED
    elif entitlement.expires_at is not None and entitlement.expires_at <= now:
        entitlement.status = EntitlementStatus.EXPIRED
    else:
        entitlement.status = EntitlementStatus.ACTIVE
