from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_engine, get_session
from app.core.security import hash_password
from app.main import app
from app.models.admin import AdminUser, Permission, Role
from app.models.store import Store

pytestmark = pytest.mark.asyncio


async def test_franchise_page_draft_publish_and_update() -> None:
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
            role = Role(code=f"franchise-{uuid4()}", name="加盟内容运营")
            role.permissions.append(permission)
            password = "test-password-2026"
            admin = AdminUser(
                username=f"franchise-{uuid4().hex}",
                password_hash=hash_password(password),
            )
            admin.roles.append(role)
            store = Store(
                name="加盟测试门店",
                city="深圳市",
                district="南山区",
                address="测试路 1 号",
                phone="0755-12345678",
                latitude=Decimal("22.543096"),
                longitude=Decimal("114.057865"),
            )
            admin.stores.append(store)
            session.add(admin)
            await session.flush()

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                login = await client.post(
                    "/api/v1/admin/auth/login",
                    json={"username": admin.username, "password": password},
                )
                headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
                admin_url = f"/api/v1/admin/stores/{store.id}/franchise"
                public_url = f"/api/v1/app/stores/{store.id}/franchise"

                assert (await client.get(admin_url, headers=headers)).json() is None
                default_public = await client.get(public_url)
                assert default_public.status_code == 200
                assert default_public.json()["contact_phone"] == store.phone
                payload = {
                    "title": "携手共创音乐教育未来",
                    "introduction": "面向认同音乐教育价值的合作伙伴。",
                    "advantages": "课程体系\n品牌运营",
                    "support_policy": "选址支持\n师资培训",
                    "application_process": "提交意向\n项目评估\n签约筹备",
                    "contact_name": "合作顾问",
                    "contact_phone": "13800138000",
                    "contact_wechat": "muyimusic",
                    "is_published": False,
                }
                draft = await client.put(admin_url, headers=headers, json=payload)
                assert draft.status_code == 200
                assert (await client.get(public_url)).status_code == 404

                payload["is_published"] = True
                payload["title"] = "木易音乐加盟合作"
                published = await client.put(admin_url, headers=headers, json=payload)
                assert published.status_code == 200
                public = await client.get(public_url)
                assert public.status_code == 200
                assert public.json()["title"] == "木易音乐加盟合作"
                assert "is_published" not in public.json()
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
