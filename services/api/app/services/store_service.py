import math
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser
from app.models.store import Store, StoreStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.store import (
    StoreAdminListResponse,
    StoreCreate,
    StorePublicListResponse,
    StorePublicRead,
    StoreRead,
    StoreUpdate,
)
from app.services.auth_service import has_platform_scope


class StoreNotFoundError(Exception):
    pass


def authorized_store_ids(admin_user: AdminUser) -> set[UUID] | None:
    if has_platform_scope(admin_user):
        return None
    return {store.id for store in admin_user.stores}


def can_access_store(admin_user: AdminUser, store_id: UUID) -> bool:
    allowed_store_ids = authorized_store_ids(admin_user)
    return allowed_store_ids is None or store_id in allowed_store_ids


def distance_km(
    latitude: float,
    longitude: float,
    store_latitude: float,
    store_longitude: float,
) -> float:
    earth_radius_km = 6371.0088
    latitude_delta = math.radians(store_latitude - latitude)
    longitude_delta = math.radians(store_longitude - longitude)
    start_latitude = math.radians(latitude)
    end_latitude = math.radians(store_latitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(start_latitude)
        * math.cos(end_latitude)
        * math.sin(longitude_delta / 2) ** 2
    )
    return round(
        earth_radius_km
        * 2
        * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine)),
        2,
    )


def store_snapshot(store: Store) -> dict[str, Any]:
    return {
        "name": store.name,
        "city": store.city,
        "district": store.district,
        "address": store.address,
        "phone": store.phone,
        "latitude": float(store.latitude),
        "longitude": float(store.longitude),
        "status": store.status.value,
        "sort_order": store.sort_order,
    }


class StoreService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = StoreRepository(session)
        self.audit_repository = AuditRepository(session)

    async def list_admin(
        self,
        *,
        admin_user: AdminUser,
        keyword: str | None,
        status: StoreStatus | None,
        page: int,
        page_size: int,
    ) -> StoreAdminListResponse:
        stores, total = await self.repository.list_admin(
            keyword=keyword,
            status=status,
            page=page,
            page_size=page_size,
            allowed_store_ids=authorized_store_ids(admin_user),
        )
        return StoreAdminListResponse(
            items=[StoreRead.model_validate(store) for store in stores],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_public(
        self,
        *,
        keyword: str | None,
        latitude: float | None,
        longitude: float | None,
    ) -> StorePublicListResponse:
        stores = await self.repository.list_public(keyword)
        items = []
        for store in stores:
            item = StorePublicRead.model_validate(store)
            if latitude is not None and longitude is not None:
                item.distance_km = distance_km(
                    latitude,
                    longitude,
                    float(store.latitude),
                    float(store.longitude),
                )
            items.append(item)
        if latitude is not None and longitude is not None:
            items.sort(
                key=lambda item: (
                    item.distance_km if item.distance_km is not None else float("inf")
                )
            )
        return StorePublicListResponse(items=items)

    async def create(
        self,
        payload: StoreCreate,
        admin_user: AdminUser,
    ) -> StoreRead:
        store = Store(
            name=payload.name,
            city=payload.city,
            district=payload.district,
            address=payload.address,
            phone=payload.phone,
            latitude=Decimal(str(payload.latitude)),
            longitude=Decimal(str(payload.longitude)),
            status=payload.status,
            sort_order=payload.sort_order,
        )
        if not has_platform_scope(admin_user):
            store.authorized_admins.append(admin_user)
        try:
            self.repository.add(store)
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="store.create",
                resource_type="store",
                resource_id=str(store.id),
                details={"after": store_snapshot(store)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(store)
        return StoreRead.model_validate(store)

    async def update(
        self,
        store_id: UUID,
        payload: StoreUpdate,
        admin_user: AdminUser,
    ) -> StoreRead:
        if not can_access_store(admin_user, store_id):
            raise StoreNotFoundError
        store = await self.repository.get(store_id)
        if store is None:
            raise StoreNotFoundError
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            return StoreRead.model_validate(store)
        before = store_snapshot(store)
        for field, value in changes.items():
            if field in {"latitude", "longitude"}:
                value = Decimal(str(value))
            setattr(store, field, value)
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="store.update",
                resource_type="store",
                resource_id=str(store.id),
                details={
                    "before": before,
                    "after": store_snapshot(store),
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(store)
        return StoreRead.model_validate(store)
