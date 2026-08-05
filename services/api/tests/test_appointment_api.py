from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_engine, get_session
from app.core.security import hash_password
from app.main import app
from app.models.admin import AdminUser, Permission, Role
from app.models.appointment import Appointment, LessonConsumption
from app.models.product import Category, Product, ProductStatus
from app.models.schedule import ClassSchedule, Teacher
from app.models.store import Store
from app.models.user import CourseEntitlement, EntitlementStatus, User

pytestmark = pytest.mark.asyncio


def make_store(name: str) -> Store:
    return Store(
        name=name,
        city="深圳市",
        district="南山区",
        address="预约测试路 100 号",
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


async def create_user_login(
    client: AsyncClient,
    session: AsyncSession,
    nickname: str,
) -> tuple[User, dict[str, str]]:
    response = await client.post(
        "/api/v1/app/auth/login",
        json={
            "provider": "h5",
            "code": f"appointment-{uuid4().hex}",
            "nickname": nickname,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    user = await session.get(User, UUID(payload["user"]["id"]))
    assert user is not None
    return user, {"Authorization": f"Bearer {payload['access_token']}"}


async def create_foundation(
    session: AsyncSession,
) -> tuple[Store, Store, Product, Teacher, AdminUser, AdminUser]:
    store = make_store("预约授权门店")
    denied_store = make_store("预约未授权门店")
    session.add_all((store, denied_store))
    await session.flush()

    category = Category(store_id=store.id, name="钢琴课程")
    product = Product(
        store_id=store.id,
        category=category,
        name="少儿钢琴课",
        cover_object_key="tests/appointment-cover.jpg",
        status=ProductStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    teacher = Teacher(store_id=store.id, name="预约测试教师")

    permissions = list(
        (
            await session.scalars(
                select(Permission).where(
                    Permission.code.in_(
                        (
                            "appointments:manage",
                            "consumptions:manage",
                            "consumptions:reverse",
                        )
                    )
                )
            )
        ).all()
    )
    assert len(permissions) == 3
    role = Role(code=f"appointment-manager-{uuid4()}", name="预约消课运营")
    role.permissions.extend(permissions)
    password_hash = hash_password("test-password-2026")
    admin = AdminUser(
        username=f"appointment-admin-{uuid4().hex}",
        password_hash=password_hash,
    )
    admin.roles.append(role)
    admin.stores.append(store)
    readonly_admin = AdminUser(
        username=f"appointment-readonly-{uuid4().hex}",
        password_hash=password_hash,
    )
    readonly_admin.roles.append(
        Role(code=f"appointment-readonly-{uuid4()}", name="无预约权限")
    )
    readonly_admin.stores.append(store)
    session.add_all((product, teacher, admin, readonly_admin))
    await session.flush()
    return store, denied_store, product, teacher, admin, readonly_admin


def make_schedule(
    *,
    store: Store,
    product: Product,
    teacher: Teacher,
    starts_at: datetime,
    capacity: int = 2,
    course_name: str = "少儿钢琴课",
) -> ClassSchedule:
    return ClassSchedule(
        store_id=store.id,
        product_id=product.id,
        teacher=teacher,
        course_name=course_name,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        capacity=capacity,
    )


def make_entitlement(
    *,
    user: User,
    store: Store,
    product: Product,
    lessons: int = 4,
) -> CourseEntitlement:
    now = datetime.now(UTC)
    return CourseEntitlement(
        user=user,
        store_id=store.id,
        product_id=product.id,
        course_name=product.name,
        total_lessons=lessons,
        remaining_lessons=lessons,
        valid_from=now - timedelta(days=1),
        expires_at=now + timedelta(days=180),
        status=EntitlementStatus.ACTIVE,
    )


async def test_appointment_booking_conflicts_and_cancellation() -> None:
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
            store, _, product, teacher, admin, _ = await create_foundation(session)
            starts_at = datetime.now(UTC) + timedelta(days=1)
            schedule = make_schedule(
                store=store,
                product=product,
                teacher=teacher,
                starts_at=starts_at,
                capacity=1,
            )
            overlapping_schedule = make_schedule(
                store=store,
                product=product,
                teacher=teacher,
                starts_at=starts_at + timedelta(minutes=15),
                course_name="重叠时段课程",
            )
            empty_schedule = make_schedule(
                store=store,
                product=product,
                teacher=teacher,
                starts_at=starts_at + timedelta(hours=3),
                course_name="无权益测试课程",
            )
            session.add_all((schedule, overlapping_schedule, empty_schedule))
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                user, user_headers = await create_user_login(
                    client, session, "预约学员"
                )
                entitlement = make_entitlement(
                    user=user,
                    store=store,
                    product=product,
                )
                session.add(entitlement)
                await session.flush()

                booking_headers = {
                    **user_headers,
                    "Idempotency-Key": "booking-first-0001",
                }
                create_response = await client.post(
                    f"/api/v1/app/schedules/{schedule.id}/appointments",
                    headers=booking_headers,
                    json={},
                )
                assert create_response.status_code == 201
                appointment = create_response.json()
                appointment_id = appointment["id"]
                assert appointment["status"] == "reserved"
                assert appointment["entitlement_remaining_lessons"] == 4
                assert appointment["entitlement_reserved_lessons"] == 1
                assert appointment["entitlement_available_lessons"] == 3

                idempotent_response = await client.post(
                    f"/api/v1/app/schedules/{schedule.id}/appointments",
                    headers=booking_headers,
                    json={},
                )
                assert idempotent_response.status_code == 201
                assert idempotent_response.json()["id"] == appointment_id

                duplicate_response = await client.post(
                    f"/api/v1/app/schedules/{schedule.id}/appointments",
                    headers={
                        **user_headers,
                        "Idempotency-Key": "booking-duplicate-0002",
                    },
                    json={},
                )
                assert duplicate_response.status_code == 409
                assert duplicate_response.json()["message"] == "当前排课名额已满"

                overlap_response = await client.post(
                    (f"/api/v1/app/schedules/{overlapping_schedule.id}/appointments"),
                    headers={
                        **user_headers,
                        "Idempotency-Key": "booking-overlap-0003",
                    },
                    json={},
                )
                assert overlap_response.status_code == 409
                assert "该时段已有其他预约" in overlap_response.json()["message"]

                no_entitlement_user, no_entitlement_headers = await create_user_login(
                    client, session, "无权益学员"
                )
                assert no_entitlement_user.id != user.id
                no_entitlement_response = await client.post(
                    f"/api/v1/app/schedules/{empty_schedule.id}/appointments",
                    headers={
                        **no_entitlement_headers,
                        "Idempotency-Key": "booking-no-entitlement-0004",
                    },
                    json={},
                )
                assert no_entitlement_response.status_code == 409
                assert (
                    "没有可用于该课程的有效课时"
                    in no_entitlement_response.json()["message"]
                )

                cancel_response = await client.post(
                    f"/api/v1/app/me/appointments/{appointment_id}/cancel",
                    headers={
                        **user_headers,
                        "Idempotency-Key": "cancel-user-0005",
                    },
                    json={"reason": "临时有事"},
                )
                assert cancel_response.status_code == 200
                assert cancel_response.json()["status"] == "cancelled"
                assert cancel_response.json()["cancelled_by"] == "user"

                await session.refresh(schedule)
                await session.refresh(entitlement)
                assert schedule.reserved_count == 0
                assert entitlement.reserved_lessons == 0

                rebook_response = await client.post(
                    f"/api/v1/app/schedules/{schedule.id}/appointments",
                    headers={
                        **user_headers,
                        "Idempotency-Key": "booking-rebook-0006",
                    },
                    json={"entitlement_id": str(entitlement.id)},
                )
                assert rebook_response.status_code == 201
                rebook_id = rebook_response.json()["id"]

                admin_headers = await login_admin(
                    client,
                    admin,
                    "test-password-2026",
                )
                admin_cancel = await client.post(
                    (
                        f"/api/v1/admin/stores/{store.id}/appointments/"
                        f"{rebook_id}/cancel"
                    ),
                    headers={
                        **admin_headers,
                        "Idempotency-Key": "cancel-admin-0007",
                    },
                    json={"reason": "教师临时请假"},
                )
                assert admin_cancel.status_code == 200
                assert admin_cancel.json()["cancelled_by"] == "admin"

                late_booking_schedule = make_schedule(
                    store=store,
                    product=product,
                    teacher=teacher,
                    starts_at=datetime.now(UTC) + timedelta(hours=1),
                    course_name="截止时间测试",
                )
                session.add(late_booking_schedule)
                await session.flush()
                late_booking = await client.post(
                    (f"/api/v1/app/schedules/{late_booking_schedule.id}/appointments"),
                    headers={
                        **user_headers,
                        "Idempotency-Key": "booking-late-0008",
                    },
                    json={},
                )
                assert late_booking.status_code == 409
                assert "预约截止时间" in late_booking.json()["message"]
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def test_appointment_settlement_reversal_permissions_and_store_isolation() -> (
    None
):
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
            (
                store,
                denied_store,
                product,
                teacher,
                admin,
                readonly_admin,
            ) = await create_foundation(session)
            now = datetime.now(UTC)
            attended_schedule = make_schedule(
                store=store,
                product=product,
                teacher=teacher,
                starts_at=now + timedelta(days=1),
                course_name="正常到课课程",
            )
            no_show_schedule = make_schedule(
                store=store,
                product=product,
                teacher=teacher,
                starts_at=now + timedelta(days=1, hours=3),
                course_name="缺席课程",
            )
            session.add_all((attended_schedule, no_show_schedule))
            await session.flush()

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                user, user_headers = await create_user_login(
                    client, session, "消课学员"
                )
                entitlement = make_entitlement(
                    user=user,
                    store=store,
                    product=product,
                    lessons=4,
                )
                session.add(entitlement)
                await session.flush()

                appointment_ids: list[str] = []
                for index, schedule in enumerate(
                    (attended_schedule, no_show_schedule),
                    start=1,
                ):
                    response = await client.post(
                        f"/api/v1/app/schedules/{schedule.id}/appointments",
                        headers={
                            **user_headers,
                            "Idempotency-Key": f"settle-booking-{index:04d}",
                        },
                        json={},
                    )
                    assert response.status_code == 201
                    appointment_ids.append(response.json()["id"])

                attended_schedule.starts_at = now - timedelta(hours=2)
                attended_schedule.ends_at = now - timedelta(hours=1)
                no_show_schedule.starts_at = now - timedelta(hours=4)
                no_show_schedule.ends_at = now - timedelta(hours=3)
                await session.flush()

                admin_headers = await login_admin(
                    client,
                    admin,
                    "test-password-2026",
                )
                readonly_headers = await login_admin(
                    client,
                    readonly_admin,
                    "test-password-2026",
                )
                query = {
                    "starts_from": (now - timedelta(days=1)).isoformat(),
                    "starts_before": (now + timedelta(days=1)).isoformat(),
                }
                forbidden = await client.get(
                    f"/api/v1/admin/stores/{store.id}/appointments",
                    headers=readonly_headers,
                    params=query,
                )
                assert forbidden.status_code == 403
                denied = await client.get(
                    f"/api/v1/admin/stores/{denied_store.id}/appointments",
                    headers=admin_headers,
                    params=query,
                )
                assert denied.status_code == 404

                list_response = await client.get(
                    f"/api/v1/admin/stores/{store.id}/appointments",
                    headers=admin_headers,
                    params={**query, "keyword": "消课学员"},
                )
                assert list_response.status_code == 200
                assert list_response.json()["total"] == 2
                assert all(
                    item["can_admin_settle"] for item in list_response.json()["items"]
                )

                consume_headers = {
                    **admin_headers,
                    "Idempotency-Key": "consume-attended-0001",
                }
                consume_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{store.id}/appointments/"
                        f"{appointment_ids[0]}/consume"
                    ),
                    headers=consume_headers,
                    json={"notes": "正常到课"},
                )
                assert consume_response.status_code == 200
                consumed = consume_response.json()
                assert consumed["status"] == "completed"
                assert consumed["entitlement_remaining_lessons"] == 3
                assert consumed["entitlement_reserved_lessons"] == 1
                consumption_id = consumed["active_consumption_id"]
                assert consumption_id is not None

                repeated_consume = await client.post(
                    (
                        f"/api/v1/admin/stores/{store.id}/appointments/"
                        f"{appointment_ids[0]}/consume"
                    ),
                    headers=consume_headers,
                    json={"notes": "重复请求不应再次扣课"},
                )
                assert repeated_consume.status_code == 200
                assert repeated_consume.json()["entitlement_remaining_lessons"] == 3

                reverse_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{store.id}/consumptions/"
                        f"{consumption_id}/reverse"
                    ),
                    headers={
                        **admin_headers,
                        "Idempotency-Key": "reverse-consumption-0002",
                    },
                    json={"reason": "核对后发现点错学员"},
                )
                assert reverse_response.status_code == 200
                reversed_appointment = reverse_response.json()
                assert reversed_appointment["status"] == "reserved"
                assert reversed_appointment["active_consumption_id"] is None
                assert reversed_appointment["entitlement_remaining_lessons"] == 4
                assert reversed_appointment["entitlement_reserved_lessons"] == 2

                consume_again = await client.post(
                    (
                        f"/api/v1/admin/stores/{store.id}/appointments/"
                        f"{appointment_ids[0]}/consume"
                    ),
                    headers={
                        **admin_headers,
                        "Idempotency-Key": "consume-attended-again-0003",
                    },
                    json={"notes": "复核后重新消课"},
                )
                assert consume_again.status_code == 200
                assert consume_again.json()["status"] == "completed"

                no_show_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{store.id}/appointments/"
                        f"{appointment_ids[1]}/no-show"
                    ),
                    headers={
                        **admin_headers,
                        "Idempotency-Key": "consume-no-show-0004",
                    },
                    json={"notes": "学员未到课"},
                )
                assert no_show_response.status_code == 200
                no_show = no_show_response.json()
                assert no_show["status"] == "no_show"
                assert no_show["entitlement_remaining_lessons"] == 2
                assert no_show["entitlement_reserved_lessons"] == 0

                my_appointments = await client.get(
                    "/api/v1/app/me/appointments",
                    headers=user_headers,
                    params={"store_id": str(store.id), "status": "no_show"},
                )
                assert my_appointments.status_code == 200
                assert my_appointments.json()["total"] == 1
                assert my_appointments.json()["items"][0]["id"] == appointment_ids[1]

                consumptions = list(
                    (
                        await session.scalars(
                            select(LessonConsumption).where(
                                LessonConsumption.user_id == user.id
                            )
                        )
                    ).all()
                )
                assert len(consumptions) == 3
                assert sum(item.lessons for item in consumptions) == 3
                appointments = list(
                    (
                        await session.scalars(
                            select(Appointment).where(Appointment.user_id == user.id)
                        )
                    ).all()
                )
                assert len(appointments) == 2
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
