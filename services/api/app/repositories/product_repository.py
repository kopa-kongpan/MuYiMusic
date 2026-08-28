from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import (
    Category,
    Product,
    ProductSku,
    ProductStatus,
    ProductVideoCourseBinding,
    VideoCourse,
)
from app.schemas.product import ProductSort


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_category(self, category_id: UUID) -> Category | None:
        return await self.session.get(Category, category_id)

    async def get_category_by_name(
        self,
        store_id: UUID,
        name: str,
    ) -> Category | None:
        statement = select(Category).where(
            Category.store_id == store_id,
            func.lower(Category.name) == name.lower(),
        )
        return cast(Category | None, await self.session.scalar(statement))

    async def list_categories(
        self,
        store_id: UUID,
        *,
        public_only: bool = False,
    ) -> list[Category]:
        filters = [Category.store_id == store_id]
        if public_only:
            filters.append(Category.is_enabled.is_(True))
        statement = (
            select(Category)
            .where(*filters)
            .order_by(Category.sort_order, Category.created_at, Category.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_categories_by_ids(self, ids: set[UUID]) -> list[Category]:
        if not ids:
            return []
        statement = select(Category).where(Category.id.in_(ids))
        return list((await self.session.scalars(statement)).all())

    def add_category(self, category: Category) -> None:
        self.session.add(category)

    @staticmethod
    def product_load_options() -> tuple[Any, ...]:
        return (
            selectinload(Product.category),
            selectinload(Product.skus),
            selectinload(Product.images),
            selectinload(Product.video_course_bindings)
            .selectinload(ProductVideoCourseBinding.video_course)
            .selectinload(VideoCourse.lessons),
            selectinload(Product.video_course_bindings).selectinload(
                ProductVideoCourseBinding.selected_lessons
            ),
        )

    async def get_product(self, product_id: UUID) -> Product | None:
        statement = (
            select(Product)
            .options(*self.product_load_options())
            .where(Product.id == product_id)
        )
        return cast(Product | None, await self.session.scalar(statement))

    async def list_admin_products(
        self,
        *,
        store_id: UUID,
        keyword: str | None,
        category_id: UUID | None,
        status: ProductStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        filters = [Product.store_id == store_id]
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(Product.name.ilike(pattern), Product.summary.ilike(pattern))
            )
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        if status is not None:
            filters.append(Product.status == status)
        total = int(
            await self.session.scalar(select(func.count(Product.id)).where(*filters))
            or 0
        )
        statement = (
            select(Product)
            .options(*self.product_load_options())
            .where(*filters)
            .order_by(Product.sort_order, Product.created_at.desc(), Product.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self.session.scalars(statement)).all()), total

    async def list_public_products(
        self,
        *,
        store_id: UUID,
        now: datetime,
        keyword: str | None,
        category_id: UUID | None,
        sort: ProductSort,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        filters = [
            Product.store_id == store_id,
            Product.status == ProductStatus.PUBLISHED,
            Category.is_enabled.is_(True),
            or_(Product.sale_starts_at.is_(None), Product.sale_starts_at <= now),
            or_(Product.sale_ends_at.is_(None), Product.sale_ends_at > now),
        ]
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(Product.name.ilike(pattern), Product.summary.ilike(pattern))
            )
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        active_price = (
            select(func.min(ProductSku.price_cents))
            .where(
                ProductSku.product_id == Product.id,
                ProductSku.is_active.is_(True),
            )
            .correlate(Product)
            .scalar_subquery()
        )
        order_by = {
            ProductSort.COMPREHENSIVE: (
                Product.sort_order,
                Product.sales_count.desc(),
                Product.published_at.desc(),
            ),
            ProductSort.SALES: (
                Product.sales_count.desc(),
                Product.published_at.desc(),
            ),
            ProductSort.NEWEST: (
                Product.published_at.desc(),
                Product.created_at.desc(),
            ),
            ProductSort.PRICE_ASC: (active_price.asc(), Product.sort_order),
            ProductSort.PRICE_DESC: (active_price.desc(), Product.sort_order),
        }[sort]
        base = select(Product).join(Category, Category.id == Product.category_id)
        total = int(
            await self.session.scalar(
                select(func.count(Product.id))
                .join(Category, Category.id == Product.category_id)
                .where(*filters)
            )
            or 0
        )
        statement = (
            base.options(*self.product_load_options())
            .where(*filters)
            .order_by(*order_by, Product.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self.session.scalars(statement)).all()), total

    def add_product(self, product: Product) -> None:
        self.session.add(product)

    async def get_video_course(self, video_course_id: UUID) -> VideoCourse | None:
        statement = (
            select(VideoCourse)
            .options(
                selectinload(VideoCourse.category), selectinload(VideoCourse.lessons)
            )
            .where(VideoCourse.id == video_course_id)
        )
        return cast(VideoCourse | None, await self.session.scalar(statement))

    async def list_video_courses(
        self,
        *,
        store_id: UUID,
        keyword: str | None,
        category_id: UUID | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[VideoCourse], int]:
        filters = [VideoCourse.store_id == store_id]
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(VideoCourse.name.ilike(pattern), VideoCourse.summary.ilike(pattern))
            )
        if category_id is not None:
            filters.append(VideoCourse.category_id == category_id)
        if is_active is not None:
            filters.append(VideoCourse.is_active.is_(is_active))
        total = int(
            await self.session.scalar(
                select(func.count(VideoCourse.id)).where(*filters)
            )
            or 0
        )
        statement = (
            select(VideoCourse)
            .options(
                selectinload(VideoCourse.category), selectinload(VideoCourse.lessons)
            )
            .where(*filters)
            .order_by(VideoCourse.created_at.desc(), VideoCourse.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self.session.scalars(statement)).all()), total

    async def get_video_course_by_name(
        self,
        store_id: UUID,
        name: str,
    ) -> VideoCourse | None:
        statement = select(VideoCourse).where(
            VideoCourse.store_id == store_id,
            func.lower(VideoCourse.name) == name.lower(),
        )
        return cast(VideoCourse | None, await self.session.scalar(statement))

    def add_video_course(self, video_course: VideoCourse) -> None:
        self.session.add(video_course)
