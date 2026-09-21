"""预约冲突检测。

覆盖 AppointmentService.create_appointment 的各类冲突分支：
名额已满、同一学员时段重叠、教师停用、排课未关联商品。
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tests.conftest import (
    api_context,
    build_booking_world,
    create_user_login,
    make_entitlement,
    make_schedule,
)

pytestmark = pytest.mark.asyncio


async def test_schedule_capacity_blocks_second_student() -> None:
    """容量为 1 的排课，第二个学员应被拒绝且名额不被超卖。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        schedule = make_schedule(
            store=world.store,
            product=world.product,
            teacher=world.teacher,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            capacity=1,
        )
        ctx.session.add(schedule)
        await ctx.session.flush()

        first_user, first_headers = await create_user_login(
            ctx.client, ctx.session, "容量学员甲"
        )
        second_user, second_headers = await create_user_login(
            ctx.client, ctx.session, "容量学员乙"
        )
        ctx.session.add_all(
            (
                make_entitlement(
                    user=first_user, store=world.store, product=world.product
                ),
                make_entitlement(
                    user=second_user, store=world.store, product=world.product
                ),
            )
        )
        await ctx.session.flush()

        first = await ctx.client.post(
            f"/api/v1/app/schedules/{schedule.id}/appointments",
            headers={**first_headers, "Idempotency-Key": f"cap-1-{uuid4().hex}"},
            json={},
        )
        assert first.status_code == 201, first.text

        second = await ctx.client.post(
            f"/api/v1/app/schedules/{schedule.id}/appointments",
            headers={**second_headers, "Idempotency-Key": f"cap-2-{uuid4().hex}"},
            json={},
        )
        assert second.status_code == 409
        assert second.json()["message"] == "当前排课名额已满"

        await ctx.session.refresh(schedule)
        assert schedule.reserved_count == 1


async def test_overlapping_schedules_block_same_student() -> None:
    """同一学员在时段重叠的两个排课上只能预约一个。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        starts_at = datetime.now(UTC) + timedelta(days=1)
        first_schedule = make_schedule(
            store=world.store,
            product=world.product,
            teacher=world.teacher,
            starts_at=starts_at,
        )
        # 晚 15 分钟开始，与上一节课（1 小时）重叠 45 分钟。
        overlapping_schedule = make_schedule(
            store=world.store,
            product=world.product,
            teacher=world.teacher,
            starts_at=starts_at + timedelta(minutes=15),
            course_name="重叠时段课程",
        )
        ctx.session.add_all((first_schedule, overlapping_schedule))
        await ctx.session.flush()

        user, headers = await create_user_login(ctx.client, ctx.session, "重叠学员")
        ctx.session.add(
            make_entitlement(user=user, store=world.store, product=world.product)
        )
        await ctx.session.flush()

        first = await ctx.client.post(
            f"/api/v1/app/schedules/{first_schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": f"ovl-1-{uuid4().hex}"},
            json={},
        )
        assert first.status_code == 201, first.text

        overlapped = await ctx.client.post(
            f"/api/v1/app/schedules/{overlapping_schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": f"ovl-2-{uuid4().hex}"},
            json={},
        )
        assert overlapped.status_code == 409
        assert overlapped.json()["message"] == "你在该时段已有其他预约"


async def test_adjacent_schedules_do_not_overlap() -> None:
    """紧邻但不重叠（前一节结束即后一节开始）应允许预约，防止边界判断写成闭区间。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        starts_at = datetime.now(UTC) + timedelta(days=1)
        first_schedule = make_schedule(
            store=world.store,
            product=world.product,
            teacher=world.teacher,
            starts_at=starts_at,
        )
        adjacent_schedule = make_schedule(
            store=world.store,
            product=world.product,
            teacher=world.teacher,
            starts_at=starts_at + timedelta(hours=1),
            course_name="紧邻时段课程",
        )
        ctx.session.add_all((first_schedule, adjacent_schedule))
        await ctx.session.flush()

        user, headers = await create_user_login(ctx.client, ctx.session, "紧邻学员")
        ctx.session.add(
            make_entitlement(
                user=user, store=world.store, product=world.product, lessons=4
            )
        )
        await ctx.session.flush()

        first = await ctx.client.post(
            f"/api/v1/app/schedules/{first_schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": f"adj-1-{uuid4().hex}"},
            json={},
        )
        assert first.status_code == 201, first.text

        adjacent = await ctx.client.post(
            f"/api/v1/app/schedules/{adjacent_schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": f"adj-2-{uuid4().hex}"},
            json={},
        )
        assert adjacent.status_code == 201, adjacent.text


async def test_inactive_teacher_blocks_booking() -> None:
    """教师停用后其排课不可被预约。"""
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

        world.teacher.is_active = False
        await ctx.session.flush()

        user, headers = await create_user_login(ctx.client, ctx.session, "停用教师学员")
        ctx.session.add(
            make_entitlement(user=user, store=world.store, product=world.product)
        )
        await ctx.session.flush()

        response = await ctx.client.post(
            f"/api/v1/app/schedules/{schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": f"inactive-{uuid4().hex}"},
            json={},
        )
        assert response.status_code == 409
        assert response.json()["message"] == "授课教师当前不可预约"


async def test_idempotency_key_reuse_across_schedules_is_rejected() -> None:
    """同一幂等键复用到另一个排课上必须报冲突，而不是静默返回旧预约。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        starts_at = datetime.now(UTC) + timedelta(days=1)
        first_schedule = make_schedule(
            store=world.store,
            product=world.product,
            teacher=world.teacher,
            starts_at=starts_at,
        )
        other_schedule = make_schedule(
            store=world.store,
            product=world.product,
            teacher=world.teacher,
            starts_at=starts_at + timedelta(days=1),
            course_name="另一节课",
        )
        ctx.session.add_all((first_schedule, other_schedule))
        await ctx.session.flush()

        user, headers = await create_user_login(ctx.client, ctx.session, "幂等学员")
        ctx.session.add(
            make_entitlement(user=user, store=world.store, product=world.product)
        )
        await ctx.session.flush()

        shared_key = f"shared-{uuid4().hex}"
        first = await ctx.client.post(
            f"/api/v1/app/schedules/{first_schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": shared_key},
            json={},
        )
        assert first.status_code == 201, first.text

        # 同键 + 同排课 → 幂等重放，返回同一条预约。
        replay = await ctx.client.post(
            f"/api/v1/app/schedules/{first_schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": shared_key},
            json={},
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == first.json()["id"]

        # 同键 + 不同排课 → 冲突。
        misused = await ctx.client.post(
            f"/api/v1/app/schedules/{other_schedule.id}/appointments",
            headers={**headers, "Idempotency-Key": shared_key},
            json={},
        )
        assert misused.status_code == 409
        assert misused.json()["message"] == "幂等键已用于其他排课"
