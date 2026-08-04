from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentBlockType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    SHORTCUT = "shortcut"


class ContentBlockStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class ContentJumpType(StrEnum):
    NONE = "none"
    INTERNAL = "internal"
    WEB_URL = "web_url"


class StoreContentBlock(Base):
    __tablename__ = "store_content_blocks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        index=True,
    )
    block_type: Mapped[ContentBlockType] = mapped_column(
        Enum(
            ContentBlockType,
            name="content_block_type",
            values_callable=lambda values: [value.value for value in values],
        ),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(128))
    media_object_key: Mapped[str | None] = mapped_column(String(1024))
    jump_type: Mapped[ContentJumpType] = mapped_column(
        Enum(
            ContentJumpType,
            name="content_jump_type",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=ContentJumpType.NONE,
        server_default=ContentJumpType.NONE.value,
    )
    jump_target: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )
    status: Mapped[ContentBlockStatus] = mapped_column(
        Enum(
            ContentBlockStatus,
            name="content_block_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=ContentBlockStatus.ENABLED,
        server_default=ContentBlockStatus.ENABLED.value,
        index=True,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
