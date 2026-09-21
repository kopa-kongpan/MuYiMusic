"""课时扣减与恢复。

覆盖消课（ATTENDED）、缺席（NO_SHOW）、撤销消课三条路径对
CourseEntitlement.remaining_lessons / reserved_lessons 的影响，
以及课时耗尽后的状态流转。
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.appointment import LessonConsumption
from app.models.user import EntitlementStatus
from tests.conftest import (
    api_context,
    build_booking_world,
    create_user_login,
    login_admin,
    make_entitlement,
    make_schedule,
)

pytestmark = pytest.mark.asyncio


async def _book_past_lesson(
    ctx, world, *, lessons: int = 2, nickname: str = "消课学员"
):
    """建一个已结束的排课并完成预约。

    返回 (user, headers, entitlement, appointment_id)。
    消课要求 schedule.ends_at <= now，但预约要求未过截止时间，
    所以先在未来时段下单，再把排课时间改到过去。
    """
    schedule = make_schedule(
        store=world.store,
        product=world.product,
        teacher=world.teacher,
        starts_at=datetime.now(UTC) + timedelta(days=1),
    )
    ctx.session.add(schedule)
    await ctx.session.flush()

    user, headers = await create_user_login(ctx.client, ctx.session, nickname)
    entitlement = make_entitlement(
        user=user, store=world.store, product=world.product, lessons=lessons
    )
    ctx.session.add(entitlement)
    await ctx.session.flush()

    created = await ctx.client.post(
        f"/api/v1/app/schedules/{schedule.id}/appointments",
        headers={**headers, "Idempotency-Key": f"book-{uuid4().hex}"},
        json={},
    )
    assert created.status_code == 201, created.text

    now = datetime.now(UTC)
    schedule.starts_at = now - timedelta(hours=2)
    schedule.ends_at = now - timedelta(hours=1)
    await ctx.session.flush()

    return user, headers, entitlement, created.json()["id"]


async def test_attended_consumption_deducts_one_lesson() -> None:
    """正常消课：remaining 和 reserved 各减 1，预约转 completed。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        _, _, entitlement, appointment_id = await _book_past_lesson(
            ctx, world, lessons=2
        )
        admin_headers = await login_admin(ctx.client, world.admin)

        await ctx.session.refresh(entitlement)
        assert entitlement.remaining_lessons == 2
        assert entitlement.reserved_lessons == 1

        response = await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/appointments/{appointment_id}/consume",
            headers={**admin_headers, "Idempotency-Key": f"consume-{uuid4().hex}"},
            json={"notes": "正常到课"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"

        await ctx.session.refresh(entitlement)
        assert entitlement.remaining_lessons == 1
        assert entitlement.reserved_lessons == 0
        assert entitlement.status == EntitlementStatus.ACTIVE


async def test_no_show_also_deducts_one_lesson() -> None:
    """缺席同样扣 1 课时，但预约状态是 no_show。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        _, _, entitlement, appointment_id = await _book_past_lesson(
            ctx, world, lessons=3, nickname="缺席学员"
        )
        admin_headers = await login_admin(ctx.client, world.admin)

        response = await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/appointments/{appointment_id}/no-show",
            headers={**admin_headers, "Idempotency-Key": f"noshow-{uuid4().hex}"},
            json={"notes": "未到场"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "no_show"

        await ctx.session.refresh(entitlement)
        assert entitlement.remaining_lessons == 2
        assert entitlement.reserved_lessons == 0


async def test_reverse_consumption_restores_lesson() -> None:
    """撤销消课把课时还回去，并且权益状态从耗尽回到 active。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        # 只给 1 课时：消课后应耗尽，撤销后应恢复为 active。
        _, _, entitlement, appointment_id = await _book_past_lesson(
            ctx, world, lessons=1, nickname="撤销学员"
        )
        admin_headers = await login_admin(ctx.client, world.admin)

        consumed = await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/appointments/{appointment_id}/consume",
            headers={**admin_headers, "Idempotency-Key": f"consume-{uuid4().hex}"},
            json={"notes": "先消课"},
        )
        assert consumed.status_code == 200, consumed.text

        await ctx.session.refresh(entitlement)
        assert entitlement.remaining_lessons == 0
        assert entitlement.status == EntitlementStatus.EXHAUSTED

        consumption = (
            await ctx.session.scalars(
                select(LessonConsumption).where(
                    LessonConsumption.appointment_id == appointment_id
                )
            )
        ).one()

        reversed_response = await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/consumptions/{consumption.id}/reverse",
            headers={**admin_headers, "Idempotency-Key": f"reverse-{uuid4().hex}"},
            json={"reason": "误操作撤销"},
        )
        assert reversed_response.status_code == 200, reversed_response.text

        await ctx.session.refresh(entitlement)
        assert entitlement.remaining_lessons == 1
        assert entitlement.status == EntitlementStatus.ACTIVE


async def test_double_reverse_is_rejected() -> None:
    """同一条消课记录不能被撤销两次，否则课时会被凭空放大。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        _, _, entitlement, appointment_id = await _book_past_lesson(
            ctx, world, lessons=2, nickname="重复撤销学员"
        )
        admin_headers = await login_admin(ctx.client, world.admin)

        await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/appointments/{appointment_id}/consume",
            headers={**admin_headers, "Idempotency-Key": f"consume-{uuid4().hex}"},
            json={"notes": "消课"},
        )
        consumption = (
            await ctx.session.scalars(
                select(LessonConsumption).where(
                    LessonConsumption.appointment_id == appointment_id
                )
            )
        ).one()

        first = await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/consumptions/{consumption.id}/reverse",
            headers={**admin_headers, "Idempotency-Key": f"rev-1-{uuid4().hex}"},
            json={"reason": "第一次撤销"},
        )
        assert first.status_code == 200, first.text

        second = await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/consumptions/{consumption.id}/reverse",
            headers={**admin_headers, "Idempotency-Key": f"rev-2-{uuid4().hex}"},
            json={"reason": "第二次撤销"},
        )
        assert second.status_code == 409
        assert second.json()["message"] == "该消课记录已撤销或不可撤销"

        await ctx.session.refresh(entitlement)
        # 撤销只生效一次：2 - 1(消课) + 1(撤销) = 2。
        assert entitlement.remaining_lessons == 2


async def test_consume_before_class_ends_is_rejected() -> None:
    """课程还没结束就消课应被拒绝。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        schedule = make_schedule(
            store=world.store,
            product=world.product,
            teacher=world.teacher,
            starts_at=datetime.now(UTC) + timedelta(days=1),
        )
        ctx.session.add(schedule)
        await ctx.session.flush()

        user, headers = await create_user_login(ctx.client, ctx.session, "提前消课学员")
        ctx.session.add(
            make_entitlement(user=user, store=world.store, product=world.product)
        )
        await ctx.session.flush()

        created = await ctx.client.post(
            f"/api/v1/app/schedules/{schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": f"early-{uuid4().hex}"},
            json={},
        )
        assert created.status_code == 201, created.text

        admin_headers = await login_admin(ctx.client, world.admin)
        response = await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/appointments/{created.json()['id']}/consume",
            headers={**admin_headers, "Idempotency-Key": f"consume-{uuid4().hex}"},
            json={"notes": "提前消课"},
        )
        assert response.status_code == 409
        assert response.json()["message"] == "课程结束后才能执行消课或缺席"


async def test_exhausted_entitlement_blocks_further_booking() -> None:
    """课时耗尽后，同一学员不能再预约同一课程。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        _, headers, entitlement, appointment_id = await _book_past_lesson(
            ctx, world, lessons=1, nickname="耗尽学员"
        )
        admin_headers = await login_admin(ctx.client, world.admin)

        consumed = await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/appointments/{appointment_id}/consume",
            headers={**admin_headers, "Idempotency-Key": f"consume-{uuid4().hex}"},
            json={"notes": "用掉唯一课时"},
        )
        assert consumed.status_code == 200, consumed.text

        await ctx.session.refresh(entitlement)
        assert entitlement.remaining_lessons == 0
        assert entitlement.status == EntitlementStatus.EXHAUSTED

        future_schedule = make_schedule(
            store=world.store,
            product=world.product,
            teacher=world.teacher,
            starts_at=datetime.now(UTC) + timedelta(days=2),
            course_name="耗尽后课程",
        )
        ctx.session.add(future_schedule)
        await ctx.session.flush()

        # 关键：复用原学员的 token，命中的是那条已耗尽的权益，
        # 而不是一个天生没有权益的新用户。
        response = await ctx.client.post(
            f"/api/v1/app/schedules/{future_schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": f"after-exhaust-{uuid4().hex}"},
            json={},
        )
        assert response.status_code == 409
        assert response.json()["message"] == "没有可用于该课程的有效课时"
