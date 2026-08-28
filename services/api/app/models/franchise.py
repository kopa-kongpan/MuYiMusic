from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FranchisePage(Base):
    __tablename__ = "franchise_pages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), unique=True
    )
    title: Mapped[str] = mapped_column(String(128))
    introduction: Mapped[str] = mapped_column(Text)
    advantages: Mapped[str] = mapped_column(Text)
    support_policy: Mapped[str] = mapped_column(Text)
    application_process: Mapped[str] = mapped_column(Text)
    contact_name: Mapped[str] = mapped_column(String(64))
    contact_phone: Mapped[str] = mapped_column(String(32))
    contact_wechat: Mapped[str | None] = mapped_column(String(64))
    is_published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
