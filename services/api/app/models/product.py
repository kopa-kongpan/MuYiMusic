from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.store import Store


class ProductStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    OFFLINE = "offline"
    ARCHIVED = "archived"


class ProductType(StrEnum):
    COURSE = "course"
    VIDEO = "video"


class VideoCourseAccessMode(StrEnum):
    ALL = "all"
    SELECTED = "selected"


product_video_course_binding_lessons = Table(
    "product_video_course_binding_lessons",
    Base.metadata,
    Column(
        "binding_id",
        ForeignKey("product_video_course_bindings.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "video_course_lesson_id",
        ForeignKey("video_course_lessons.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Category(Base):
    __tablename__ = "categories"
    # 迁移里已有的复合索引，必须在模型里同步声明，否则 autogenerate 会 drop 掉。
    __table_args__ = (
        Index("ix_categories_store_public", "store_id", "is_enabled", "sort_order"),
        UniqueConstraint("store_id", "name", name="uq_categories_store_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        index=True,
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
    store: Mapped["Store"] = relationship()
    products: Mapped[list["Product"]] = relationship(back_populates="category")
    video_courses: Mapped[list["VideoCourse"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_public", "store_id", "status", "sort_order"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), index=True)
    summary: Mapped[str] = mapped_column(String(300), default="", server_default="")
    details: Mapped[str] = mapped_column(Text, default="", server_default="")
    notes: Mapped[str | None] = mapped_column(Text)
    cover_object_key: Mapped[str] = mapped_column(String(1024))
    product_type: Mapped[ProductType] = mapped_column(
        Enum(
            ProductType,
            name="product_type",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=ProductType.COURSE,
        server_default=ProductType.COURSE.value,
        index=True,
    )
    status: Mapped[ProductStatus] = mapped_column(
        Enum(
            ProductStatus,
            name="product_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=ProductStatus.DRAFT,
        server_default=ProductStatus.DRAFT.value,
        index=True,
    )
    sale_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sale_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sales_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    store: Mapped["Store"] = relationship()
    category: Mapped[Category] = relationship(back_populates="products")
    skus: Mapped[list["ProductSku"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductSku.sort_order, ProductSku.created_at",
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductImage.sort_order, ProductImage.created_at",
    )
    video_course_bindings: Mapped[list["ProductVideoCourseBinding"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductVideoCourseBinding.created_at",
    )


class ProductSku(Base):
    __tablename__ = "product_skus"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128))
    price_cents: Mapped[int] = mapped_column(Integer)
    lesson_count: Mapped[int] = mapped_column(Integer)
    validity_days: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        index=True,
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
    product: Mapped[Product] = relationship(back_populates="skus")


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    object_key: Mapped[str] = mapped_column(String(1024))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    product: Mapped[Product] = relationship(back_populates="images")


class VideoCourse(Base):
    __tablename__ = "video_courses"
    __table_args__ = (
        UniqueConstraint("store_id", "name", name="uq_video_courses_store_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), index=True)
    summary: Mapped[str] = mapped_column(String(300), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        index=True,
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
    store: Mapped["Store"] = relationship()
    category: Mapped[Category] = relationship(back_populates="video_courses")
    lessons: Mapped[list["VideoCourseLesson"]] = relationship(
        back_populates="video_course",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="VideoCourseLesson.lesson_number, VideoCourseLesson.created_at",
    )
    product_bindings: Mapped[list["ProductVideoCourseBinding"]] = relationship(
        back_populates="video_course"
    )


class VideoCourseLesson(Base):
    __tablename__ = "video_course_lessons"
    __table_args__ = (
        CheckConstraint(
            "lesson_number > 0",
            name="ck_video_course_lessons_lesson_number",
        ),
        UniqueConstraint(
            "video_course_id",
            "lesson_number",
            name="uq_video_course_lessons_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    video_course_id: Mapped[UUID] = mapped_column(
        ForeignKey("video_courses.id", ondelete="CASCADE"),
        index=True,
    )
    lesson_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    object_key: Mapped[str] = mapped_column(String(1024))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        index=True,
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
    video_course: Mapped[VideoCourse] = relationship(back_populates="lessons")


class ProductVideoCourseBinding(Base):
    __tablename__ = "product_video_course_bindings"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "video_course_id",
            name="uq_product_video_course_bindings_course",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    video_course_id: Mapped[UUID] = mapped_column(
        ForeignKey("video_courses.id", ondelete="CASCADE"),
        index=True,
    )
    access_mode: Mapped[VideoCourseAccessMode] = mapped_column(
        Enum(
            VideoCourseAccessMode,
            name="video_course_access_mode",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=VideoCourseAccessMode.ALL,
        server_default=VideoCourseAccessMode.ALL.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    product: Mapped[Product] = relationship(back_populates="video_course_bindings")
    video_course: Mapped[VideoCourse] = relationship(
        back_populates="product_bindings",
        lazy="selectin",
    )
    selected_lessons: Mapped[list[VideoCourseLesson]] = relationship(
        secondary=product_video_course_binding_lessons,
        lazy="selectin",
        order_by="VideoCourseLesson.lesson_number, VideoCourseLesson.created_at",
    )
