"""权限与门店授权。

三条独立的防线，分别验证：
1. `require_permission` —— 缺权限码 → 403
2. `require_platform_admin` —— 非平台角色 → 403
3. `can_access_store` —— 有权限码但门店未授权 → 404（不泄露资源存在性）
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tests.conftest import (
    api_context,
    build_booking_world,
    create_user_login,
    login_admin,
    make_admin,
    make_entitlement,
    make_platform_admin,
    make_schedule,
)

pytestmark = pytest.mark.asyncio

_WINDOW = {
    "starts_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
    "starts_before": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
}


async def test_admin_without_permission_code_gets_403() -> None:
    """有门店授权但没有 appointments:manage，应被依赖层 403 拦下。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        weak_admin = await make_admin(
            ctx.session,
            permission_codes=("users:read",),
            stores=(world.store,),
            label="weak-admin",
        )
        headers = await login_admin(ctx.client, weak_admin)

        response = await ctx.client.get(
            f"/api/v1/admin/stores/{world.store.id}/appointments",
            headers=headers,
            params=_WINDOW,
        )
        assert response.status_code == 403
        assert response.json()["message"] == "没有执行此操作的权限"


async def test_admin_with_permission_can_list_own_store() -> None:
    """对照组：同样的接口，权限齐全 + 门店已授权就应当放行。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        headers = await login_admin(ctx.client, world.admin)

        response = await ctx.client.get(
            f"/api/v1/admin/stores/{world.store.id}/appointments",
            headers=headers,
            params=_WINDOW,
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 0


async def test_cross_store_access_returns_404_not_403() -> None:
    """权限码齐全但门店未授权：返回 404，避免通过状态码探测门店是否存在。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        headers = await login_admin(ctx.client, world.admin)

        response = await ctx.client.get(
            f"/api/v1/admin/stores/{world.other_store.id}/appointments",
            headers=headers,
            params=_WINDOW,
        )
        assert response.status_code == 404


async def test_cross_store_cancel_is_blocked() -> None:
    """跨门店取消别的门店的预约同样应被拦截，且不会改动资源。"""
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

        user, user_headers = await create_user_login(
            ctx.client, ctx.session, "跨店受害学员"
        )
        ctx.session.add(
            make_entitlement(user=user, store=world.store, product=world.product)
        )
        await ctx.session.flush()

        created = await ctx.client.post(
            f"/api/v1/app/schedules/{schedule.id}/appointments",
            headers={**user_headers, "Idempotency-Key": f"book-{uuid4().hex}"},
            json={},
        )
        assert created.status_code == 201, created.text
        appointment_id = created.json()["id"]

        # 这个管理员只被授权到 other_store。
        outsider = await make_admin(
            ctx.session,
            permission_codes=("appointments:manage",),
            stores=(world.other_store,),
            label="outsider-admin",
        )
        outsider_headers = await login_admin(ctx.client, outsider)

        # 走自己有权限的门店路径，但预约属于另一家店 → 404。
        response = await ctx.client.post(
            f"/api/v1/admin/stores/{world.other_store.id}"
            f"/appointments/{appointment_id}/cancel",
            headers={
                **outsider_headers,
                "Idempotency-Key": f"cross-{uuid4().hex}",
            },
            json={"reason": "跨店取消"},
        )
        assert response.status_code == 404

        await ctx.session.refresh(schedule)
        assert schedule.reserved_count == 1


async def test_store_operator_cannot_manage_admin_accounts() -> None:
    """门店运营即便持有 admins:manage，也进不了平台域接口。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        # 故意把 admins:manage 发给一个非平台角色：
        # require_platform_admin 要求「平台角色 且 有权限码」，只有后者不够。
        store_admin = await make_admin(
            ctx.session,
            permission_codes=("admins:manage",),
            stores=(world.store,),
            label="store-operator",
        )
        headers = await login_admin(ctx.client, store_admin)

        response = await ctx.client.get("/api/v1/admin/admin-users", headers=headers)
        assert response.status_code == 403
        assert response.json()["message"] == "仅平台管理员可以管理运营账号"


async def test_platform_admin_can_manage_admin_accounts() -> None:
    """对照组：平台管理员可以访问运营账号列表，并且不受门店授权限制。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        platform_admin = await make_platform_admin(ctx.session)
        headers = await login_admin(ctx.client, platform_admin)

        listed = await ctx.client.get("/api/v1/admin/admin-users", headers=headers)
        assert listed.status_code == 200, listed.text

        # 平台域没有门店白名单，任何门店都能查。
        any_store = await ctx.client.get(
            f"/api/v1/admin/stores/{world.other_store.id}/appointments",
            headers=headers,
            params=_WINDOW,
        )
        assert any_store.status_code == 200, any_store.text


async def test_user_token_cannot_call_admin_api() -> None:
    """学员 token 不能当管理员 token 用（subject_type 不匹配）。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        _, user_headers = await create_user_login(ctx.client, ctx.session, "越权学员")

        response = await ctx.client.get(
            f"/api/v1/admin/stores/{world.store.id}/appointments",
            headers=user_headers,
            params=_WINDOW,
        )
        assert response.status_code == 401


async def test_admin_token_cannot_call_user_api() -> None:
    """反向也要拦住：管理员 token 不能访问学员侧接口。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        admin_headers = await login_admin(ctx.client, world.admin)

        response = await ctx.client.get(
            "/api/v1/app/me/appointments", headers=admin_headers
        )
        assert response.status_code == 401


async def test_missing_and_malformed_tokens_are_rejected() -> None:
    """无 token / 伪造 token 都应是 401，而不是 500 或放行。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        path = f"/api/v1/admin/stores/{world.store.id}/appointments"

        anonymous = await ctx.client.get(path, params=_WINDOW)
        assert anonymous.status_code == 401

        forged = await ctx.client.get(
            path,
            headers={"Authorization": "Bearer not-a-real-jwt"},
            params=_WINDOW,
        )
        assert forged.status_code == 401


async def test_deactivated_admin_is_rejected() -> None:
    """管理员被停用后，已签发的 token 也应立即失效。"""
    async with api_context() as ctx:
        world = await build_booking_world(ctx.session)
        headers = await login_admin(ctx.client, world.admin)

        world.admin.is_active = False
        await ctx.session.flush()

        response = await ctx.client.get(
            f"/api/v1/admin/stores/{world.store.id}/appointments",
            headers=headers,
            params=_WINDOW,
        )
        assert response.status_code == 401
        assert response.json()["message"] == "管理员账号不可用"
