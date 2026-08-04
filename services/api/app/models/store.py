from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.admin import AdminUser


class StoreStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), index=True)
    city: Mapped[str] = mapped_column(String(64), index=True)
    district: Mapped[str] = mapped_column(String(64), default="")
    address: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(String(32))
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    status: Mapped[StoreStatus] = mapped_column(
        Enum(
            StoreStatus,
            name="store_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=StoreStatus.ACTIVE,
        server_default=StoreStatus.ACTIVE.value,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    authorized_admins: Mapped[list["AdminUser"]] = relationship(
        secondary="admin_user_stores",
        back_populates="stores",
    )
