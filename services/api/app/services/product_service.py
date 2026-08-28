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
    ProductVideoCourseBinding,
    VideoCourse,
    VideoCourseAccessMode,
    VideoCourseLesson,
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
    ProductVideoCourseBindingRead,
    PurchaseValidationRequest,
    PurchaseValidationResponse,
    VideoCourseCreate,
    VideoCourseLessonRead,
    VideoCourseListResponse,
    VideoCourseRead,
    VideoCourseUpdate,
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


class DuplicateVideoCourseError(Exception):
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
        "video_course_bindings": [
            {
                "video_course_id": str(binding.video_course_id),
                "access_mode": binding.access_mode.value,
                "lesson_ids": [str(lesson.id) for lesson in binding.selected_lessons],
            }
            for binding in product.video_course_bindings
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

    async def list_video_courses_admin(
        self,
        *,
        store_id: UUID,
        admin_user: AdminUser,
        keyword: str | None,
        category_id: UUID | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> VideoCourseListResponse:
        await self._require_store_access(store_id, admin_user)
        items, total = await self.repository.list_video_courses(
            store_id=store_id,
            keyword=keyword,
            category_id=category_id,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )
        return VideoCourseListResponse(
            items=[self._to_video_course_read(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_video_course_admin(
        self,
        *,
        store_id: UUID,
        video_course_id: UUID,
        admin_user: AdminUser,
    ) -> VideoCourseRead:
        await self._require_store_access(store_id, admin_user)
        return self._to_video_course_read(
            await self._require_video_course(store_id, video_course_id)
        )

    async def create_video_course(
        self,
        *,
        store_id: UUID,
        payload: VideoCourseCreate,
        admin_user: AdminUser,
    ) -> VideoCourseRead:
        await self._require_store_access(store_id, admin_user)
        category = await self._require_category(store_id, payload.category_id)
        if await self.repository.get_video_course_by_name(store_id, payload.name):
            raise DuplicateVideoCourseError
        self._validate_video_lesson_keys(
            store_id,
            [lesson.object_key for lesson in payload.lessons],
        )
        video_course = VideoCourse(
            store_id=store_id,
            category=category,
            name=payload.name,
            summary=payload.summary,
            is_active=payload.is_active,
        )
        video_course.lessons.extend(
            VideoCourseLesson(**lesson.model_dump(exclude={"id"}))
            for lesson in payload.lessons
        )
        try:
            self.repository.add_video_course(video_course)
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="video_course.create",
                resource_type="video_course",
                resource_id=str(video_course.id),
                details={"name": video_course.name},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        saved = await self.repository.get_video_course(video_course.id)
        assert saved is not None
        return self._to_video_course_read(saved)

    async def update_video_course(
        self,
        *,
        store_id: UUID,
        video_course_id: UUID,
        payload: VideoCourseUpdate,
        admin_user: AdminUser,
    ) -> VideoCourseRead:
        await self._require_store_access(store_id, admin_user)
        video_course = await self._require_video_course(store_id, video_course_id)
        changes = payload.model_dump(exclude_unset=True, exclude={"lessons"})
        if payload.category_id is not None:
            video_course.category = await self._require_category(
                store_id,
                payload.category_id,
            )
            changes.pop("category_id", None)
        if payload.name is not None:
            duplicate = await self.repository.get_video_course_by_name(
                store_id,
                payload.name,
            )
            if duplicate is not None and duplicate.id != video_course.id:
                raise DuplicateVideoCourseError
        for field, value in changes.items():
            setattr(video_course, field, value)
        if payload.lessons is not None:
            self._validate_video_lesson_keys(
                store_id,
                [lesson.object_key for lesson in payload.lessons],
            )
            self._sync_video_course_lessons(video_course, payload.lessons)
        if video_course.is_active and not any(
            lesson.is_active for lesson in video_course.lessons
        ):
            raise InvalidProductError("启用的视频课程至少需要一个启用课时")
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="video_course.update",
                resource_type="video_course",
                resource_id=str(video_course.id),
                details={"name": video_course.name},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        saved = await self.repository.get_video_course(video_course.id)
        assert saved is not None
        return self._to_video_course_read(saved)

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
        )
        bindings = await self._build_video_course_bindings(
            store_id,
            payload.video_course_bindings,
        )
        product = Product(
            store_id=store_id,
            category=category,
            name=payload.name,
            summary=payload.summary,
            details=payload.details,
            notes=payload.notes,
            cover_object_key=payload.cover_object_key,
            product_type=ProductType.COURSE,
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
        product.video_course_bindings.extend(bindings)
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
            exclude={"skus", "images", "video_course_bindings"},
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
        self._validate_media_keys(store_id, cover_key, image_keys)
        before = product_snapshot(product)
        try:
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
            if payload.video_course_bindings is not None:
                product.video_course_bindings.clear()
                await self.session.flush()
                bindings = await self._build_video_course_bindings(
                    store_id,
                    payload.video_course_bindings,
                )
                product.video_course_bindings.extend(bindings)
            product.product_type = ProductType.COURSE
            if product.status == ProductStatus.PUBLISHED:
                self._validate_publishable(product)
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

    async def _require_video_course(
        self,
        store_id: UUID,
        video_course_id: UUID,
    ) -> VideoCourse:
        video_course = await self.repository.get_video_course(video_course_id)
        if video_course is None or video_course.store_id != store_id:
            raise ProductResourceNotFoundError
        return video_course

    def _validate_media_keys(
        self,
        store_id: UUID,
        cover_key: str,
        image_keys: list[str],
    ) -> None:
        if not self.storage.is_product_object_key(store_id, cover_key):
            raise InvalidProductError("商品封面不属于当前门店")
        if any(
            not self.storage.is_product_object_key(store_id, key) for key in image_keys
        ):
            raise InvalidProductError("商品图集包含不属于当前门店的图片")

    def _validate_video_lesson_keys(
        self,
        store_id: UUID,
        video_keys: list[str],
    ) -> None:
        if any(
            not self.storage.is_product_video_object_key(store_id, key)
            for key in video_keys
        ):
            raise InvalidProductError("视频课时包含不属于当前门店的视频文件")

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

    def _sync_video_course_lessons(
        self,
        video_course: VideoCourse,
        payload_lessons: list[Any],
    ) -> None:
        existing = {lesson.id: lesson for lesson in video_course.lessons}
        submitted_ids = {
            lesson.id for lesson in payload_lessons if lesson.id is not None
        }
        if any(lesson_id not in existing for lesson_id in submitted_ids):
            raise InvalidProductError("视频课时不属于当前视频课程")
        for lesson in video_course.lessons:
            if lesson.id not in submitted_ids:
                lesson.is_active = False
        for item in payload_lessons:
            values = item.model_dump(exclude={"id"})
            if item.id is None:
                video_course.lessons.append(VideoCourseLesson(**values))
            else:
                target = existing[item.id]
                for field, value in values.items():
                    setattr(target, field, value)

    async def _build_video_course_bindings(
        self,
        store_id: UUID,
        payload_bindings: list[Any],
    ) -> list[ProductVideoCourseBinding]:
        resolved = [
            (item, await self._require_video_course(store_id, item.video_course_id))
            for item in payload_bindings
        ]
        bindings: list[ProductVideoCourseBinding] = []
        for item, video_course in resolved:
            if not video_course.is_active:
                raise InvalidProductError("只能绑定已启用的视频课程")
            lessons: list[VideoCourseLesson] = []
            if item.access_mode == VideoCourseAccessMode.SELECTED:
                lessons = [
                    lesson
                    for lesson in video_course.lessons
                    if lesson.id in set(item.lesson_ids) and lesson.is_active
                ]
                if len(lessons) != len(item.lesson_ids):
                    raise InvalidProductError("所选视频课时无效或不属于该视频课程")
            binding = ProductVideoCourseBinding(
                video_course=video_course,
                access_mode=item.access_mode,
            )
            if lessons:
                binding.selected_lessons.extend(lessons)
            bindings.append(binding)
        return bindings

    def _validate_publishable(self, product: Product) -> None:
        try:
            validate_sale_window(product.sale_starts_at, product.sale_ends_at)
        except ValueError as error:
            raise InvalidProductError(str(error)) from error
        if not product.category.is_enabled:
            raise InvalidProductError("启用商品分类后才能发布")
        if not any(sku.is_active for sku in product.skus):
            raise InvalidProductError("至少需要一个启用的课程规格")
        if any(sku.lesson_count == 0 for sku in product.skus if sku.is_active):
            raise InvalidProductError("启用的课程规格必须设置线下课时数")
        self._validate_media_keys(
            product.store_id,
            product.cover_object_key,
            [image.object_key for image in product.images],
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
            video_course_bindings=[
                self._to_binding_read(binding)
                for binding in product.video_course_bindings
            ],
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
            video_chapter_count=len(self._bound_video_lessons(product)),
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
            video_chapters=self._public_video_previews(product),
        )

    def _to_video_course_read(self, video_course: VideoCourse) -> VideoCourseRead:
        return VideoCourseRead(
            id=video_course.id,
            store_id=video_course.store_id,
            category_id=video_course.category_id,
            category_name=video_course.category.name,
            name=video_course.name,
            summary=video_course.summary,
            is_active=video_course.is_active,
            created_at=video_course.created_at,
            updated_at=video_course.updated_at,
            lessons=[
                VideoCourseLessonRead(
                    id=lesson.id,
                    lesson_number=lesson.lesson_number,
                    title=lesson.title,
                    object_key=lesson.object_key,
                    video_url=self.storage.presigned_get_url(lesson.object_key),
                    duration_seconds=lesson.duration_seconds,
                    is_active=lesson.is_active,
                )
                for lesson in video_course.lessons
            ],
        )

    @staticmethod
    def _binding_lessons(
        binding: ProductVideoCourseBinding,
    ) -> list[VideoCourseLesson]:
        if not binding.video_course.is_active:
            return []
        candidates = (
            binding.video_course.lessons
            if binding.access_mode == VideoCourseAccessMode.ALL
            else binding.selected_lessons
        )
        return [lesson for lesson in candidates if lesson.is_active]

    def _bound_video_lessons(
        self,
        product: Product,
    ) -> list[tuple[ProductVideoCourseBinding, VideoCourseLesson]]:
        return [
            (binding, lesson)
            for binding in product.video_course_bindings
            for lesson in self._binding_lessons(binding)
        ]

    def _public_video_previews(
        self,
        product: Product,
    ) -> list[ProductVideoChapterPreview]:
        return [
            ProductVideoChapterPreview(
                id=lesson.id,
                video_course_id=binding.video_course_id,
                video_course_name=binding.video_course.name,
                lesson_number=lesson.lesson_number,
                title=lesson.title,
                duration_seconds=lesson.duration_seconds,
                sort_order=lesson.lesson_number,
            )
            for binding, lesson in self._bound_video_lessons(product)
        ]

    def _to_binding_read(
        self,
        binding: ProductVideoCourseBinding,
    ) -> ProductVideoCourseBindingRead:
        lessons = self._binding_lessons(binding)
        return ProductVideoCourseBindingRead(
            id=binding.id,
            video_course_id=binding.video_course_id,
            video_course_name=binding.video_course.name,
            access_mode=binding.access_mode,
            lesson_ids=[lesson.id for lesson in binding.selected_lessons],
            lesson_count=len(lessons),
        )

    def _to_image_read(self, image: ProductImage) -> ProductImageRead:
        return ProductImageRead(
            id=image.id,
            object_key=image.object_key,
            image_url=self.storage.media_url(image.object_key),
            sort_order=image.sort_order,
        )
