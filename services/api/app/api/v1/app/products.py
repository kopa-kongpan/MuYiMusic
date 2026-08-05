from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.providers.object_storage import ObjectStorageProvider, get_object_storage
from app.schemas.product import (
    CategoryPublicRead,
    ProductPublicListResponse,
    ProductPublicRead,
    ProductSort,
    PurchaseValidationRequest,
    PurchaseValidationResponse,
)
from app.services.product_service import (
    InvalidProductError,
    ProductService,
    PublicProductNotFoundError,
)

router = APIRouter(prefix="/stores/{store_id}", tags=["app-products"])
StorageDependency = Annotated[ObjectStorageProvider, Depends(get_object_storage)]


@router.get("/categories", response_model=list[CategoryPublicRead])
async def list_categories(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
) -> list[CategoryPublicRead]:
    try:
        return await ProductService(session, storage).list_categories_public(store_id)
    except PublicProductNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在或已停用") from error


@router.get("/products", response_model=ProductPublicListResponse)
async def list_products(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    keyword: Annotated[str | None, Query(max_length=128)] = None,
    category_id: UUID | None = None,
    sort: ProductSort = ProductSort.COMPREHENSIVE,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductPublicListResponse:
    try:
        return await ProductService(session, storage).list_products_public(
            store_id=store_id,
            keyword=keyword,
            category_id=category_id,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    except PublicProductNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在或已停用") from error


@router.get("/products/{product_id}", response_model=ProductPublicRead)
async def get_product(
    store_id: UUID,
    product_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
) -> ProductPublicRead:
    try:
        return await ProductService(session, storage).get_product_public(
            store_id=store_id,
            product_id=product_id,
        )
    except PublicProductNotFoundError as error:
        raise HTTPException(status_code=404, detail="商品不存在或不可购买") from error


@router.post(
    "/products/{product_id}/purchase-validation",
    response_model=PurchaseValidationResponse,
)
async def validate_purchase(
    store_id: UUID,
    product_id: UUID,
    payload: PurchaseValidationRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
) -> PurchaseValidationResponse:
    try:
        return await ProductService(session, storage).validate_purchase(
            store_id=store_id,
            product_id=product_id,
            payload=payload,
        )
    except PublicProductNotFoundError as error:
        raise HTTPException(status_code=404, detail="商品不存在或不可购买") from error
    except InvalidProductError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
