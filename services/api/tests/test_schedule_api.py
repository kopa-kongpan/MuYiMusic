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
        address="排课测试路 100 号",
        phone="0755-12345678",
        latitude=Decimal("22.543096"),
        longitude=Decimal("114.057865"),
    )


async def login_admin(
    client: AsyncClient,
    admin: AdminUser,
    password: str,
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": admin.username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_teacher_schedule_lifecycle_and_public_visibility() -> None:
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
                select(Permission).where(Permission.code == "schedules:manage")
            )
            assert permission is not None
            role = Role(code=f"schedule-manager-{uuid4()}", name="排课运营")
            role.permissions.append(permission)
            password = "test-password-2026"
            admin = AdminUser(
                username=f"schedule-admin-{uuid4().hex}",
                password_hash=hash_password(password),
            )
            admin.roles.append(role)
            allowed_store = make_store("排课授权门店")
            denied_store = make_store("排课未授权门店")
            admin.stores.append(allowed_store)
            session.add_all((admin, denied_store))
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                headers = await login_admin(client, admin, password)
                denied_response = await client.get(
                    f"/api/v1/admin/stores/{denied_store.id}/teachers",
                    headers=headers,
                )
                assert denied_response.status_code == 404

                teacher_response = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/teachers",
                    headers=headers,
                    json={
                        "name": "林老师",
                        "specialties": "钢琴、基础乐理",
                        "bio": "十年少儿钢琴教学经验",
                        "sort_order": 10,
                    },
                )
                assert teacher_response.status_code == 201
                teacher = teacher_response.json()
                teacher_id = teacher["id"]
                assert teacher["is_active"] is True

                duplicate_teacher = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/teachers",
                    headers=headers,
                    json={"name": "林老师"},
                )
                assert duplicate_teacher.status_code == 409

                starts_at = datetime.now(UTC) + timedelta(days=1)
                ends_at = starts_at + timedelta(hours=1)
                create_response = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/schedules",
                    headers=headers,
                    json={
                        "teacher_id": teacher_id,
                        "course_name": "少儿钢琴小组课",
                        "starts_at": starts_at.isoformat(),
                        "ends_at": ends_at.isoformat(),
                        "capacity": 6,
                        "notes": "请提前十分钟到店",
                    },
                )
                assert create_response.status_code == 201
                schedule = create_response.json()
                schedule_id = schedule["id"]
                assert schedule["teacher_name"] == "林老师"
                assert schedule["reserved_count"] == 0
                assert schedule["available_slots"] == 6
                assert schedule["status"] == "open"

                overlapping = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/schedules",
                    headers=headers,
                    json={
                        "teacher_id": teacher_id,
                        "course_name": "冲突课程",
                        "starts_at": (starts_at + timedelta(minutes=30)).isoformat(),
                        "ends_at": (ends_at + timedelta(minutes=30)).isoformat(),
                        "capacity": 1,
                    },
                )
                assert overlapping.status_code == 409

                past_schedule = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/schedules",
                    headers=headers,
                    json={
                        "teacher_id": teacher_id,
                        "course_name": "过去课程",
                        "starts_at": (starts_at - timedelta(days=2)).isoformat(),
                        "ends_at": (ends_at - timedelta(days=2)).isoformat(),
                        "capacity": 1,
                    },
                )
                assert past_schedule.status_code == 422

                updated_starts_at = starts_at + timedelta(hours=1)
                updated_ends_at = ends_at + timedelta(hours=1)
                update_response = await client.patch(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/schedules/"
                        f"{schedule_id}"
                    ),
                    headers=headers,
                    json={
                        "starts_at": updated_starts_at.isoformat(),
                        "ends_at": updated_ends_at.isoformat(),
                        "capacity": 8,
                    },
                )
                assert update_response.status_code == 200
                assert update_response.json()["available_slots"] == 8

                query = {
                    "starts_from": datetime.now(UTC).isoformat(),
                    "starts_before": (
                        datetime.now(UTC) + timedelta(days=3)
                    ).isoformat(),
                }
                public_response = await client.get(
                    f"/api/v1/app/stores/{allowed_store.id}/schedules",
                    params=query,
                )
                assert public_response.status_code == 200
                assert public_response.json()["total"] == 1
                assert public_response.json()["items"][0]["id"] == schedule_id

                close_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/schedules/"
                        f"{schedule_id}/status"
                    ),
                    headers=headers,
                    json={"status": "closed"},
                )
                assert close_response.status_code == 200
                assert (
                    await client.get(
                        f"/api/v1/app/stores/{allowed_store.id}/schedules",
                        params=query,
                    )
                ).json()["items"] == []

                reopen_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/schedules/"
                        f"{schedule_id}/status"
                    ),
                    headers=headers,
                    json={"status": "open"},
                )
                assert reopen_response.status_code == 200

                await client.patch(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/teachers/"
                        f"{teacher_id}"
                    ),
                    headers=headers,
                    json={"is_active": False},
                )
                hidden_for_inactive_teacher = await client.get(
                    f"/api/v1/app/stores/{allowed_store.id}/schedules",
                    params=query,
                )
                assert hidden_for_inactive_teacher.json()["items"] == []

                await client.patch(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/teachers/"
                        f"{teacher_id}"
                    ),
                    headers=headers,
                    json={"is_active": True},
                )
                cancel_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/schedules/"
                        f"{schedule_id}/status"
                    ),
                    headers=headers,
                    json={"status": "cancelled"},
                )
                assert cancel_response.status_code == 200
                assert cancel_response.json()["status"] == "cancelled"
                invalid_reopen = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/schedules/"
                        f"{schedule_id}/status"
                    ),
                    headers=headers,
                    json={"status": "open"},
                )
                assert invalid_reopen.status_code == 409
                invalid_edit = await client.patch(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/schedules/"
                        f"{schedule_id}"
                    ),
                    headers=headers,
                    json={"capacity": 9},
                )
                assert invalid_edit.status_code == 409

                too_wide_query = await client.get(
                    f"/api/v1/app/stores/{allowed_store.id}/schedules",
                    params={
                        "starts_from": datetime.now(UTC).isoformat(),
                        "starts_before": (
                            datetime.now(UTC) + timedelta(days=32)
                        ).isoformat(),
                    },
                )
                assert too_wide_query.status_code == 422

            audit_count = await session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.resource_type.in_(("teacher", "class_schedule"))
                )
            )
            assert audit_count == 8
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def test_schedule_management_requires_permission() -> None:
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
            password = "test-password-2026"
            admin = AdminUser(
                username=f"schedule-readonly-{uuid4().hex}",
                password_hash=hash_password(password),
            )
            admin.roles.append(
                Role(code=f"schedule-readonly-{uuid4()}", name="无排课权限")
            )
            store = make_store("排课权限测试门店")
            admin.stores.append(store)
            session.add(admin)
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                headers = await login_admin(client, admin, password)
                response = await client.get(
                    f"/api/v1/admin/stores/{store.id}/teachers",
                    headers=headers,
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
