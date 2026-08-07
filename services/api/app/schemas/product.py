from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.product import ProductStatus, ProductType


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


class ProductVideoWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: UUID | None = None
    title: str = Field(min_length=1, max_length=128)
    object_key: str = Field(min_length=1, max_length=1024)
    duration_seconds: int | None = Field(default=None, ge=1, le=604800)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_active: bool = True


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: UUID
    name: str = Field(min_length=1, max_length=128)
    summary: str = Field(default="", max_length=300)
    details: str = Field(default="", max_length=50000)
    notes: str | None = Field(default=None, max_length=5000)
    cover_object_key: str = Field(min_length=1, max_length=1024)
    product_type: ProductType = ProductType.COURSE
    sale_starts_at: datetime | None = None
    sale_ends_at: datetime | None = None
    sort_order: int = Field(default=0, ge=0, le=9999)
    skus: list[ProductSkuWrite] = Field(min_length=1, max_length=100)
    images: list[ProductImageWrite] = Field(default_factory=list, max_length=20)
    videos: list[ProductVideoWrite] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_product(self) -> "ProductCreate":
        validate_sale_window(self.sale_starts_at, self.sale_ends_at)
        if any(sku.id is not None for sku in self.skus):
            raise ValueError("新商品的 SKU 不能预设编号")
        if len({image.object_key for image in self.images}) != len(self.images):
            raise ValueError("商品图集不能包含重复图片")
        self.validate_product_type()
        return self

    def validate_product_type(self) -> None:
        if self.product_type == ProductType.COURSE:
            if any(sku.lesson_count == 0 for sku in self.skus):
                raise ValueError("线下课时课的每个 SKU 必须设置课时数")
            if self.videos:
                raise ValueError("线下课时课不能关联视频章节")
        elif any(sku.lesson_count != 0 for sku in self.skus):
            raise ValueError("视频课程的所有 SKU 课时数必须为 0")
        keys = [video.object_key for video in self.videos]
        if len(keys) != len(set(keys)):
            raise ValueError("视频章节不能包含重复视频文件")


class ProductUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    summary: str | None = Field(default=None, max_length=300)
    details: str | None = Field(default=None, max_length=50000)
    notes: str | None = Field(default=None, max_length=5000)
    cover_object_key: str | None = Field(default=None, min_length=1, max_length=1024)
    product_type: ProductType | None = None
    sale_starts_at: datetime | None = None
    sale_ends_at: datetime | None = None
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    skus: list[ProductSkuWrite] | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    images: list[ProductImageWrite] | None = Field(default=None, max_length=20)
    videos: list[ProductVideoWrite] | None = Field(default=None, max_length=100)

    @field_validator(
        "category_id",
        "name",
        "summary",
        "details",
        "cover_object_key",
        "product_type",
        "sort_order",
        "skus",
        "images",
        "videos",
        mode="before",
    )
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("商品必填字段不能设置为 null")
        return value

    @model_validator(mode="after")
    def validate_unique_resources(self) -> "ProductUpdate":
        if self.product_type == ProductType.COURSE and self.videos:
            raise ValueError("线下课时课不能关联视频章节")
        if self.skus is not None:
            ids = [sku.id for sku in self.skus if sku.id is not None]
            if len(ids) != len(set(ids)):
                raise ValueError("SKU 编号不能重复")
        if self.images is not None:
            keys = [image.object_key for image in self.images]
            if len(keys) != len(set(keys)):
                raise ValueError("商品图集不能包含重复图片")
        if self.videos is not None:
            ids = [video.id for video in self.videos if video.id is not None]
            if len(ids) != len(set(ids)):
                raise ValueError("视频章节编号不能重复")
            keys = [video.object_key for video in self.videos]
            if len(keys) != len(set(keys)):
                raise ValueError("视频章节不能包含重复视频文件")
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


class ProductVideoRead(BaseModel):
    id: UUID
    title: str
    object_key: str
    video_url: str | None
    duration_seconds: int | None
    sort_order: int
    is_active: bool


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
    videos: list[ProductVideoRead]


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
    """公开详情中的视频章节预览：只暴露元信息，不暴露播放地址。"""

    id: UUID
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
