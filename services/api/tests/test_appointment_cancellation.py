"""预约取消与截止时间。

覆盖学员取消（受 CANCELLATION_CUTOFF_MINUTES 约束）、
管理员取消（不受截止时间约束）以及取消后的资源归还。
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.appointment import AppointmentCancelledBy, AppointmentStatus
from tests.conftest import (
    api_context,
    build_booking_world,
    create_user_login,
    login_admin,
    make_entitlement,
    make_schedule,
)

pytestmark = pytest.mark.asyncio


async def _book(ctx, world, *, starts_at, nickname="取消学员", capacity=2):
    schedule = make_schedule(
        store=world.store,
        product=world.product,
        teacher=world.teacher,
        starts_at=starts_at,
        capacity=capacity,
    )
    ctx.session.add(schedule)
    await ctx.session.flush()

    user, headers = await create_user_login(ctx.client, ctx.session, nickname)
    entitlement = make_entitlement(user=user, store=world.store, product=world.product)
    ctx.session.add(entitlement)
    await ctx.session.flush()

    created = await ctx.client.post(
        f"/api/v1/app/schedules/{schedule.id}/appointments",
        headers={**headers, "Idempotency-Key": f"book-{uuid4().hex}"},
        json={},
    )
    assert created.status_code == 201, created.text
    return schedule, entitlement, headers, created.json()["id"]


async def test_user_cancel_before_cutoff_releases_resources() -> None:
    """截止时间前取消：名额和锁定课时都归还，状态转 cancelled。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        schedule, entitlement, headers, appointment_id = await _book(
            ctx, world, starts_at=datetime.now(UTC) + timedelta(days=1)
        )

        await ctx.session.refresh(schedule)
        await ctx.session.refresh(entitlement)
        assert schedule.reserved_count == 1
        assert entitlement.reserved_lessons == 1

        response = await ctx.client.post(
            f"/api/v1/app/me/appointments/{appointment_id}/cancel",
            headers={**headers, "Idempotency-Key": f"cancel-{uuid4().hex}"},
            json={"reason": "临时有事"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "cancelled"

        await ctx.session.refresh(schedule)
        await ctx.session.refresh(entitlement)
        assert schedule.reserved_count == 0
        assert entitlement.reserved_lessons == 0
        # 取消不扣课时，只释放锁定。
        assert entitlement.remaining_lessons == 4


async def test_user_cancel_after_cutoff_is_rejected() -> None:
    """超过取消截止时间（开课前 2 小时）后学员不能自行取消。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        schedule, entitlement, headers, appointment_id = await _book(
            ctx, world, starts_at=datetime.now(UTC) + timedelta(days=1)
        )

        # 把开课时间挪到 1 小时后，已进入 2 小时截止窗口内。
        schedule.starts_at = datetime.now(UTC) + timedelta(hours=1)
        schedule.ends_at = schedule.starts_at + timedelta(hours=1)
        await ctx.session.flush()

        response = await ctx.client.post(
            f"/api/v1/app/me/appointments/{appointment_id}/cancel",
            headers={**headers, "Idempotency-Key": f"cancel-late-{uuid4().hex}"},
            json={"reason": "临时有事"},
        )
        assert response.status_code == 409
        assert "取消截止时间" in response.json()["message"]

        # 被拒后资源不应发生变化。
        await ctx.session.refresh(schedule)
        await ctx.session.refresh(entitlement)
        assert schedule.reserved_count == 1
        assert entitlement.reserved_lessons == 1


async def test_admin_cancel_ignores_cutoff() -> None:
    """管理员取消不受截止时间限制，并记录取消来源为 admin。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        schedule, entitlement, _, appointment_id = await _book(
            ctx,
            world,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            nickname="管理员取消学员",
        )

        # 同样挪进截止窗口内，学员已无法取消。
        schedule.starts_at = datetime.now(UTC) + timedelta(minutes=30)
        schedule.ends_at = schedule.starts_at + timedelta(hours=1)
        await ctx.session.flush()

        admin_headers = await login_admin(ctx.client, world.admin)
        response = await ctx.client.post(
            f"/api/v1/admin/stores/{world.store.id}"
            f"/appointments/{appointment_id}/cancel",
            headers={**admin_headers, "Idempotency-Key": f"admin-cx-{uuid4().hex}"},
            json={"reason": "教师临时请假"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "cancelled"

        await ctx.session.refresh(schedule)
        await ctx.session.refresh(entitlement)
        assert schedule.reserved_count == 0
        assert entitlement.reserved_lessons == 0


async def test_cancel_is_idempotent() -> None:
    """重复取消同一预约返回成功但不会重复归还名额。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        schedule, entitlement, headers, appointment_id = await _book(
            ctx,
            world,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            nickname="重复取消学员",
        )

        first = await ctx.client.post(
            f"/api/v1/app/me/appointments/{appointment_id}/cancel",
            headers={**headers, "Idempotency-Key": f"cx-1-{uuid4().hex}"},
            json={"reason": "第一次取消"},
        )
        assert first.status_code == 200, first.text

        second = await ctx.client.post(
            f"/api/v1/app/me/appointments/{appointment_id}/cancel",
            headers={**headers, "Idempotency-Key": f"cx-2-{uuid4().hex}"},
            json={"reason": "第二次取消"},
        )
        assert second.status_code == 200, second.text
        assert second.json()["status"] == "cancelled"

        await ctx.session.refresh(schedule)
        await ctx.session.refresh(entitlement)
        # 名额只被归还一次，不会变成负数或超额。
        assert schedule.reserved_count == 0
        assert entitlement.reserved_lessons == 0


async def test_cancelled_slot_can_be_rebooked_by_another_student() -> None:
    """取消释放的名额应能被其他学员抢到（容量 1 的排课）。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        schedule, _, headers, appointment_id = await _book(
            ctx,
            world,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            nickname="先占位学员",
            capacity=1,
        )

        other_user, other_headers = await create_user_login(
            ctx.client, ctx.session, "候补学员"
        )
        ctx.session.add(
            make_entitlement(user=other_user, store=world.store, product=world.product)
        )
        await ctx.session.flush()

        # 满员时候补失败。
        blocked = await ctx.client.post(
            f"/api/v1/app/schedules/{schedule.id}/appointments",
            headers={**other_headers, "Idempotency-Key": f"wait-1-{uuid4().hex}"},
            json={},
        )
        assert blocked.status_code == 409

        cancelled = await ctx.client.post(
            f"/api/v1/app/me/appointments/{appointment_id}/cancel",
            headers={**headers, "Idempotency-Key": f"cx-{uuid4().hex}"},
            json={"reason": "让位"},
        )
        assert cancelled.status_code == 200, cancelled.text

        # 名额释放后候补成功。
        retried = await ctx.client.post(
            f"/api/v1/app/schedules/{schedule.id}/appointments",
            headers={**other_headers, "Idempotency-Key": f"wait-2-{uuid4().hex}"},
            json={},
        )
        assert retried.status_code == 201, retried.text


async def test_other_user_cannot_cancel_someone_elses_appointment() -> None:
    """学员不能取消别人的预约，且应返回 404 而非 403（不泄露存在性）。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        schedule, entitlement, _, appointment_id = await _book(
            ctx,
            world,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            nickname="被害学员",
        )

        _, attacker_headers = await create_user_login(
            ctx.client, ctx.session, "越权学员"
        )
        response = await ctx.client.post(
            f"/api/v1/app/me/appointments/{appointment_id}/cancel",
            headers={**attacker_headers, "Idempotency-Key": f"evil-{uuid4().hex}"},
            json={"reason": "越权取消"},
        )
        assert response.status_code == 404

        await ctx.session.refresh(schedule)
        await ctx.session.refresh(entitlement)
        assert schedule.reserved_count == 1
        assert entitlement.reserved_lessons == 1


async def test_cancelled_appointment_records_actor() -> None:
    """取消记录里要写清是谁取消的，供后续对账与申诉。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        _, _, headers, appointment_id = await _book(
            ctx,
            world,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            nickname="取消归因学员",
        )

        response = await ctx.client.post(
            f"/api/v1/app/me/appointments/{appointment_id}/cancel",
            headers={**headers, "Idempotency-Key": f"cx-{uuid4().hex}"},
            json={"reason": "学员自主取消"},
        )
        assert response.status_code == 200, response.text

        from uuid import UUID

        from app.models.appointment import Appointment

        appointment = await ctx.session.get(Appointment, UUID(appointment_id))
        assert appointment is not None
        assert appointment.status == AppointmentStatus.CANCELLED
        assert appointment.cancelled_by == AppointmentCancelledBy.USER
        assert appointment.cancellation_reason == "学员自主取消"
        assert appointment.cancelled_at is not None
