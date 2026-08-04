from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
from app.models.store import Store

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
        sort_order=0,
    )


async def test_store_home_content_lifecycle_and_store_isolation() -> None:
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
                select(Permission).where(Permission.code == "store_content:manage")
            )
            assert permission is not None
            role = Role(code=f"content-operator-{uuid4()}", name="内容运营")
            role.permissions.append(permission)
            password = "test-password-2026"
            admin = AdminUser(
                username=f"content-admin-{uuid4().hex}",
                password_hash=hash_password(password),
            )
            admin.roles.append(role)
            allowed_store = make_store("已授权内容门店")
            denied_store = make_store("未授权内容门店")
            admin.stores.append(allowed_store)
            session.add_all((admin, denied_store))
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                login_response = await client.post(
                    "/api/v1/admin/auth/login",
                    json={"username": admin.username, "password": password},
                )
                assert login_response.status_code == 200
                headers = {
                    "Authorization": (f"Bearer {login_response.json()['access_token']}")
                }

                stores_response = await client.get(
                    "/api/v1/admin/stores",
                    headers=headers,
                )
                assert stores_response.status_code == 200
                assert [item["id"] for item in stores_response.json()["items"]] == [
                    str(allowed_store.id)
                ]

                denied_response = await client.get(
                    f"/api/v1/admin/stores/{denied_store.id}/home-content",
                    headers=headers,
                )
                assert denied_response.status_code == 404

                shortcut_response = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/home-content",
                    headers=headers,
                    json={
                        "block_type": "shortcut",
                        "title": "课程介绍",
                        "jump_type": "internal",
                        "jump_target": "/pages/courses/index",
                        "sort_order": 20,
                        "status": "enabled",
                    },
                )
                assert shortcut_response.status_code == 201
                shortcut_id = shortcut_response.json()["id"]

                image_key = f"muyimusic/stores/{allowed_store.id}/home/test-image.jpg"
                image_response = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/home-content",
                    headers=headers,
                    json={
                        "block_type": "image",
                        "title": "门店环境",
                        "media_object_key": image_key,
                        "jump_type": "none",
                        "sort_order": 10,
                        "status": "enabled",
                    },
                )
                assert image_response.status_code == 201
                image_id = image_response.json()["id"]

                future_response = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/home-content",
                    headers=headers,
                    json={
                        "block_type": "image",
                        "title": "未来活动",
                        "media_object_key": (
                            f"muyimusic/stores/{allowed_store.id}/home/future.jpg"
                        ),
                        "jump_type": "none",
                        "sort_order": 0,
                        "status": "enabled",
                        "starts_at": (
                            datetime.now(UTC) + timedelta(days=1)
                        ).isoformat(),
                    },
                )
                assert future_response.status_code == 201

                home_response = await client.get(
                    f"/api/v1/app/stores/{allowed_store.id}/home"
                )
                assert home_response.status_code == 200
                assert home_response.json()["store"]["id"] == str(allowed_store.id)
                assert [
                    item["id"] for item in home_response.json()["content_blocks"]
                ] == [image_id, shortcut_id]

                reorder_response = await client.put(
                    f"/api/v1/admin/stores/{allowed_store.id}/home-content/order",
                    headers=headers,
                    json={
                        "items": [
                            {"id": shortcut_id, "sort_order": 10},
                            {"id": image_id, "sort_order": 30},
                        ]
                    },
                )
                assert reorder_response.status_code == 200

                reordered_home = await client.get(
                    f"/api/v1/app/stores/{allowed_store.id}/home"
                )
                assert [
                    item["id"] for item in reordered_home.json()["content_blocks"]
                ] == [shortcut_id, image_id]

                disable_response = await client.patch(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/home-content/"
                        f"{shortcut_id}"
                    ),
                    headers=headers,
                    json={"status": "disabled"},
                )
                assert disable_response.status_code == 200

                visible_home = await client.get(
                    f"/api/v1/app/stores/{allowed_store.id}/home"
                )
                assert [
                    item["id"] for item in visible_home.json()["content_blocks"]
                ] == [image_id]

                upload_response = await client.post(
                    "/api/v1/admin/media/upload-tickets",
                    headers=headers,
                    json={
                        "store_id": str(allowed_store.id),
                        "file_name": "store.jpg",
                        "content_type": "image/jpeg",
                        "file_size": 1024,
                    },
                )
                assert upload_response.status_code == 503
                assert "尚未配置" in upload_response.json()["message"]

            audit_count = await session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.resource_type == "store_content",
                )
            )
            assert audit_count == 4
            reorder_audit_count = await session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.action == "store_content.reorder",
                    AuditLog.resource_id == str(allowed_store.id),
                )
            )
            assert reorder_audit_count == 1
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def test_store_content_requires_manage_permission() -> None:
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
            store = make_store("无权限测试门店")
            role = Role(code=f"readonly-{uuid4()}", name="只读角色")
            password = "test-password-2026"
            admin = AdminUser(
                username=f"readonly-{uuid4().hex}",
                password_hash=hash_password(password),
            )
            admin.roles.append(role)
            admin.stores.append(store)
            session.add(admin)
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                login_response = await client.post(
                    "/api/v1/admin/auth/login",
                    json={"username": admin.username, "password": password},
                )
                headers = {
                    "Authorization": (f"Bearer {login_response.json()['access_token']}")
                }
                response = await client.get(
                    f"/api/v1/admin/stores/{store.id}/home-content",
                    headers=headers,
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
