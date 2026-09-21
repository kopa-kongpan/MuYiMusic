"""并发预约。

这个文件和其他测试不一样：**不能**用 `api_context()`。

`api_context()` 把所有请求压在同一条连接、同一个事务里，
`SELECT ... FOR UPDATE` 拿的是同一个事务自己已经持有的锁，
永远不会真正竞争——那样写出来的「并发测试」实际上是串行的，
必然通过，但什么都没验证。

所以这里用真实连接、真实提交，测完手工清理。数据用随机后缀隔离，
失败时残留的数据也不会影响下一次运行。
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text

from app.core.database import get_session_factory
from app.main import app
from app.models.appointment import Appointment
from app.models.notification import Notification
from app.models.product import Category, Product
from app.models.schedule import ClassSchedule, Teacher
from app.models.store import Store
from app.models.user import CourseEntitlement, ProviderAccount, User
from tests.conftest import (
    create_user_login,
    make_entitlement,
    make_product,
    make_schedule,
    make_store,
)

pytestmark = pytest.mark.asyncio


async def _cleanup(store_id: UUID, user_ids: list[UUID]) -> None:
    """按外键依赖顺序删除本次用到的数据。

    appointments / course_entitlements 对 users、stores 都是 RESTRICT，
    所以必须自下而上删，不能指望级联。
    """
    async with get_session_factory()() as session:
        await session.execute(
            delete(Notification).where(Notification.recipient_user_id.in_(user_ids))
        )
        await session.execute(
            delete(Notification).where(
                Notification.appointment_id.in_(
                    text(
                        "select id from appointments where store_id = :store_id"
                    ).bindparams(store_id=store_id)
                )
            )
        )
        await session.execute(
            delete(Appointment).where(Appointment.store_id == store_id)
        )
        await session.execute(
            delete(CourseEntitlement).where(CourseEntitlement.store_id == store_id)
        )
        await session.execute(
            delete(ClassSchedule).where(ClassSchedule.store_id == store_id)
        )
        await session.execute(delete(Product).where(Product.store_id == store_id))
        await session.execute(delete(Category).where(Category.store_id == store_id))
        await session.execute(delete(Teacher).where(Teacher.store_id == store_id))
        await session.execute(
            delete(ProviderAccount).where(ProviderAccount.user_id.in_(user_ids))
        )
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.execute(delete(Store).where(Store.id == store_id))
        await session.commit()


async def test_concurrent_booking_does_not_oversell() -> None:
    """N 个学员同时抢 1 个名额：只能有 1 个成功，其余 409。

    这是整套测试里最重要的一条——库存超卖是这个系统最贵的 bug。
    """
    contenders = 5
    store_id: UUID | None = None
    user_ids: list[UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            async with get_session_factory()() as setup:
                store = make_store(f"并发门店-{uuid4().hex[:8]}")
                setup.add(store)
                await setup.flush()
                store_id = store.id

                product = make_product(store)
                teacher = Teacher(store_id=store.id, name=f"并发教师-{uuid4().hex[:8]}")
                setup.add_all((product, teacher))
                await setup.flush()

                schedule = make_schedule(
                    store=store,
                    product=product,
                    teacher=teacher,
                    starts_at=datetime.now(UTC) + timedelta(days=1),
                    capacity=1,
                )
                setup.add(schedule)
                await setup.flush()
                schedule_id = schedule.id

                headers_list = []
                for index in range(contenders):
                    user, headers = await create_user_login(
                        client, setup, f"并发学员{index}"
                    )
                    user_ids.append(user.id)
                    headers_list.append(headers)
                    setup.add(make_entitlement(user=user, store=store, product=product))
                await setup.commit()

            async def book(headers: dict[str, str]):
                return await client.post(
                    f"/api/v1/app/schedules/{schedule_id}/appointments",
                    headers={**headers, "Idempotency-Key": f"race-{uuid4().hex}"},
                    json={},
                )

            responses = await asyncio.gather(
                *(book(headers) for headers in headers_list),
                return_exceptions=True,
            )

            assert not [
                item for item in responses if isinstance(item, BaseException)
            ], f"并发请求里有异常未被服务端消化：{responses}"
            codes = sorted(response.status_code for response in responses)
            assert codes.count(201) == 1, f"名额被超卖或全部失败：{codes}"
            assert all(code in (201, 409) for code in codes), codes

            async with get_session_factory()() as verify:
                final = await verify.get(ClassSchedule, schedule_id)
                assert final is not None
                assert final.reserved_count == 1
                assert final.reserved_count <= final.capacity
    finally:
        if store_id is not None:
            await _cleanup(store_id, user_ids)


async def test_concurrent_same_idempotency_key_creates_one_appointment() -> None:
    """同一个幂等键并发重放（比如客户端重试风暴），只能落一条预约。"""
    attempts = 4
    store_id: UUID | None = None
    user_ids: list[UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            async with get_session_factory()() as setup:
                store = make_store(f"幂等门店-{uuid4().hex[:8]}")
                setup.add(store)
                await setup.flush()
                store_id = store.id

                product = make_product(store)
                teacher = Teacher(store_id=store.id, name=f"幂等教师-{uuid4().hex[:8]}")
                setup.add_all((product, teacher))
                await setup.flush()

                schedule = make_schedule(
                    store=store,
                    product=product,
                    teacher=teacher,
                    starts_at=datetime.now(UTC) + timedelta(days=1),
                    capacity=attempts,
                )
                setup.add(schedule)
                await setup.flush()
                schedule_id = schedule.id

                user, headers = await create_user_login(client, setup, "幂等重试学员")
                user_ids.append(user.id)
                user_id = user.id
                setup.add(make_entitlement(user=user, store=store, product=product))
                await setup.commit()

            shared_key = f"retry-storm-{uuid4().hex}"

            async def book():
                return await client.post(
                    f"/api/v1/app/schedules/{schedule_id}/appointments",
                    headers={**headers, "Idempotency-Key": shared_key},
                    json={},
                )

            responses = await asyncio.gather(
                *(book() for _ in range(attempts)), return_exceptions=True
            )
            assert not [
                item for item in responses if isinstance(item, BaseException)
            ], f"并发重放里有异常未被服务端消化：{responses}"

            successes = [
                response for response in responses if response.status_code == 201
            ]
            assert successes, f"全部失败：{[r.status_code for r in responses]}"
            # 所有成功响应必须指向同一条预约。
            assert len({response.json()["id"] for response in successes}) == 1

            async with get_session_factory()() as verify:
                rows = (
                    await verify.scalars(
                        select(Appointment).where(Appointment.user_id == user_id)
                    )
                ).all()
                assert len(rows) == 1, f"幂等键被并发击穿，落了 {len(rows)} 条预约"

                final = await verify.get(ClassSchedule, schedule_id)
                assert final is not None
                assert final.reserved_count == 1
    finally:
        if store_id is not None:
            await _cleanup(store_id, user_ids)


async def test_failed_booking_rolls_back_reserved_counters() -> None:
    """预约失败后不能留下「名额已占但没有预约」的幽灵占位。

    容量 1 的排课先被占满，后续失败请求必须完整回滚，
    schedule.reserved_count 和 entitlement.reserved_lessons 都不能虚增。
    """
    store_id: UUID | None = None
    user_ids: list[UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            async with get_session_factory()() as setup:
                store = make_store(f"回滚门店-{uuid4().hex[:8]}")
                setup.add(store)
                await setup.flush()
                store_id = store.id

                product = make_product(store)
                teacher = Teacher(store_id=store.id, name=f"回滚教师-{uuid4().hex[:8]}")
                setup.add_all((product, teacher))
                await setup.flush()

                schedule = make_schedule(
                    store=store,
                    product=product,
                    teacher=teacher,
                    starts_at=datetime.now(UTC) + timedelta(days=1),
                    capacity=1,
                )
                setup.add(schedule)
                await setup.flush()
                schedule_id = schedule.id

                winner, winner_headers = await create_user_login(
                    client, setup, "占位成功学员"
                )
                loser, loser_headers = await create_user_login(
                    client, setup, "占位失败学员"
                )
                user_ids.extend((winner.id, loser.id))
                setup.add_all(
                    (
                        make_entitlement(user=winner, store=store, product=product),
                        make_entitlement(user=loser, store=store, product=product),
                    )
                )
                await setup.commit()
                loser_id = loser.id

            first = await client.post(
                f"/api/v1/app/schedules/{schedule_id}/appointments",
                headers={**winner_headers, "Idempotency-Key": f"win-{uuid4().hex}"},
                json={},
            )
            assert first.status_code == 201, first.text

            blocked = await client.post(
                f"/api/v1/app/schedules/{schedule_id}/appointments",
                headers={**loser_headers, "Idempotency-Key": f"lose-{uuid4().hex}"},
                json={},
            )
            assert blocked.status_code == 409

            async with get_session_factory()() as verify:
                final_schedule = await verify.get(ClassSchedule, schedule_id)
                assert final_schedule is not None
                assert final_schedule.reserved_count == 1

                loser_entitlement = (
                    await verify.scalars(
                        select(CourseEntitlement).where(
                            CourseEntitlement.user_id == loser_id
                        )
                    )
                ).one()
                # 失败方的锁定课时必须是 0，否则课时会被永久冻结。
                assert loser_entitlement.reserved_lessons == 0
                assert loser_entitlement.remaining_lessons == 4
    finally:
        if store_id is not None:
            await _cleanup(store_id, user_ids)
