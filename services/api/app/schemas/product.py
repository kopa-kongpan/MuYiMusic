from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.product import ProductStatus, ProductType, VideoCourseAccessMode


def validate_sale_window(
    sale_starts_at: datetime | None,
    sale_ends_at: datetime | None,
) -> None:
    for value in (sale_starts_at, sale_ends_at):
        if value is not None and value.tzinfo is None:
            raise ValueError("销售时间必须包含时区")
    if (
        sale_starts_at is not None
        and sale_ends_at is not None
        and sale_starts_at >= sale_ends_at
    ):
        raise ValueError("销售结束时间必须晚于开始时间")


class ProductSort(StrEnum):
    COMPREHENSIVE = "comprehensive"
    SALES = "sales"
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"


class CategoryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=64)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_enabled: bool = True


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=64)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    is_enabled: bool | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    name: str
    sort_order: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class CategoryPublicRead(BaseModel):
    id: UUID
    name: str
    sort_order: int


class CategoryOrderItem(BaseModel):
    id: UUID
    sort_order: int = Field(ge=0, le=9999)


class CategoryOrderUpdate(BaseModel):
    items: list[CategoryOrderItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "CategoryOrderUpdate":
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("排序分类不能重复")
        return self


class ProductSkuWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: UUID | None = None
    name: str = Field(min_length=1, max_length=128)
    price_cents: int = Field(ge=0, le=100_000_000)
    lesson_count: int = Field(ge=0, le=10000)
    validity_days: int = Field(gt=0, le=36500)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_active: bool = True


class ProductImageWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    object_key: str = Field(min_length=1, max_length=1024)
    sort_order: int = Field(default=0, ge=0, le=9999)


class VideoCourseLessonWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: UUID | None = None
    lesson_number: int = Field(ge=1, le=10000)
    title: str = Field(min_length=1, max_length=128)
    object_key: str = Field(min_length=1, max_length=1024)
    duration_seconds: int | None = Field(default=None, ge=1, le=604800)
    is_active: bool = True


class VideoCourseCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: UUID
    name: str = Field(min_length=1, max_length=128)
    summary: str = Field(default="", max_length=300)
    is_active: bool = True
    lessons: list[VideoCourseLessonWrite] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_lessons(self) -> "VideoCourseCreate":
        if any(lesson.id is not None for lesson in self.lessons):
            raise ValueError("新视频课程的课时不能预设编号")
        validate_video_course_lessons(self.lessons)
        if self.is_active and not any(lesson.is_active for lesson in self.lessons):
            raise ValueError("启用的视频课程至少需要一个启用课时")
        return self


class VideoCourseUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    summary: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None
    lessons: list[VideoCourseLessonWrite] | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
    )

    @field_validator(
        "category_id",
        "name",
        "summary",
        "is_active",
        "lessons",
        mode="before",
    )
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("视频课程必填字段不能设置为 null")
        return value

    @model_validator(mode="after")
    def validate_lessons(self) -> "VideoCourseUpdate":
        if self.lessons is not None:
            validate_video_course_lessons(self.lessons)
        return self


def validate_video_course_lessons(lessons: list[VideoCourseLessonWrite]) -> None:
    lesson_ids = [lesson.id for lesson in lessons if lesson.id is not None]
    if len(lesson_ids) != len(set(lesson_ids)):
        raise ValueError("视频课时编号不能重复")
    lesson_numbers = [lesson.lesson_number for lesson in lessons]
    if len(lesson_numbers) != len(set(lesson_numbers)):
        raise ValueError("视频课时序号不能重复")
    object_keys = [lesson.object_key for lesson in lessons]
    if len(object_keys) != len(set(object_keys)):
        raise ValueError("视频课时不能包含重复视频文件")


class ProductVideoCourseBindingWrite(BaseModel):
    video_course_id: UUID
    access_mode: VideoCourseAccessMode = VideoCourseAccessMode.ALL
    lesson_ids: list[UUID] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def validate_access_mode(self) -> "ProductVideoCourseBindingWrite":
        if len(self.lesson_ids) != len(set(self.lesson_ids)):
            raise ValueError("绑定的视频课时不能重复")
        if self.access_mode == VideoCourseAccessMode.ALL and self.lesson_ids:
            raise ValueError("开放全部课时时不能指定课时")
        if self.access_mode == VideoCourseAccessMode.SELECTED and not self.lesson_ids:
            raise ValueError("按课时开放时至少选择一个课时")
        return self


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: UUID
    name: str = Field(min_length=1, max_length=128)
    summary: str = Field(default="", max_length=300)
    details: str = Field(default="", max_length=50000)
    notes: str | None = Field(default=None, max_length=5000)
    cover_object_key: str = Field(min_length=1, max_length=1024)
    sale_starts_at: datetime | None = None
    sale_ends_at: datetime | None = None
    sort_order: int = Field(default=0, ge=0, le=9999)
    skus: list[ProductSkuWrite] = Field(min_length=1, max_length=100)
    images: list[ProductImageWrite] = Field(default_factory=list, max_length=20)
    video_course_bindings: list[ProductVideoCourseBindingWrite] = Field(
        default_factory=list,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_product(self) -> "ProductCreate":
        validate_sale_window(self.sale_starts_at, self.sale_ends_at)
        if any(sku.id is not None for sku in self.skus):
            raise ValueError("新商品的 SKU 不能预设编号")
        if len({image.object_key for image in self.images}) != len(self.images):
            raise ValueError("商品图集不能包含重复图片")
        if any(sku.lesson_count == 0 for sku in self.skus):
            raise ValueError("每个课程规格都必须设置线下课时数")
        binding_ids = [
            binding.video_course_id for binding in self.video_course_bindings
        ]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("同一视频课程不能重复绑定")
        return self


class ProductUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    summary: str | None = Field(default=None, max_length=300)
    details: str | None = Field(default=None, max_length=50000)
    notes: str | None = Field(default=None, max_length=5000)
    cover_object_key: str | None = Field(default=None, min_length=1, max_length=1024)
    sale_starts_at: datetime | None = None
    sale_ends_at: datetime | None = None
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    skus: list[ProductSkuWrite] | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    images: list[ProductImageWrite] | None = Field(default=None, max_length=20)
    video_course_bindings: list[ProductVideoCourseBindingWrite] | None = Field(
        default=None,
        max_length=100,
    )

    @field_validator(
        "category_id",
        "name",
        "summary",
        "details",
        "cover_object_key",
        "sort_order",
        "skus",
        "images",
        "video_course_bindings",
        mode="before",
    )
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("商品必填字段不能设置为 null")
        return value

    @model_validator(mode="after")
    def validate_unique_resources(self) -> "ProductUpdate":
        if self.skus is not None:
            ids = [sku.id for sku in self.skus if sku.id is not None]
            if len(ids) != len(set(ids)):
                raise ValueError("SKU 编号不能重复")
            if any(sku.lesson_count == 0 for sku in self.skus):
                raise ValueError("每个课程规格都必须设置线下课时数")
        if self.images is not None:
            keys = [image.object_key for image in self.images]
            if len(keys) != len(set(keys)):
                raise ValueError("商品图集不能包含重复图片")
        if self.video_course_bindings is not None:
            ids = [binding.video_course_id for binding in self.video_course_bindings]
            if len(ids) != len(set(ids)):
                raise ValueError("同一视频课程不能重复绑定")
        return self


class ProductSkuRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    price_cents: int
    lesson_count: int
    validity_days: int
    sort_order: int
    is_active: bool


class ProductImageRead(BaseModel):
    id: UUID
    object_key: str
    image_url: str | None
    sort_order: int


class VideoCourseLessonRead(BaseModel):
    id: UUID
    lesson_number: int
    title: str
    object_key: str
    video_url: str | None
    duration_seconds: int | None
    is_active: bool


class VideoCourseRead(BaseModel):
    id: UUID
    store_id: UUID
    category_id: UUID
    category_name: str
    name: str
    summary: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    lessons: list[VideoCourseLessonRead]


class VideoCourseListResponse(BaseModel):
    items: list[VideoCourseRead]
    total: int
    page: int
    page_size: int


class ProductVideoCourseBindingRead(BaseModel):
    id: UUID
    video_course_id: UUID
    video_course_name: str
    access_mode: VideoCourseAccessMode
    lesson_ids: list[UUID]
    lesson_count: int


class ProductRead(BaseModel):
    id: UUID
    store_id: UUID
    category_id: UUID
    category_name: str
    name: str
    summary: str
    details: str
    notes: str | None
    cover_object_key: str
    cover_url: str | None
    product_type: ProductType
    status: ProductStatus
    sale_starts_at: datetime | None
    sale_ends_at: datetime | None
    sales_count: int
    sort_order: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    skus: list[ProductSkuRead]
    images: list[ProductImageRead]
    video_course_bindings: list[ProductVideoCourseBindingRead]


class ProductAdminListResponse(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int


class ProductStatusUpdate(BaseModel):
    status: ProductStatus


class ProductPublicListItem(BaseModel):
    id: UUID
    category_id: UUID
    category_name: str
    name: str
    summary: str
    cover_url: str | None
    product_type: ProductType
    video_chapter_count: int
    default_sku_id: UUID
    default_sku_name: str
    lesson_count: int
    validity_days: int
    min_price_cents: int
    max_price_cents: int
    sales_count: int
    published_at: datetime | None


class ProductPublicListResponse(BaseModel):
    items: list[ProductPublicListItem]
    total: int
    page: int
    page_size: int


class ProductVideoChapterPreview(BaseModel):
    """公开详情中的配套视频课时预览，不暴露播放地址。"""

    id: UUID
    video_course_id: UUID
    video_course_name: str
    lesson_number: int
    title: str
    duration_seconds: int | None
    sort_order: int


class ProductPublicRead(BaseModel):
    id: UUID
    category_id: UUID
    category_name: str
    name: str
    summary: str
    details: str
    notes: str | None
    cover_url: str | None
    product_type: ProductType
    sales_count: int
    sale_starts_at: datetime | None
    sale_ends_at: datetime | None
    skus: list[ProductSkuRead]
    images: list[ProductImageRead]
    video_chapters: list[ProductVideoChapterPreview]


class PurchaseValidationRequest(BaseModel):
    sku_id: UUID
    quantity: int = Field(ge=1, le=99)


class PurchaseValidationResponse(BaseModel):
    store_id: UUID
    product_id: UUID
    product_name: str
    sku_id: UUID
    sku_name: str
    quantity: int
    unit_price_cents: int
    total_price_cents: int
    validated_at: datetime
