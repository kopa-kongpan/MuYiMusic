from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import Order


class PaymentProvider(StrEnum):
    WECHAT = "wechat"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CLOSED = "closed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_order_created", "order_id", "created_at"),
        Index(
            "uq_payments_order_pending",
            "order_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        CheckConstraint("amount_cents > 0", name="ck_payments_amount"),
        CheckConstraint("attempt_no > 0", name="ck_payments_attempt_no"),
        UniqueConstraint(
            "order_id",
            "attempt_no",
            name="uq_payments_order_attempt",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        index=True,
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        Enum(
            PaymentProvider,
            name="payment_provider",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=PaymentProvider.WECHAT,
        server_default=PaymentProvider.WECHAT.value,
        index=True,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
        index=True,
    )
    attempt_no: Mapped[int] = mapped_column(Integer)
    merchant_order_no: Mapped[str] = mapped_column(String(32), unique=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    prepay_id: Mapped[str | None] = mapped_column(String(128))
    notify_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    order: Mapped["Order"] = relationship(back_populates="payments")
