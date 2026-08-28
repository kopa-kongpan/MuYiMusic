from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_permission
from app.core.database import get_session
from app.models.admin import AdminUser
from app.models.product import ProductStatus
from app.providers.object_storage import ObjectStorageProvider, get_object_storage
from app.schemas.product import (
    CategoryCreate,
    CategoryOrderUpdate,
    CategoryRead,
    CategoryUpdate,
    ProductAdminListResponse,
    ProductCreate,
    ProductRead,
    ProductStatusUpdate,
    ProductUpdate,
    VideoCourseCreate,
    VideoCourseListResponse,
    VideoCourseRead,
    VideoCourseUpdate,
)
from app.services.product_service import (
    DuplicateCategoryError,
    DuplicateVideoCourseError,
    InvalidCategoryOrderError,
    InvalidProductError,
    ProductResourceNotFoundError,
    ProductService,
)

router = APIRouter(prefix="/stores/{store_id}", tags=["admin-products"])
ProductManager = Annotated[
    AdminUser,
    Depends(require_permission("products:manage")),
]
StorageDependency = Annotated[ObjectStorageProvider, Depends(get_object_storage)]


@router.get("/categories", response_model=list[CategoryRead])
async def list_categories(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> list[CategoryRead]:
    try:
        return await ProductService(session, storage).list_categories_admin(
            store_id,
            current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    store_id: UUID,
    payload: CategoryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> CategoryRead:
    try:
        return await ProductService(session, storage).create_category(
            store_id=store_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error
    except DuplicateCategoryError as error:
        raise HTTPException(status_code=409, detail="分类名称已存在") from error


@router.put("/categories/order", response_model=list[CategoryRead])
async def reorder_categories(
    store_id: UUID,
    payload: CategoryOrderUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> list[CategoryRead]:
    try:
        return await ProductService(session, storage).reorder_categories(
            store_id=store_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error
    except InvalidCategoryOrderError as error:
        raise HTTPException(status_code=409, detail="排序分类不属于当前门店") from error


@router.patch("/categories/{category_id}", response_model=CategoryRead)
async def update_category(
    store_id: UUID,
    category_id: UUID,
    payload: CategoryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> CategoryRead:
    try:
        return await ProductService(session, storage).update_category(
            store_id=store_id,
            category_id=category_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="分类不存在") from error
    except DuplicateCategoryError as error:
        raise HTTPException(status_code=409, detail="分类名称已存在") from error


@router.get("/video-courses", response_model=VideoCourseListResponse)
async def list_video_courses(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
    keyword: Annotated[str | None, Query(max_length=128)] = None,
    category_id: UUID | None = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> VideoCourseListResponse:
    try:
        return await ProductService(session, storage).list_video_courses_admin(
            store_id=store_id,
            admin_user=current_admin,
            keyword=keyword,
            category_id=category_id,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error


@router.post(
    "/video-courses",
    response_model=VideoCourseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_video_course(
    store_id: UUID,
    payload: VideoCourseCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> VideoCourseRead:
    try:
        return await ProductService(session, storage).create_video_course(
            store_id=store_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店或分类不存在") from error
    except DuplicateVideoCourseError as error:
        raise HTTPException(status_code=409, detail="视频课程名称已存在") from error
    except InvalidProductError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/video-courses/{video_course_id}", response_model=VideoCourseRead)
async def get_video_course(
    store_id: UUID,
    video_course_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> VideoCourseRead:
    try:
        return await ProductService(session, storage).get_video_course_admin(
            store_id=store_id,
            video_course_id=video_course_id,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="视频课程不存在") from error


@router.patch("/video-courses/{video_course_id}", response_model=VideoCourseRead)
async def update_video_course(
    store_id: UUID,
    video_course_id: UUID,
    payload: VideoCourseUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> VideoCourseRead:
    try:
        return await ProductService(session, storage).update_video_course(
            store_id=store_id,
            video_course_id=video_course_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="视频课程或分类不存在") from error
    except DuplicateVideoCourseError as error:
        raise HTTPException(status_code=409, detail="视频课程名称已存在") from error
    except InvalidProductError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/products", response_model=ProductAdminListResponse)
async def list_products(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
    keyword: Annotated[str | None, Query(max_length=128)] = None,
    category_id: UUID | None = None,
    product_status: Annotated[ProductStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductAdminListResponse:
    try:
        return await ProductService(session, storage).list_products_admin(
            store_id=store_id,
            admin_user=current_admin,
            keyword=keyword,
            category_id=category_id,
            status=product_status,
            page=page,
            page_size=page_size,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error


@router.post(
    "/products",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    store_id: UUID,
    payload: ProductCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> ProductRead:
    try:
        return await ProductService(session, storage).create_product(
            store_id=store_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店或分类不存在") from error
    except InvalidProductError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/products/{product_id}", response_model=ProductRead)
async def get_product(
    store_id: UUID,
    product_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> ProductRead:
    try:
        return await ProductService(session, storage).get_product_admin(
            store_id=store_id,
            product_id=product_id,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="商品不存在") from error


@router.patch("/products/{product_id}", response_model=ProductRead)
async def update_product(
    store_id: UUID,
    product_id: UUID,
    payload: ProductUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> ProductRead:
    try:
        return await ProductService(session, storage).update_product(
            store_id=store_id,
            product_id=product_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="商品或分类不存在") from error
    except InvalidProductError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/products/{product_id}/status", response_model=ProductRead)
async def change_product_status(
    store_id: UUID,
    product_id: UUID,
    payload: ProductStatusUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ProductManager,
) -> ProductRead:
    try:
        return await ProductService(session, storage).change_status(
            store_id=store_id,
            product_id=product_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ProductResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="商品不存在") from error
    except InvalidProductError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
