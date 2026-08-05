import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/app/auth/login",
        json={"provider": "h5", "code": code, "nickname": nickname},
    )
    assert response.status_code == 200
    return response.json()


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
                    item["user_id"] == user_id
                    for item in own_orders.json()["items"]
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
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/users/"
                        f"{user_id}/orders"
                    ),
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
    provider = MiniAppIdentityProvider(
        Settings(_env_file=None, app_env="production")
    )
    with pytest.raises(IdentityProviderNotConfiguredError):
        await provider.exchange(
            IdentityProvider.H5,
            f"h5-production-device-{uuid4().hex}",
        )
