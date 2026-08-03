from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_engine, get_session
from app.core.security import hash_password
from app.main import app
from app.models.admin import AdminUser, Permission, Role
from app.models.audit import AuditLog

pytestmark = pytest.mark.asyncio


async def test_admin_store_lifecycle_and_public_visibility() -> None:
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
            username = f"test-admin-{uuid4().hex}"
            password = "test-password-2026"
            permission = await session.scalar(
                select(Permission).where(Permission.code == "stores:manage")
            )
            if permission is None:
                permission = Permission(code="stores:manage", name="管理门店")
            role = Role(code=f"test-role-{uuid4()}", name="测试角色")
            role.permissions.append(permission)
            admin = AdminUser(
                username=username,
                password_hash=hash_password(password),
            )
            admin.roles.append(role)
            session.add(admin)
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                login_response = await client.post(
                    "/api/v1/admin/auth/login",
                    json={"username": username, "password": password},
                )
                assert login_response.status_code == 200
                token = login_response.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                create_response = await client.post(
                    "/api/v1/admin/stores",
                    headers=headers,
                    json={
                        "name": "集成测试门店",
                        "city": "深圳市",
                        "district": "南山区",
                        "address": "测试路 100 号",
                        "phone": "0755-12345678",
                        "latitude": 22.543096,
                        "longitude": 114.057865,
                        "status": "active",
                        "sort_order": 0,
                    },
                )
                assert create_response.status_code == 201
                store_id = create_response.json()["id"]

                public_response = await client.get(
                    "/api/v1/app/stores",
                    params={
                        "keyword": "集成测试门店",
                        "latitude": 22.543096,
                        "longitude": 114.057865,
                    },
                )
                assert public_response.status_code == 200
                assert public_response.json()["items"][0]["distance_km"] == 0

                disable_response = await client.patch(
                    f"/api/v1/admin/stores/{store_id}",
                    headers=headers,
                    json={"status": "inactive"},
                )
                assert disable_response.status_code == 200

                hidden_response = await client.get(
                    "/api/v1/app/stores",
                    params={"keyword": "集成测试门店"},
                )
                assert hidden_response.status_code == 200
                assert hidden_response.json()["items"] == []

                invalid_response = await client.post(
                    "/api/v1/admin/stores",
                    headers=headers,
                    json={},
                )
                assert invalid_response.status_code == 422
                assert invalid_response.json()["code"] == "VALIDATION_ERROR"

            audit_count = await session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.resource_id == store_id,
                )
            )
            assert audit_count == 2
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
