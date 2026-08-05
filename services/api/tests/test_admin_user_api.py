from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_engine, get_session
from app.core.security import hash_password
from app.main import app
from app.models.admin import AdminUser, Role
from app.models.audit import AuditLog
from app.models.store import Store
from app.repositories.admin_repository import AdminRepository

pytestmark = pytest.mark.asyncio


def make_store(name: str) -> Store:
    return Store(
        name=name,
        city="深圳市",
        district="南山区",
        address="运营账号测试路 100 号",
        phone="0755-12345678",
        latitude=Decimal("22.543096"),
        longitude=Decimal("114.057865"),
    )


async def login(
    client: AsyncClient,
    username: str,
    password: str,
) -> tuple[int, dict[str, str]]:
    response = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": username, "password": password},
    )
    if response.status_code != 200:
        return response.status_code, {}
    return 200, {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_operator_account_lifecycle_and_platform_protection() -> None:
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
            platform_role = await session.scalar(
                select(Role)
                .where(Role.code == "platform_admin")
                .options(selectinload(Role.permissions))
            )
            operator_role = await session.scalar(
                select(Role)
                .where(Role.code == "store_operator")
                .options(selectinload(Role.permissions))
            )
            assert platform_role is not None
            assert operator_role is not None
            assert "admins:manage" in {
                permission.code for permission in platform_role.permissions
            }
            assert "consumptions:reverse" not in {
                permission.code for permission in operator_role.permissions
            }

            platform_password = "platform-password-2026"
            platform_admin = AdminUser(
                username=f"platform-admin-{uuid4().hex}",
                password_hash=hash_password(platform_password),
            )
            platform_admin.roles.append(platform_role)
            first_store = make_store("运营账号一店")
            second_store = make_store("运营账号二店")
            session.add_all((platform_admin, first_store, second_store))
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                status_code, platform_headers = await login(
                    client,
                    platform_admin.username,
                    platform_password,
                )
                assert status_code == 200

                options_response = await client.get(
                    "/api/v1/admin/admin-users/options",
                    headers=platform_headers,
                )
                assert options_response.status_code == 200
                assert [role["code"] for role in options_response.json()["roles"]] == [
                    "store_operator"
                ]
                assert {store["id"] for store in options_response.json()["stores"]} >= {
                    str(first_store.id),
                    str(second_store.id),
                }

                operator_username = f"store-operator-{uuid4().hex}"
                operator_password = "operator-password-2026"
                create_response = await client.post(
                    "/api/v1/admin/admin-users",
                    headers=platform_headers,
                    json={
                        "username": operator_username,
                        "password": operator_password,
                        "role_code": "store_operator",
                        "store_ids": [str(first_store.id)],
                    },
                )
                assert create_response.status_code == 201
                created = create_response.json()
                assert created["roles"][0]["code"] == "store_operator"
                assert [store["id"] for store in created["stores"]] == [
                    str(first_store.id)
                ]
                operator_id = UUID(created["id"])

                duplicate_response = await client.post(
                    "/api/v1/admin/admin-users",
                    headers=platform_headers,
                    json={
                        "username": operator_username,
                        "password": operator_password,
                        "role_code": "store_operator",
                        "store_ids": [str(first_store.id)],
                    },
                )
                assert duplicate_response.status_code == 409

                platform_role_response = await client.post(
                    "/api/v1/admin/admin-users",
                    headers=platform_headers,
                    json={
                        "username": f"invalid-platform-{uuid4().hex}",
                        "password": operator_password,
                        "role_code": "platform_admin",
                        "store_ids": [str(first_store.id)],
                    },
                )
                assert platform_role_response.status_code == 422

                protected_response = await client.patch(
                    f"/api/v1/admin/admin-users/{platform_admin.id}",
                    headers=platform_headers,
                    json={"is_active": False},
                )
                assert protected_response.status_code == 422

                status_code, operator_headers = await login(
                    client,
                    operator_username,
                    operator_password,
                )
                assert status_code == 200
                forbidden_response = await client.get(
                    "/api/v1/admin/admin-users",
                    headers=operator_headers,
                )
                assert forbidden_response.status_code == 403

                new_password = "operator-new-password-2026"
                reset_response = await client.post(
                    f"/api/v1/admin/admin-users/{operator_id}/reset-password",
                    headers=platform_headers,
                    json={"password": new_password},
                )
                assert reset_response.status_code == 200
                old_login = await login(client, operator_username, operator_password)
                assert old_login[0] == 401
                assert (await login(client, operator_username, new_password))[0] == 200

                disable_response = await client.patch(
                    f"/api/v1/admin/admin-users/{operator_id}",
                    headers=platform_headers,
                    json={"is_active": False},
                )
                assert disable_response.status_code == 200
                assert disable_response.json()["is_active"] is False
                assert (await login(client, operator_username, new_password))[0] == 401

            saved_operator = await AdminRepository(session).get_by_id(operator_id)
            assert saved_operator is not None
            assert not saved_operator.is_active
            assert [role.code for role in saved_operator.roles] == ["store_operator"]
            assert [store.id for store in saved_operator.stores] == [first_store.id]
            audit_count = await session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.resource_type == "admin_user",
                    AuditLog.resource_id == str(operator_id),
                )
            )
            assert audit_count == 3
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
