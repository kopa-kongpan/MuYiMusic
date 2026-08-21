import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import get_engine, get_session
from app.core.security import hash_password
from app.main import app
from app.models.admin import AdminUser, Permission, Role
from app.models.audit import AuditLog
from app.models.product import (
    Category,
    Product,
    ProductSku,
    ProductStatus,
    ProductType,
    ProductVideo,
)
from app.models.store import Store
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
from app.providers.miniapp_identity import (
    IdentityProviderNotConfiguredError,
    MiniAppIdentityProvider,
)

pytestmark = pytest.mark.asyncio


def make_store(name: str) -> Store:
    return Store(
        name=name,
        city="深圳市",
        district="南山区",
        address="测试路 100 号",
        phone="0755-12345678",
        latitude=Decimal("22.543096"),
        longitude=Decimal("114.057865"),
    )


async def login_admin(
    client: AsyncClient,
    username: str,
    password: str,
) -> str:
    response = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


async def login_h5(
    client: AsyncClient,
    code: str,
    nickname: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/app/auth/login",
        json={"provider": "h5", "code": code, "nickname": nickname},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    return data


async def test_user_login_read_model_and_store_isolation() -> None:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_session() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_session] = override_session
        try:
            permission = await session.scalar(
                select(Permission).where(Permission.code == "users:read")
            )
            assert permission is not None
            allowed_store = make_store("用户权益测试门店")
            denied_store = make_store("未授权用户权益门店")
            reader_role = Role(code=f"user-reader-{uuid4()}", name="用户查询")
            reader_role.permissions.append(permission)
            reader = AdminUser(
                username=f"user-reader-{uuid4().hex}",
                password_hash=hash_password("test-password-2026"),
            )
            reader.roles.append(reader_role)
            reader.stores.append(allowed_store)
            readonly_admin = AdminUser(
                username=f"no-user-reader-{uuid4().hex}",
                password_hash=reader.password_hash,
            )
            readonly_admin.roles.append(
                Role(code=f"no-user-reader-{uuid4()}", name="无用户权限")
            )
            readonly_admin.stores.append(allowed_store)
            session.add_all((reader, readonly_admin, denied_store))
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                local_code = f"h5-test-device-{uuid4().hex}"
                first_login = await login_h5(client, local_code, "第一位学员")
                second_login = await login_h5(client, local_code, "更新后的学员")
                assert first_login["user"]["id"] == second_login["user"]["id"]
                assert second_login["user"]["nickname"] == "更新后的学员"
                user_token = str(second_login["access_token"])
                user_id = second_login["user"]["id"]

                account = await session.scalar(
                    select(ProviderAccount).where(
                        ProviderAccount.provider == IdentityProvider.H5,
                        ProviderAccount.user_id == user_id,
                    )
                )
                assert account is not None
                expected_subject = hashlib.sha256(local_code.encode()).hexdigest()
                assert account.provider_subject == f"local_{expected_subject}"
                assert local_code not in account.provider_subject

                user = await session.get(User, user_id)
                assert user is not None
                user.phone = "13800001234"
                other_user = User(nickname="另一位学员")

                own_order_id = uuid4()
                own_item_id = uuid4()
                own_order = Order(
                    id=own_order_id,
                    order_no=f"TEST-{uuid4().hex[:20]}",
                    user_id=user.id,
                    store_id=allowed_store.id,
                    status=OrderStatus.CONFIRMED,
                    total_amount_cents=316000,
                    items=[
                        OrderItem(
                            id=own_item_id,
                            product_name="少儿钢琴启蒙",
                            sku_name="10 课时",
                            unit_price_cents=158000,
                            quantity=2,
                            total_amount_cents=316000,
                            lesson_count=10,
                            validity_days=180,
                        )
                    ],
                )
                denied_item_id = uuid4()
                denied_order = Order(
                    order_no=f"TEST-{uuid4().hex[:20]}",
                    user_id=user.id,
                    store_id=denied_store.id,
                    status=OrderStatus.PENDING,
                    total_amount_cents=88000,
                    items=[
                        OrderItem(
                            id=denied_item_id,
                            product_name="声乐体验课",
                            sku_name="1 课时",
                            unit_price_cents=88000,
                            quantity=1,
                            total_amount_cents=88000,
                            lesson_count=1,
                            validity_days=30,
                        )
                    ],
                )
                other_item_id = uuid4()
                other_order = Order(
                    order_no=f"TEST-{uuid4().hex[:20]}",
                    user=other_user,
                    store_id=allowed_store.id,
                    status=OrderStatus.CONFIRMED,
                    total_amount_cents=128000,
                    items=[
                        OrderItem(
                            id=other_item_id,
                            product_name="吉他入门课",
                            sku_name="4 课时",
                            unit_price_cents=128000,
                            quantity=1,
                            total_amount_cents=128000,
                            lesson_count=4,
                            validity_days=60,
                        )
                    ],
                )
                now = datetime.now(UTC)
                session.add_all((own_order, denied_order, other_order))
                await session.flush()
                session.add_all(
                    (
                        CourseEntitlement(
                            user_id=user.id,
                            store_id=allowed_store.id,
                            order_item_id=own_item_id,
                            course_name="少儿钢琴启蒙",
                            total_lessons=20,
                            remaining_lessons=18,
                            valid_from=now,
                            expires_at=now + timedelta(days=180),
                            status=EntitlementStatus.ACTIVE,
                        ),
                        CourseEntitlement(
                            user_id=user.id,
                            store_id=denied_store.id,
                            order_item_id=denied_item_id,
                            course_name="声乐体验课",
                            total_lessons=1,
                            remaining_lessons=1,
                            valid_from=now,
                            expires_at=now + timedelta(days=30),
                            status=EntitlementStatus.ACTIVE,
                        ),
                        CourseEntitlement(
                            user=other_user,
                            store_id=allowed_store.id,
                            order_item_id=other_item_id,
                            course_name="吉他入门课",
                            total_lessons=4,
                            remaining_lessons=4,
                            valid_from=now,
                            expires_at=now + timedelta(days=60),
                            status=EntitlementStatus.ACTIVE,
                        ),
                    )
                )
                await session.flush()

                user_headers = {"Authorization": f"Bearer {user_token}"}
                profile_response = await client.get(
                    "/api/v1/app/me",
                    headers=user_headers,
                )
                assert profile_response.status_code == 200
                assert profile_response.json()["phone"] == "13800001234"

                own_orders = await client.get(
                    "/api/v1/app/me/orders",
                    headers=user_headers,
                )
                assert own_orders.status_code == 200
                assert own_orders.json()["total"] == 2
                assert all(
                    item["user_id"] == user_id for item in own_orders.json()["items"]
                )
                store_orders = await client.get(
                    "/api/v1/app/me/orders",
                    headers=user_headers,
                    params={"store_id": str(allowed_store.id)},
                )
                assert store_orders.json()["total"] == 1
                order_payload = store_orders.json()["items"][0]
                assert order_payload["total_amount_cents"] == 316000
                assert order_payload["items"][0]["unit_price_cents"] == 158000
                assert order_payload["items"][0]["quantity"] == 2

                entitlements = await client.get(
                    "/api/v1/app/me/course-entitlements",
                    headers=user_headers,
                    params={"store_id": str(allowed_store.id)},
                )
                assert entitlements.status_code == 200
                assert entitlements.json()["total"] == 1
                entitlement = entitlements.json()["items"][0]
                assert entitlement["course_name"] == "少儿钢琴启蒙"
                assert entitlement["total_lessons"] == 20
                assert entitlement["remaining_lessons"] == 18

                reader_token = await login_admin(
                    client,
                    reader.username,
                    "test-password-2026",
                )
                readonly_token = await login_admin(
                    client,
                    readonly_admin.username,
                    "test-password-2026",
                )
                reader_headers = {"Authorization": f"Bearer {reader_token}"}
                readonly_headers = {"Authorization": f"Bearer {readonly_token}"}

                assert (
                    await client.get("/api/v1/app/me", headers=reader_headers)
                ).status_code == 401
                assert (
                    await client.get(
                        f"/api/v1/admin/stores/{allowed_store.id}/users",
                        headers=user_headers,
                    )
                ).status_code == 401
                assert (
                    await client.get(
                        f"/api/v1/admin/stores/{allowed_store.id}/users",
                        headers=readonly_headers,
                    )
                ).status_code == 403
                assert (
                    await client.get(
                        f"/api/v1/admin/stores/{denied_store.id}/users",
                        headers=reader_headers,
                    )
                ).status_code == 404

                users_response = await client.get(
                    f"/api/v1/admin/stores/{allowed_store.id}/users",
                    headers=reader_headers,
                    params={"keyword": "1380000"},
                )
                assert users_response.status_code == 200
                assert users_response.json()["total"] == 1
                user_summary = users_response.json()["items"][0]
                assert user_summary["id"] == user_id
                assert user_summary["phone_masked"] == "138****1234"
                assert user_summary["order_count"] == 1
                assert user_summary["entitlement_count"] == 1

                admin_orders = await client.get(
                    (f"/api/v1/admin/stores/{allowed_store.id}/users/{user_id}/orders"),
                    headers=reader_headers,
                )
                assert admin_orders.status_code == 200
                assert admin_orders.json()["total"] == 1
                admin_entitlements = await client.get(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/users/"
                        f"{user_id}/course-entitlements"
                    ),
                    headers=reader_headers,
                )
                assert admin_entitlements.status_code == 200
                assert admin_entitlements.json()["total"] == 1

                last_login_at = account.last_login_at
                user.status = UserStatus.DISABLED
                await session.flush()
                assert (
                    await client.get("/api/v1/app/me", headers=user_headers)
                ).status_code == 401
                disabled_login = await client.post(
                    "/api/v1/app/auth/login",
                    json={
                        "provider": "h5",
                        "code": local_code,
                        "nickname": "不应写入的昵称",
                    },
                )
                assert disabled_login.status_code == 403
                await session.refresh(account)
                await session.refresh(user)
                assert account.last_login_at == last_login_at
                assert user.nickname == "更新后的学员"
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def test_h5_local_identity_is_rejected_outside_local_environment() -> None:
    provider = MiniAppIdentityProvider(Settings(_env_file=None, app_env="production"))
    with pytest.raises(IdentityProviderNotConfiguredError):
        await provider.exchange(
            IdentityProvider.H5,
            f"h5-production-device-{uuid4().hex}",
        )


async def test_admin_can_adjust_course_entitlement_lessons_with_audit() -> None:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_session() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_session] = override_session
        try:
            permission = await session.scalar(
                select(Permission).where(Permission.code == "consumptions:manage")
            )
            assert permission is not None
            store = make_store("课时调整测试门店")
            role = Role(code=f"lesson-manager-{uuid4()}", name="课时管理")
            role.permissions.append(permission)
            manager = AdminUser(
                username=f"lesson-manager-{uuid4().hex}",
                password_hash=hash_password("test-password-2026"),
            )
            manager.roles.append(role)
            manager.stores.append(store)
            session.add(manager)
            await session.flush()
            user = User(nickname="课时调整学员")
            now = datetime.now(UTC)
            course_entitlement = CourseEntitlement(
                user=user,
                store_id=store.id,
                course_name="钢琴进阶课",
                product_type=ProductType.COURSE,
                total_lessons=10,
                remaining_lessons=7,
                reserved_lessons=2,
                valid_from=now,
                expires_at=now + timedelta(days=180),
                status=EntitlementStatus.ACTIVE,
            )
            video_entitlement = CourseEntitlement(
                user=user,
                store_id=store.id,
                course_name="乐理视频课",
                product_type=ProductType.VIDEO,
                total_lessons=0,
                remaining_lessons=0,
                reserved_lessons=0,
                valid_from=now,
                expires_at=now + timedelta(days=180),
                status=EntitlementStatus.ACTIVE,
            )
            session.add_all((course_entitlement, video_entitlement))
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                token = await login_admin(
                    client,
                    manager.username,
                    "test-password-2026",
                )
                headers = {"Authorization": f"Bearer {token}"}
                base_url = (
                    f"/api/v1/admin/stores/{store.id}/users/{user.id}/"
                    "course-entitlements"
                )
                adjusted = await client.patch(
                    f"{base_url}/{course_entitlement.id}/lessons",
                    headers=headers,
                    json={
                        "remaining_lessons": 9,
                        "reason": "补赠两节课",
                    },
                )
                assert adjusted.status_code == 200
                payload = adjusted.json()
                assert payload["remaining_lessons"] == 9
                assert payload["total_lessons"] == 12
                assert payload["reserved_lessons"] == 2
                assert payload["status"] == "active"

                audit_log = await session.scalar(
                    select(AuditLog).where(
                        AuditLog.action == "entitlement.lessons_adjust",
                        AuditLog.resource_id == str(course_entitlement.id),
                    )
                )
                assert audit_log is not None
                assert audit_log.details["previous_remaining_lessons"] == 7
                assert audit_log.details["new_remaining_lessons"] == 9
                assert audit_log.details["reason"] == "补赠两节课"

                below_reserved = await client.patch(
                    f"{base_url}/{course_entitlement.id}/lessons",
                    headers=headers,
                    json={"remaining_lessons": 1, "reason": "错误修正"},
                )
                assert below_reserved.status_code == 409
                assert "已预约锁定" in below_reserved.json()["message"]

                video_adjustment = await client.patch(
                    f"{base_url}/{video_entitlement.id}/lessons",
                    headers=headers,
                    json={"remaining_lessons": 1, "reason": "错误修正"},
                )
                assert video_adjustment.status_code == 409
                assert "视频课程" in video_adjustment.json()["message"]
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def test_grant_video_course_entitlement_and_watch_chapters() -> None:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_session() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_session] = override_session
        try:
            manage_permission = await session.scalar(
                select(Permission).where(Permission.code == "products:manage")
            )
            assert manage_permission is not None
            read_permission = await session.scalar(
                select(Permission).where(Permission.code == "users:read")
            )
            assert read_permission is not None
            store = make_store("视频课程开通门店")
            manager_role = Role(code=f"video-manager-{uuid4()}", name="视频课程管理")
            manager_role.permissions.append(manage_permission)
            manager_role.permissions.append(read_permission)
            manager = AdminUser(
                username=f"video-manager-{uuid4().hex}",
                password_hash=hash_password("test-password-2026"),
            )
            manager.roles.append(manager_role)
            manager.stores.append(store)
            category = Category(
                store=store,
                name="视频课程",
                sort_order=0,
                is_enabled=True,
            )
            product = Product(
                store=store,
                category=category,
                name="钢琴教学视频课",
                summary="全套钢琴教学",
                details="从零开始学钢琴",
                cover_object_key=(f"muyimusic/stores/{store.id}/products/cover.jpg"),
                product_type=ProductType.VIDEO,
                status=ProductStatus.PUBLISHED,
                published_at=datetime.now(UTC),
            )
            sku = ProductSku(
                name="全期观看",
                price_cents=19900,
                lesson_count=0,
                validity_days=365,
                sort_order=10,
            )
            product.skus.append(sku)
            product.videos.extend(
                (
                    ProductVideo(
                        title="第一章 认识键盘",
                        object_key=(
                            f"muyimusic/stores/{store.id}/products/videos/chapter1.mp4"
                        ),
                        duration_seconds=720,
                        sort_order=10,
                    ),
                    ProductVideo(
                        title="第二章 基础指法",
                        object_key=(
                            f"muyimusic/stores/{store.id}/products/videos/chapter2.mp4"
                        ),
                        duration_seconds=840,
                        sort_order=20,
                    ),
                )
            )
            session.add_all((manager, category, product))
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                login = await login_h5(
                    client,
                    f"h5-video-student-{uuid4().hex}",
                    "视频课学员",
                )
                user_token = str(login["access_token"])
                user_id = login["user"]["id"]
                manager_token = await login_admin(
                    client,
                    manager.username,
                    "test-password-2026",
                )
                manager_headers = {"Authorization": f"Bearer {manager_token}"}
                user_headers = {"Authorization": f"Bearer {user_token}"}

                payload = {
                    "product_id": str(product.id),
                    "sku_id": str(sku.id),
                    "quantity": 1,
                    "idempotency_key": f"grant-{uuid4().hex}",
                }
                grant_url = (
                    f"/api/v1/admin/stores/{store.id}/users/{user_id}/entitlements"
                )
                granted = await client.post(
                    grant_url,
                    headers=manager_headers,
                    json=payload,
                )
                assert granted.status_code == 201
                order = granted.json()
                assert order["user_id"] == user_id
                assert order["status"] == "confirmed"
                assert order["items"][0]["product_type"] == "video"
                assert order["items"][0]["lesson_count"] == 0
                assert order["items"][0]["validity_days"] == 365

                # 同一幂等键重复提交返回同一订单，不重复发放
                duplicated = await client.post(
                    grant_url,
                    headers=manager_headers,
                    json=payload,
                )
                assert duplicated.status_code == 201
                assert duplicated.json()["id"] == order["id"]

                # 权益落库：视频课程课时为 0，永久活跃
                entitlement = await session.scalar(
                    select(CourseEntitlement).where(
                        CourseEntitlement.user_id == user_id,
                        CourseEntitlement.store_id == store.id,
                    )
                )
                assert entitlement is not None
                assert entitlement.product_type == ProductType.VIDEO
                assert entitlement.total_lessons == 0
                assert entitlement.remaining_lessons == 0
                assert entitlement.reserved_lessons == 0
                assert entitlement.status == EntitlementStatus.ACTIVE
                assert entitlement.expires_at is not None

                # 用户端权益返回视频章节（未配置对象存储时播放地址为 null）
                mine = await client.get(
                    "/api/v1/app/me/course-entitlements",
                    headers=user_headers,
                    params={"store_id": str(store.id)},
                )
                assert mine.status_code == 200
                assert mine.json()["total"] == 1
                my_entitlement = mine.json()["items"][0]
                assert my_entitlement["product_type"] == "video"
                assert my_entitlement["total_lessons"] == 0
                assert len(my_entitlement["video_chapters"]) == 2
                chapter = my_entitlement["video_chapters"][0]
                assert chapter["title"] == "第一章 认识键盘"
                assert chapter["duration_seconds"] == 720
                assert chapter["sort_order"] == 10
                assert chapter["video_url"] is None
                assert "object_key" not in chapter

                # 管理员端权益列表同样透传章节
                admin_view = await client.get(
                    (
                        f"/api/v1/admin/stores/{store.id}/users/"
                        f"{user_id}/course-entitlements"
                    ),
                    headers=manager_headers,
                )
                assert admin_view.status_code == 200
                assert admin_view.json()["items"][0]["product_type"] == "video"
                assert len(admin_view.json()["items"][0]["video_chapters"]) == 2

                # 无管理权限的管理员不能开通权益
                permission = await session.scalar(
                    select(Permission).where(Permission.code == "users:read")
                )
                assert permission is not None
                limited_role = Role(
                    code=f"video-viewer-{uuid4()}",
                    name="仅查看",
                )
                limited_role.permissions.append(permission)
                limited = AdminUser(
                    username=f"video-viewer-{uuid4().hex}",
                    password_hash=hash_password("test-password-2026"),
                )
                limited.roles.append(limited_role)
                limited.stores.append(store)
                session.add(limited)
                await session.flush()
                limited_token = await login_admin(
                    client,
                    limited.username,
                    "test-password-2026",
                )
                forbidden = await client.post(
                    grant_url,
                    headers={"Authorization": f"Bearer {limited_token}"},
                    json={**payload, "idempotency_key": f"grant-{uuid4().hex}"},
                )
                assert forbidden.status_code == 403
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
