from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FulfillmentStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WechatFulfillment(Base):
    __tablename__ = "wechat_fulfillments"
    __table_args__ = (
        CheckConstraint("logistics_type IN (3, 4)", name="ck_fulfillment_logistics"),
        CheckConstraint("attempts >= 0", name="ck_fulfillment_attempts"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), unique=True
    )
    confirmed_by_admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_users.id", ondelete="RESTRICT")
    )
    logistics_type: Mapped[int] = mapped_column(Integer)
    item_description: Mapped[str] = mapped_column(String(120))
    evidence: Mapped[str] = mapped_column(String(500))
    payer_openid: Mapped[str] = mapped_column(String(128))
    status: Mapped[FulfillmentStatus] = mapped_column(
        Enum(
            FulfillmentStatus,
            name="fulfillment_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=FulfillmentStatus.PENDING,
        server_default=FulfillmentStatus.PENDING.value,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    last_error: Mapped[str | None] = mapped_column(String(128))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
