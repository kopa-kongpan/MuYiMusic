from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser
from app.models.product import (
    Category,
    Product,
    ProductImage,
    ProductSku,
    ProductStatus,
    ProductType,
    ProductVideo,
)
from app.models.store import StoreStatus
from app.providers.object_storage import ObjectStorageProvider
from app.repositories.audit_repository import AuditRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.product import (
    CategoryCreate,
    CategoryOrderUpdate,
    CategoryPublicRead,
    CategoryRead,
    CategoryUpdate,
    ProductAdminListResponse,
    ProductCreate,
    ProductImageRead,
    ProductPublicListItem,
    ProductPublicListResponse,
    ProductPublicRead,
    ProductRead,
    ProductSkuRead,
    ProductSort,
    ProductStatusUpdate,
    ProductUpdate,
    ProductVideoChapterPreview,
    ProductVideoRead,
    PurchaseValidationRequest,
    PurchaseValidationResponse,
    validate_sale_window,
)
from app.services.store_service import can_access_store


class ProductResourceNotFoundError(Exception):
    pass


class PublicProductNotFoundError(Exception):
    pass


class InvalidProductError(Exception):
    pass


class DuplicateCategoryError(Exception):
    pass


class InvalidCategoryOrderError(Exception):
    pass


def category_snapshot(category: Category) -> dict[str, Any]:
    return {
        "store_id": str(category.store_id),
        "name": category.name,
        "sort_order": category.sort_order,
        "is_enabled": category.is_enabled,
    }


def product_snapshot(product: Product) -> dict[str, Any]:
    return {
        "store_id": str(product.store_id),
        "category_id": str(product.category_id),
        "name": product.name,
        "summary": product.summary,
        "details": product.details,
        "notes": product.notes,
        "cover_object_key": product.cover_object_key,
        "status": product.status.value,
        "sale_starts_at": (
            product.sale_starts_at.isoformat() if product.sale_starts_at else None
        ),
        "sale_ends_at": (
            product.sale_ends_at.isoformat() if product.sale_ends_at else None
        ),
        "sales_count": product.sales_count,
        "sort_order": product.sort_order,
        "published_at": (
            product.published_at.isoformat() if product.published_at else None
        ),
        "skus": [
            {
                "id": str(sku.id),
                "name": sku.name,
                "price_cents": sku.price_cents,
                "lesson_count": sku.lesson_count,
                "validity_days": sku.validity_days,
                "sort_order": sku.sort_order,
                "is_active": sku.is_active,
            }
            for sku in product.skus
        ],
        "images": [
            {"object_key": image.object_key, "sort_order": image.sort_order}
            for image in product.images
        ],
    }


class ProductService:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorageProvider,
    ) -> None:
        self.session = session
        self.storage = storage
        self.repository = ProductRepository(session)
        self.store_repository = StoreRepository(session)
        self.audit_repository = AuditRepository(session)

    async def list_categories_admin(
        self,
        store_id: UUID,
        admin_user: AdminUser,
    ) -> list[CategoryRead]:
        await self._require_store_access(store_id, admin_user)
        categories = await self.repository.list_categories(store_id)
        return [CategoryRead.model_validate(category) for category in categories]

    async def list_categories_public(
        self,
        store_id: UUID,
    ) -> list[CategoryPublicRead]:
        await self._require_public_store(store_id)
        categories = await self.repository.list_categories(store_id, public_only=True)
        return [
            CategoryPublicRead(
                id=category.id,
                name=category.name,
                sort_order=category.sort_order,
            )
            for category in categories
        ]

    async def create_category(
        self,
        *,
        store_id: UUID,
        payload: CategoryCreate,
        admin_user: AdminUser,
    ) -> CategoryRead:
        await self._require_store_access(store_id, admin_user)
        if await self.repository.get_category_by_name(store_id, payload.name):
            raise DuplicateCategoryError
        category = Category(store_id=store_id, **payload.model_dump())
        try:
            self.repository.add_category(category)
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="category.create",
                resource_type="category",
                resource_id=str(category.id),
                details={"after": category_snapshot(category)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(category)
        return CategoryRead.model_validate(category)

    async def update_category(
        self,
        *,
        store_id: UUID,
        category_id: UUID,
        payload: CategoryUpdate,
        admin_user: AdminUser,
    ) -> CategoryRead:
        await self._require_store_access(store_id, admin_user)
        category = await self._require_category(store_id, category_id)
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            return CategoryRead.model_validate(category)
        if "name" in changes:
            duplicate = await self.repository.get_category_by_name(
                store_id,
                str(changes["name"]),
            )
            if duplicate is not None and duplicate.id != category.id:
                raise DuplicateCategoryError
        before = category_snapshot(category)
        for field, value in changes.items():
            setattr(category, field, value)
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="category.update",
                resource_type="category",
                resource_id=str(category.id),
                details={"before": before, "after": category_snapshot(category)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(category)
        return CategoryRead.model_validate(category)

    async def reorder_categories(
        self,
        *,
        store_id: UUID,
        payload: CategoryOrderUpdate,
        admin_user: AdminUser,
    ) -> list[CategoryRead]:
        await self._require_store_access(store_id, admin_user)
        categories = await self.repository.list_categories_by_ids(
            {item.id for item in payload.items}
        )
        if len(categories) != len(payload.items) or any(
            category.store_id != store_id for category in categories
        ):
            raise InvalidCategoryOrderError
        by_id = {category.id: category for category in categories}
        try:
            for item in payload.items:
                by_id[item.id].sort_order = item.sort_order
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="category.reorder",
                resource_type="category",
                resource_id=str(store_id),
                details={
                    "items": [item.model_dump(mode="json") for item in payload.items]
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        ordered = await self.repository.list_categories(store_id)
        return [CategoryRead.model_validate(category) for category in ordered]

    async def list_products_admin(
        self,
        *,
        store_id: UUID,
        admin_user: AdminUser,
        keyword: str | None,
        category_id: UUID | None,
        status: ProductStatus | None,
        page: int,
        page_size: int,
    ) -> ProductAdminListResponse:
        await self._require_store_access(store_id, admin_user)
        items, total = await self.repository.list_admin_products(
            store_id=store_id,
            keyword=keyword,
            category_id=category_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return ProductAdminListResponse(
            items=[self._to_admin_read(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_product_admin(
        self,
        *,
        store_id: UUID,
        product_id: UUID,
        admin_user: AdminUser,
    ) -> ProductRead:
        await self._require_store_access(store_id, admin_user)
        return self._to_admin_read(await self._require_product(store_id, product_id))

    async def create_product(
        self,
        *,
        store_id: UUID,
        payload: ProductCreate,
        admin_user: AdminUser,
    ) -> ProductRead:
        await self._require_store_access(store_id, admin_user)
        category = await self._require_category(store_id, payload.category_id)
        self._validate_media_keys(
            store_id,
            payload.cover_object_key,
            [image.object_key for image in payload.images],
            [video.object_key for video in payload.videos],
        )
        product = Product(
            store_id=store_id,
            category=category,
            name=payload.name,
            summary=payload.summary,
            details=payload.details,
            notes=payload.notes,
            cover_object_key=payload.cover_object_key,
            product_type=payload.product_type,
            sale_starts_at=payload.sale_starts_at,
            sale_ends_at=payload.sale_ends_at,
            sort_order=payload.sort_order,
            status=ProductStatus.DRAFT,
        )
        product.skus.extend(
            ProductSku(**sku.model_dump(exclude={"id"})) for sku in payload.skus
        )
        product.images.extend(
            ProductImage(**image.model_dump()) for image in payload.images
        )
        product.videos.extend(
            ProductVideo(**video.model_dump()) for video in payload.videos
        )
        try:
            self.repository.add_product(product)
            details = {"after": product_snapshot(product)}
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="product.create",
                resource_type="product",
                resource_id=str(product.id),
                details=details,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        saved = await self.repository.get_product(product.id)
        assert saved is not None
        return self._to_admin_read(saved)

    async def update_product(
        self,
        *,
        store_id: UUID,
        product_id: UUID,
        payload: ProductUpdate,
        admin_user: AdminUser,
    ) -> ProductRead:
        await self._require_store_access(store_id, admin_user)
        product = await self._require_product(store_id, product_id)
        if product.status == ProductStatus.ARCHIVED:
            raise InvalidProductError("已归档商品不能再修改")
        changes = payload.model_dump(
            exclude_unset=True,
            exclude={"skus", "images", "videos"},
        )
        category = product.category
        if payload.category_id is not None:
            category = await self._require_category(store_id, payload.category_id)
        starts_at = changes.get("sale_starts_at", product.sale_starts_at)
        ends_at = changes.get("sale_ends_at", product.sale_ends_at)
        try:
            validate_sale_window(starts_at, ends_at)
        except ValueError as error:
            raise InvalidProductError(str(error)) from error
        cover_key = str(changes.get("cover_object_key", product.cover_object_key))
        image_keys = (
            [image.object_key for image in payload.images]
            if payload.images is not None
            else [image.object_key for image in product.images]
        )
        video_keys = (
            [video.object_key for video in payload.videos]
            if payload.videos is not None
            else [video.object_key for video in product.videos]
        )
        self._validate_media_keys(store_id, cover_key, image_keys, video_keys)
        before = product_snapshot(product)
        for field, value in changes.items():
            if field == "category_id":
                product.category = category
            else:
                setattr(product, field, value)
        if payload.skus is not None:
            self._sync_skus(product, payload.skus)
        if payload.images is not None:
            product.images.clear()
            product.images.extend(
                ProductImage(**image.model_dump()) for image in payload.images
            )
        if payload.videos is not None:
            self._sync_videos(product, payload.videos)
        if product.product_type == ProductType.COURSE and any(
            video.is_active for video in product.videos
        ):
            raise InvalidProductError("线下课时课不能关联视频章节")
        if product.status == ProductStatus.PUBLISHED:
            self._validate_publishable(product)
        try:
            details = {"before": before, "after": product_snapshot(product)}
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="product.update",
                resource_type="product",
                resource_id=str(product.id),
                details=details,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        saved = await self.repository.get_product(product.id)
        assert saved is not None
        return self._to_admin_read(saved)

    async def change_status(
        self,
        *,
        store_id: UUID,
        product_id: UUID,
        payload: ProductStatusUpdate,
        admin_user: AdminUser,
    ) -> ProductRead:
        await self._require_store_access(store_id, admin_user)
        product = await self._require_product(store_id, product_id)
        allowed_transitions = {
            ProductStatus.DRAFT: {ProductStatus.PUBLISHED},
            ProductStatus.PUBLISHED: {ProductStatus.OFFLINE},
            ProductStatus.OFFLINE: {
                ProductStatus.PUBLISHED,
                ProductStatus.ARCHIVED,
            },
            ProductStatus.ARCHIVED: set(),
        }
        if payload.status not in allowed_transitions[product.status]:
            raise InvalidProductError(
                f"商品不能从 {product.status.value} 变更为 {payload.status.value}"
            )
        if payload.status == ProductStatus.PUBLISHED:
            self._validate_publishable(product)
            if product.published_at is None:
                product.published_at = datetime.now(UTC)
        before = product_snapshot(product)
        product.status = payload.status
        try:
            details = {"before": before, "after": product_snapshot(product)}
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="product.status.change",
                resource_type="product",
                resource_id=str(product.id),
                details=details,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        saved = await self.repository.get_product(product.id)
        assert saved is not None
        return self._to_admin_read(saved)

    async def list_products_public(
        self,
        *,
        store_id: UUID,
        keyword: str | None,
        category_id: UUID | None,
        sort: ProductSort,
        page: int,
        page_size: int,
    ) -> ProductPublicListResponse:
        await self._require_public_store(store_id)
        items, total = await self.repository.list_public_products(
            store_id=store_id,
            now=datetime.now(UTC),
            keyword=keyword,
            category_id=category_id,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        return ProductPublicListResponse(
            items=[self._to_public_list_item(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_product_public(
        self,
        *,
        store_id: UUID,
        product_id: UUID,
    ) -> ProductPublicRead:
        await self._require_public_store(store_id)
        product = await self.repository.get_product(product_id)
        if not self._is_public_product(product, store_id, datetime.now(UTC)):
            raise PublicProductNotFoundError
        assert product is not None
        return self._to_public_read(product)

    async def validate_purchase(
        self,
        *,
        store_id: UUID,
        product_id: UUID,
        payload: PurchaseValidationRequest,
    ) -> PurchaseValidationResponse:
        await self._require_public_store(store_id)
        now = datetime.now(UTC)
        product = await self.repository.get_product(product_id)
        if not self._is_public_product(product, store_id, now):
            raise PublicProductNotFoundError
        assert product is not None
        sku = next(
            (
                item
                for item in product.skus
                if item.id == payload.sku_id and item.is_active
            ),
            None,
        )
        if sku is None:
            raise InvalidProductError("所选课程规格已不可购买")
        return PurchaseValidationResponse(
            store_id=store_id,
            product_id=product.id,
            product_name=product.name,
            sku_id=sku.id,
            sku_name=sku.name,
            quantity=payload.quantity,
            unit_price_cents=sku.price_cents,
            total_price_cents=sku.price_cents * payload.quantity,
            validated_at=now,
        )

    async def _require_store_access(
        self,
        store_id: UUID,
        admin_user: AdminUser,
    ) -> None:
        if not can_access_store(admin_user, store_id):
            raise ProductResourceNotFoundError
        if await self.store_repository.get(store_id) is None:
            raise ProductResourceNotFoundError

    async def _require_public_store(self, store_id: UUID) -> None:
        store = await self.store_repository.get(store_id)
        if store is None or store.status != StoreStatus.ACTIVE:
            raise PublicProductNotFoundError

    async def _require_category(
        self,
        store_id: UUID,
        category_id: UUID,
    ) -> Category:
        category = await self.repository.get_category(category_id)
        if category is None or category.store_id != store_id:
            raise ProductResourceNotFoundError
        return category

    async def _require_product(
        self,
        store_id: UUID,
        product_id: UUID,
    ) -> Product:
        product = await self.repository.get_product(product_id)
        if product is None or product.store_id != store_id:
            raise ProductResourceNotFoundError
        return product

    def _validate_media_keys(
        self,
        store_id: UUID,
        cover_key: str,
        image_keys: list[str],
        video_keys: list[str],
    ) -> None:
        if not self.storage.is_product_object_key(store_id, cover_key):
            raise InvalidProductError("商品封面不属于当前门店")
        if any(
            not self.storage.is_product_object_key(store_id, key) for key in image_keys
        ):
            raise InvalidProductError("商品图集包含不属于当前门店的图片")
        if any(
            not self.storage.is_product_video_object_key(store_id, key)
            for key in video_keys
        ):
            raise InvalidProductError("视频章节包含不属于当前门店的视频文件")

    def _sync_skus(self, product: Product, payload_skus: list[Any]) -> None:
        existing = {sku.id: sku for sku in product.skus}
        submitted_ids = {sku.id for sku in payload_skus if sku.id is not None}
        if any(sku_id not in existing for sku_id in submitted_ids):
            raise InvalidProductError("SKU 不属于当前商品")
        for sku in product.skus:
            if sku.id not in submitted_ids:
                sku.is_active = False
        for item in payload_skus:
            values = item.model_dump(exclude={"id"})
            if item.id is None:
                product.skus.append(ProductSku(**values))
            else:
                target = existing[item.id]
                for field, value in values.items():
                    setattr(target, field, value)

    def _sync_videos(self, product: Product, payload_videos: list[Any]) -> None:
        existing = {video.id: video for video in product.videos}
        submitted_ids = {video.id for video in payload_videos if video.id is not None}
        if any(video_id not in existing for video_id in submitted_ids):
            raise InvalidProductError("视频章节不属于当前商品")
        for video in product.videos:
            if video.id not in submitted_ids:
                video.is_active = False
        for item in payload_videos:
            values = item.model_dump(exclude={"id"})
            if item.id is None:
                product.videos.append(ProductVideo(**values))
            else:
                target = existing[item.id]
                for field, value in values.items():
                    setattr(target, field, value)

    def _validate_publishable(self, product: Product) -> None:
        try:
            validate_sale_window(product.sale_starts_at, product.sale_ends_at)
        except ValueError as error:
            raise InvalidProductError(str(error)) from error
        if not product.category.is_enabled:
            raise InvalidProductError("启用商品分类后才能发布")
        if not any(sku.is_active for sku in product.skus):
            raise InvalidProductError("至少需要一个启用的课程规格")
        if product.product_type == ProductType.COURSE:
            if any(sku.lesson_count == 0 for sku in product.skus if sku.is_active):
                raise InvalidProductError("线下课时课的启用规格必须设置课时数")
            if any(video.is_active for video in product.videos):
                raise InvalidProductError("线下课时课不能关联视频章节")
        else:
            if any(
                sku.lesson_count != 0 for sku in product.skus if sku.is_active
            ):
                raise InvalidProductError("视频课程的启用规格课时数必须为 0")
            if not any(video.is_active for video in product.videos):
                raise InvalidProductError("视频课程至少需要一个启用的视频章节")
        self._validate_media_keys(
            product.store_id,
            product.cover_object_key,
            [image.object_key for image in product.images],
            [video.object_key for video in product.videos if video.is_active],
        )

    @staticmethod
    def _is_public_product(
        product: Product | None,
        store_id: UUID,
        now: datetime,
    ) -> bool:
        if (
            product is None
            or product.store_id != store_id
            or product.status != ProductStatus.PUBLISHED
            or not product.category.is_enabled
            or not any(sku.is_active for sku in product.skus)
        ):
            return False
        if product.sale_starts_at is not None and product.sale_starts_at > now:
            return False
        return product.sale_ends_at is None or product.sale_ends_at > now

    def _to_admin_read(self, product: Product) -> ProductRead:
        return ProductRead(
            id=product.id,
            store_id=product.store_id,
            category_id=product.category_id,
            category_name=product.category.name,
            name=product.name,
            summary=product.summary,
            details=product.details,
            notes=product.notes,
            cover_object_key=product.cover_object_key,
            cover_url=self.storage.media_url(product.cover_object_key),
            product_type=product.product_type,
            status=product.status,
            sale_starts_at=product.sale_starts_at,
            sale_ends_at=product.sale_ends_at,
            sales_count=product.sales_count,
            sort_order=product.sort_order,
            published_at=product.published_at,
            created_at=product.created_at,
            updated_at=product.updated_at,
            skus=[ProductSkuRead.model_validate(sku) for sku in product.skus],
            images=[self._to_image_read(image) for image in product.images],
            videos=[self._to_video_read(video) for video in product.videos],
        )

    def _to_public_list_item(self, product: Product) -> ProductPublicListItem:
        active_skus = [sku for sku in product.skus if sku.is_active]
        default_sku = min(
            active_skus,
            key=lambda sku: (sku.price_cents, sku.sort_order, sku.created_at, sku.id),
        )
        prices = [sku.price_cents for sku in active_skus]
        return ProductPublicListItem(
            id=product.id,
            category_id=product.category_id,
            category_name=product.category.name,
            name=product.name,
            summary=product.summary,
            cover_url=self.storage.media_url(product.cover_object_key),
            product_type=product.product_type,
            video_chapter_count=sum(1 for video in product.videos if video.is_active),
            default_sku_id=default_sku.id,
            default_sku_name=default_sku.name,
            lesson_count=default_sku.lesson_count,
            validity_days=default_sku.validity_days,
            min_price_cents=min(prices),
            max_price_cents=max(prices),
            sales_count=product.sales_count,
            published_at=product.published_at,
        )

    def _to_public_read(self, product: Product) -> ProductPublicRead:
        return ProductPublicRead(
            id=product.id,
            category_id=product.category_id,
            category_name=product.category.name,
            name=product.name,
            summary=product.summary,
            details=product.details,
            notes=product.notes,
            cover_url=self.storage.media_url(product.cover_object_key),
            product_type=product.product_type,
            sales_count=product.sales_count,
            sale_starts_at=product.sale_starts_at,
            sale_ends_at=product.sale_ends_at,
            skus=[
                ProductSkuRead.model_validate(sku)
                for sku in product.skus
                if sku.is_active
            ],
            images=[self._to_image_read(image) for image in product.images],
            video_chapters=[
                ProductVideoChapterPreview(
                    id=video.id,
                    title=video.title,
                    duration_seconds=video.duration_seconds,
                    sort_order=video.sort_order,
                )
                for video in product.videos
                if video.is_active
            ],
        )

    def _to_video_read(self, video: ProductVideo) -> ProductVideoRead:
        return ProductVideoRead(
            id=video.id,
            title=video.title,
            object_key=video.object_key,
            video_url=self.storage.presigned_get_url(video.object_key),
            duration_seconds=video.duration_seconds,
            sort_order=video.sort_order,
            is_active=video.is_active,
        )

    def _to_image_read(self, image: ProductImage) -> ProductImageRead:
        return ProductImageRead(
            id=image.id,
            object_key=image.object_key,
            image_url=self.storage.media_url(image.object_key),
            sort_order=image.sort_order,
        )
