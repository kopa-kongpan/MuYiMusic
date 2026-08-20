from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_access_token
from app.models.admin import AdminUser
from app.models.product import ProductStatus
from app.models.user import (
    CourseEntitlement,
    EntitlementStatus,
    IdentityProvider,
    Order,
    OrderItem,
    OrderStatus,
    ProviderAccount,
    User,
    UserStatus,
)
from app.providers.miniapp_identity import MiniAppIdentityProvider
from app.providers.object_storage import ObjectStorageProvider
from app.repositories.product_repository import ProductRepository
from app.repositories.store_repository import StoreRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    CourseEntitlementListResponse,
    CourseEntitlementRead,
    EntitlementGrantRequest,
    EntitlementVideoChapterRead,
    OrderItemRead,
    OrderListResponse,
    OrderRead,
    UserAdminListResponse,
    UserAdminRead,
    UserLoginRequest,
    UserProfile,
    UserProfileUpdate,
    UserTokenResponse,
)
from app.services.store_service import can_access_store


class UserDisabledError(Exception):
    pass


class UserResourceNotFoundError(Exception):
    pass


def user_profile(user: User) -> UserProfile:
    return UserProfile(
        id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        phone=user.phone,
        status=user.status,
    )


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    if len(phone) < 7:
        return "*" * len(phone)
    return f"{phone[:3]}****{phone[-4:]}"


class UserService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        identity_provider: MiniAppIdentityProvider,
        storage: ObjectStorageProvider | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.identity_provider = identity_provider
        self.storage = storage
        self.repository = UserRepository(session)
        self.store_repository = StoreRepository(session)
        self.product_repository = ProductRepository(session)

    async def login(self, payload: UserLoginRequest) -> UserTokenResponse:
        identity = await self.identity_provider.exchange(payload.provider, payload.code)
        account = await self.repository.get_account(
            payload.provider,
            identity.subject,
        )
        if account is None:
            defaults = {
                IdentityProvider.WEAPP: "微信用户",
                IdentityProvider.TT: "抖音用户",
                IdentityProvider.H5: "本地用户",
            }
            user = User(
                nickname=payload.nickname or defaults[payload.provider],
                avatar_url=payload.avatar_url,
            )
            account = ProviderAccount(
                provider=payload.provider,
                provider_subject=identity.subject,
                union_subject=identity.union_subject,
                last_login_at=datetime.now(UTC),
            )
            user.provider_accounts.append(account)
            self.repository.add_user(user)
        else:
            user = account.user
            if user.status != UserStatus.ACTIVE:
                raise UserDisabledError
            account.last_login_at = datetime.now(UTC)
            if identity.union_subject:
                account.union_subject = identity.union_subject
            if payload.nickname:
                user.nickname = payload.nickname
            if payload.avatar_url:
                user.avatar_url = payload.avatar_url
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        secret = self.settings.jwt_secret
        if secret is None:
            raise RuntimeError("JWT_SECRET is required")
        expires_in = self.settings.user_access_token_minutes * 60
        return UserTokenResponse(
            access_token=create_access_token(
                user.id,
                secret,
                self.settings.user_access_token_minutes,
                subject_type="user",
            ),
            expires_in=expires_in,
            user=user_profile(user),
        )

    async def update_profile(
        self,
        user: User,
        payload: UserProfileUpdate,
    ) -> UserProfile:
        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(user, field, value)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(user)
        return user_profile(user)

    async def list_orders(
        self,
        *,
        user_id: UUID,
        store_id: UUID | None,
        status: OrderStatus | None,
        page: int,
        page_size: int,
    ) -> OrderListResponse:
        rows, total = await self.repository.list_orders(
            user_id=user_id,
            store_id=store_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return OrderListResponse(
            items=[
                self._to_order_read(order, store_name) for order, store_name in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_entitlements(
        self,
        *,
        user_id: UUID,
        store_id: UUID | None,
        status: EntitlementStatus | None,
        page: int,
        page_size: int,
    ) -> CourseEntitlementListResponse:
        rows, total = await self.repository.list_entitlements(
            user_id=user_id,
            store_id=store_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return CourseEntitlementListResponse(
            items=[
                self._to_entitlement_read(entitlement, store_name)
                for entitlement, store_name in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def grant_entitlement(
        self,
        *,
        store_id: UUID,
        user_id: UUID,
        payload: EntitlementGrantRequest,
        admin_user: AdminUser,
    ) -> OrderRead:
        """线下成交后录入订单并开通课程权益。

        同一用户 + 同一幂等键重复提交时直接返回已有订单，不重复发权益。
        """
        await self._require_store_access(store_id, admin_user)
        if await self.repository.get_user(user_id) is None:
            raise UserResourceNotFoundError
        existing = await self.repository.get_order_by_create_key(
            user_id,
            payload.idempotency_key,
        )
        if existing is not None:
            store = await self.store_repository.get(store_id)
            store_name = store.name if store is not None else ""
            return self._to_order_read(existing, store_name)
        product = await self.product_repository.get_product(payload.product_id)
        if (
            product is None
            or product.store_id != store_id
            or product.status == ProductStatus.ARCHIVED
        ):
            raise UserResourceNotFoundError
        sku = next(
            (
                item
                for item in product.skus
                if item.id == payload.sku_id and item.is_active
            ),
            None,
        )
        if sku is None:
            raise UserResourceNotFoundError
        now = datetime.now(UTC)
        order = Order(
            order_no=self._order_no(now),
            user_id=user_id,
            store_id=store_id,
            status=OrderStatus.CONFIRMED,
            total_amount_cents=sku.price_cents * payload.quantity,
            create_idempotency_key=payload.idempotency_key,
        )
        item = OrderItem(
            product_id=product.id,
            product_sku_id=sku.id,
            product_name=product.name,
            sku_name=sku.name,
            unit_price_cents=sku.price_cents,
            quantity=payload.quantity,
            total_amount_cents=sku.price_cents * payload.quantity,
            lesson_count=sku.lesson_count,
            validity_days=sku.validity_days,
            product_type=product.product_type,
        )
        order.items.append(item)
        expires_at = (
            now + timedelta(days=sku.validity_days) if sku.validity_days else None
        )
        entitlement = CourseEntitlement(
            user_id=user_id,
            store_id=store_id,
            order_item_id=item.id,
            product_id=product.id,
            product_sku_id=sku.id,
            course_name=product.name,
            product_type=product.product_type,
            total_lessons=sku.lesson_count,
            remaining_lessons=sku.lesson_count,
            reserved_lessons=0,
            valid_from=now,
            expires_at=expires_at,
            status=EntitlementStatus.ACTIVE,
        )
        try:
            self.session.add_all([order, entitlement])
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.repository.get_order_by_create_key(
                user_id,
                payload.idempotency_key,
            )
            if existing is None:
                raise
            store = await self.store_repository.get(store_id)
            store_name = store.name if store is not None else ""
            return self._to_order_read(existing, store_name)
        store = await self.store_repository.get(store_id)
        store_name = store.name if store is not None else ""
        return self._to_order_read(order, store_name)

    @staticmethod
    def _order_no(now: datetime) -> str:
        return f"O{now:%Y%m%d%H%M%S}{uuid4().hex[:12].upper()}"

    async def list_users_admin(
        self,
        *,
        store_id: UUID,
        admin_user: AdminUser,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> UserAdminListResponse:
        await self._require_store_access(store_id, admin_user)
        users, total = await self.repository.list_users_for_store(
            store_id=store_id,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        order_counts, entitlement_counts = await self.repository.user_store_counts(
            [user.id for user in users],
            store_id,
        )
        return UserAdminListResponse(
            items=[
                UserAdminRead(
                    id=user.id,
                    nickname=user.nickname,
                    avatar_url=user.avatar_url,
                    phone_masked=mask_phone(user.phone),
                    status=user.status,
                    provider_names=[
                        account.provider for account in user.provider_accounts
                    ],
                    order_count=order_counts.get(user.id, 0),
                    entitlement_count=entitlement_counts.get(user.id, 0),
                    created_at=user.created_at,
                )
                for user in users
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_user_orders_admin(
        self,
        *,
        store_id: UUID,
        user_id: UUID,
        admin_user: AdminUser,
        status: OrderStatus | None,
        page: int,
        page_size: int,
    ) -> OrderListResponse:
        await self._require_store_access(store_id, admin_user)
        return await self.list_orders(
            user_id=user_id,
            store_id=store_id,
            status=status,
            page=page,
            page_size=page_size,
        )

    async def list_user_entitlements_admin(
        self,
        *,
        store_id: UUID,
        user_id: UUID,
        admin_user: AdminUser,
        status: EntitlementStatus | None,
        page: int,
        page_size: int,
    ) -> CourseEntitlementListResponse:
        await self._require_store_access(store_id, admin_user)
        return await self.list_entitlements(
            user_id=user_id,
            store_id=store_id,
            status=status,
            page=page,
            page_size=page_size,
        )

    async def _require_store_access(
        self,
        store_id: UUID,
        admin_user: AdminUser,
    ) -> None:
        if not can_access_store(admin_user, store_id):
            raise UserResourceNotFoundError
        if await self.store_repository.get(store_id) is None:
            raise UserResourceNotFoundError

    @staticmethod
    def _to_order_read(order: Order, store_name: str) -> OrderRead:
        return OrderRead(
            id=order.id,
            order_no=order.order_no,
            user_id=order.user_id,
            store_id=order.store_id,
            store_name=store_name,
            status=order.status,
            total_amount_cents=order.total_amount_cents,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[
                OrderItemRead(
                    id=item.id,
                    product_id=item.product_id,
                    product_sku_id=item.product_sku_id,
                    product_name=item.product_name,
                    sku_name=item.sku_name,
                    unit_price_cents=item.unit_price_cents,
                    quantity=item.quantity,
                    total_amount_cents=item.total_amount_cents,
                    lesson_count=item.lesson_count,
                    validity_days=item.validity_days,
                    product_type=item.product_type,
                )
                for item in order.items
            ],
        )

    def _to_entitlement_read(
        self,
        entitlement: CourseEntitlement,
        store_name: str,
    ) -> CourseEntitlementRead:
        product = entitlement.product
        video_chapters = []
        if product is not None:
            for video in product.videos:
                if not video.is_active:
                    continue
                video_chapters.append(
                    EntitlementVideoChapterRead(
                        id=video.id,
                        title=video.title,
                        duration_seconds=video.duration_seconds,
                        sort_order=video.sort_order,
                        video_url=(
                            self.storage.presigned_get_url(video.object_key)
                            if self.storage is not None
                            else None
                        ),
                    )
                )
        return CourseEntitlementRead(
            id=entitlement.id,
            user_id=entitlement.user_id,
            store_id=entitlement.store_id,
            store_name=store_name,
            order_item_id=entitlement.order_item_id,
            product_id=entitlement.product_id,
            product_sku_id=entitlement.product_sku_id,
            course_name=entitlement.course_name,
            product_type=entitlement.product_type,
            total_lessons=entitlement.total_lessons,
            remaining_lessons=entitlement.remaining_lessons,
            reserved_lessons=entitlement.reserved_lessons,
            available_lessons=(
                entitlement.remaining_lessons - entitlement.reserved_lessons
            ),
            valid_from=entitlement.valid_from,
            expires_at=entitlement.expires_at,
            status=entitlement.status,
            created_at=entitlement.created_at,
            video_chapters=video_chapters,
        )
