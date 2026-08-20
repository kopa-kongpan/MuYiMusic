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
        address="测试路 200 号",
        phone="0755-87654321",
        latitude=Decimal("22.543096"),
        longitude=Decimal("114.057865"),
        sort_order=0,
    )


async def test_course_product_lifecycle_and_public_purchase_validation() -> None:
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
                select(Permission).where(Permission.code == "products:manage")
            )
            assert permission is not None
            role = Role(code=f"product-operator-{uuid4()}", name="课程运营")
            role.permissions.append(permission)
            password = "test-password-2026"
            admin = AdminUser(
                username=f"product-admin-{uuid4().hex}",
                password_hash=hash_password(password),
            )
            admin.roles.append(role)
            allowed_store = make_store("已授权课程门店")
            denied_store = make_store("未授权课程门店")
            admin.stores.append(allowed_store)
            session.add_all((admin, denied_store))
            await session.flush()
            audit_count_before = await session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.resource_type.in_(("category", "product"))
                )
            )
            assert audit_count_before is not None

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
                    "Authorization": f"Bearer {login_response.json()['access_token']}"
                }

                denied_response = await client.get(
                    f"/api/v1/admin/stores/{denied_store.id}/categories",
                    headers=headers,
                )
                assert denied_response.status_code == 404

                category_response = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/categories",
                    headers=headers,
                    json={"name": "钢琴课程", "sort_order": 10},
                )
                assert category_response.status_code == 201
                category_id = category_response.json()["id"]

                duplicate_response = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/categories",
                    headers=headers,
                    json={"name": "钢琴课程"},
                )
                assert duplicate_response.status_code == 409

                invalid_product = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/products",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "name": "少儿钢琴启蒙",
                        "cover_object_key": "other-store/product.jpg",
                        "skus": [
                            {
                                "name": "10 课时",
                                "price_cents": 168000,
                                "lesson_count": 10,
                                "validity_days": 180,
                            }
                        ],
                    },
                )
                assert invalid_product.status_code == 422

                product_prefix = f"muyimusic/stores/{allowed_store.id}/products/"
                product_response = await client.post(
                    f"/api/v1/admin/stores/{allowed_store.id}/products",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "name": "少儿钢琴启蒙",
                        "summary": "系统学习基础乐理与演奏",
                        "details": "适合零基础儿童。",
                        "notes": "需提前预约上课。",
                        "cover_object_key": f"{product_prefix}cover.jpg",
                        "sort_order": 10,
                        "skus": [
                            {
                                "name": "10 课时",
                                "price_cents": 168000,
                                "lesson_count": 10,
                                "validity_days": 180,
                                "sort_order": 10,
                            }
                        ],
                        "images": [
                            {
                                "object_key": f"{product_prefix}detail.jpg",
                                "sort_order": 10,
                            }
                        ],
                    },
                )
                assert product_response.status_code == 201
                product = product_response.json()
                assert product["status"] == "draft"
                product_id = product["id"]
                sku_id = product["skus"][0]["id"]

                hidden_response = await client.get(
                    f"/api/v1/app/stores/{allowed_store.id}/products/{product_id}"
                )
                assert hidden_response.status_code == 404

                publish_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/products/"
                        f"{product_id}/status"
                    ),
                    headers=headers,
                    json={"status": "published"},
                )
                assert publish_response.status_code == 200
                assert publish_response.json()["published_at"] is not None

                categories_response = await client.get(
                    f"/api/v1/app/stores/{allowed_store.id}/categories"
                )
                assert categories_response.status_code == 200
                assert [item["id"] for item in categories_response.json()] == [
                    category_id
                ]

                list_response = await client.get(
                    f"/api/v1/app/stores/{allowed_store.id}/products",
                    params={"keyword": "钢琴", "sort": "price_asc"},
                )
                assert list_response.status_code == 200
                assert list_response.json()["total"] == 1
                assert list_response.json()["items"][0]["min_price_cents"] == 168000
                assert list_response.json()["items"][0]["lesson_count"] == 10
                assert list_response.json()["items"][0]["default_sku_id"] == sku_id

                purchase_response = await client.post(
                    (
                        f"/api/v1/app/stores/{allowed_store.id}/products/"
                        f"{product_id}/purchase-validation"
                    ),
                    json={"sku_id": sku_id, "quantity": 2},
                )
                assert purchase_response.status_code == 200
                assert purchase_response.json()["total_price_cents"] == 336000

                update_response = await client.patch(
                    f"/api/v1/admin/stores/{allowed_store.id}/products/{product_id}",
                    headers=headers,
                    json={
                        "skus": [
                            {
                                "id": sku_id,
                                "name": "10 课时",
                                "price_cents": 158000,
                                "lesson_count": 10,
                                "validity_days": 180,
                                "sort_order": 10,
                                "is_active": True,
                            }
                        ]
                    },
                )
                assert update_response.status_code == 200

                null_name_response = await client.patch(
                    f"/api/v1/admin/stores/{allowed_store.id}/products/{product_id}",
                    headers=headers,
                    json={"name": None},
                )
                assert null_name_response.status_code == 422

                mixed_timezone_response = await client.patch(
                    f"/api/v1/admin/stores/{allowed_store.id}/products/{product_id}",
                    headers=headers,
                    json={
                        "sale_starts_at": datetime.now(UTC).isoformat(),
                        "sale_ends_at": (
                            datetime.now() + timedelta(days=1)
                        ).isoformat(),
                    },
                )
                assert mixed_timezone_response.status_code == 422

                current_price_response = await client.post(
                    (
                        f"/api/v1/app/stores/{allowed_store.id}/products/"
                        f"{product_id}/purchase-validation"
                    ),
                    json={"sku_id": sku_id, "quantity": 2},
                )
                assert current_price_response.status_code == 200
                assert current_price_response.json()["unit_price_cents"] == 158000
                assert current_price_response.json()["total_price_cents"] == 316000

                disable_category = await client.patch(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/categories/"
                        f"{category_id}"
                    ),
                    headers=headers,
                    json={"is_enabled": False},
                )
                assert disable_category.status_code == 200
                assert (
                    await client.get(
                        f"/api/v1/app/stores/{allowed_store.id}/products/{product_id}"
                    )
                ).status_code == 404

                await client.patch(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/categories/"
                        f"{category_id}"
                    ),
                    headers=headers,
                    json={"is_enabled": True},
                )
                offline_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/products/"
                        f"{product_id}/status"
                    ),
                    headers=headers,
                    json={"status": "offline"},
                )
                assert offline_response.status_code == 200
                assert (
                    await client.get(
                        f"/api/v1/app/stores/{allowed_store.id}/products/{product_id}"
                    )
                ).status_code == 404

                republish_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/products/"
                        f"{product_id}/status"
                    ),
                    headers=headers,
                    json={"status": "published"},
                )
                assert republish_response.status_code == 200
                assert (
                    await client.get(
                        f"/api/v1/app/stores/{allowed_store.id}/products/{product_id}"
                    )
                ).status_code == 200

                second_offline_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/products/"
                        f"{product_id}/status"
                    ),
                    headers=headers,
                    json={"status": "offline"},
                )
                assert second_offline_response.status_code == 200

                archive_response = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/products/"
                        f"{product_id}/status"
                    ),
                    headers=headers,
                    json={"status": "archived"},
                )
                assert archive_response.status_code == 200
                invalid_transition = await client.post(
                    (
                        f"/api/v1/admin/stores/{allowed_store.id}/products/"
                        f"{product_id}/status"
                    ),
                    headers=headers,
                    json={"status": "published"},
                )
                assert invalid_transition.status_code == 409

            audit_count = await session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.resource_type.in_(("category", "product"))
                )
            )
            assert audit_count == audit_count_before + 10
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def test_course_product_requires_manage_permission() -> None:
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
            store = make_store("课程权限测试门店")
            role = Role(code=f"course-readonly-{uuid4()}", name="只读角色")
            password = "test-password-2026"
            admin = AdminUser(
                username=f"course-readonly-{uuid4().hex}",
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
                    "Authorization": f"Bearer {login_response.json()['access_token']}"
                }
                response = await client.get(
                    f"/api/v1/admin/stores/{store.id}/categories",
                    headers=headers,
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def test_video_course_lifecycle_and_public_chapter_preview() -> None:
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
                select(Permission).where(Permission.code == "products:manage")
            )
            assert permission is not None
            role = Role(code=f"video-operator-{uuid4()}", name="视频课程运营")
            role.permissions.append(permission)
            password = "test-password-2026"
            admin = AdminUser(
                username=f"video-admin-{uuid4().hex}",
                password_hash=hash_password(password),
            )
            admin.roles.append(role)
            store = make_store("视频课程门店")
            admin.stores.append(store)
            session.add_all((admin, store))
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
                    "Authorization": f"Bearer {login_response.json()['access_token']}"
                }

                category_response = await client.post(
                    f"/api/v1/admin/stores/{store.id}/categories",
                    headers=headers,
                    json={"name": "视频课程", "sort_order": 10},
                )
                assert category_response.status_code == 201
                category_id = category_response.json()["id"]

                video_prefix = f"muyimusic/stores/{store.id}/products/videos/"

                # 线下课时课关联视频章节 → 422
                course_with_videos = await client.post(
                    f"/api/v1/admin/stores/{store.id}/products",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "name": "线下钢琴课",
                        "cover_object_key": (
                            f"muyimusic/stores/{store.id}/products/cover.jpg"
                        ),
                        "product_type": "course",
                        "skus": [
                            {
                                "name": "10 课时",
                                "price_cents": 168000,
                                "lesson_count": 10,
                                "validity_days": 180,
                            }
                        ],
                        "videos": [
                            {
                                "title": "第一章",
                                "object_key": f"{video_prefix}chapter1.mp4",
                                "sort_order": 10,
                            }
                        ],
                    },
                )
                assert course_with_videos.status_code == 422

                # 视频课程 SKU 课时数不为 0 → 422
                video_with_lessons = await client.post(
                    f"/api/v1/admin/stores/{store.id}/products",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "name": "钢琴视频课",
                        "cover_object_key": (
                            f"muyimusic/stores/{store.id}/products/cover.jpg"
                        ),
                        "product_type": "video",
                        "skus": [
                            {
                                "name": "全期",
                                "price_cents": 9900,
                                "lesson_count": 10,
                                "validity_days": 365,
                            }
                        ],
                        "videos": [
                            {
                                "title": "第一章",
                                "object_key": f"{video_prefix}chapter1.mp4",
                                "sort_order": 10,
                            }
                        ],
                    },
                )
                assert video_with_lessons.status_code == 422

                # 视频文件的 object_key 不在视频目录 → 422
                wrong_key = await client.post(
                    f"/api/v1/admin/stores/{store.id}/products",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "name": "钢琴视频课",
                        "cover_object_key": (
                            f"muyimusic/stores/{store.id}/products/cover.jpg"
                        ),
                        "product_type": "video",
                        "skus": [
                            {
                                "name": "全期",
                                "price_cents": 9900,
                                "lesson_count": 0,
                                "validity_days": 365,
                            }
                        ],
                        "videos": [
                            {
                                "title": "第一章",
                                "object_key": (
                                    f"muyimusic/stores/{store.id}/products/chapter1.mp4"
                                ),
                                "sort_order": 10,
                            }
                        ],
                    },
                )
                assert wrong_key.status_code == 422

                # 正常创建视频课程
                video_response = await client.post(
                    f"/api/v1/admin/stores/{store.id}/products",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "name": "钢琴视频课",
                        "summary": "录播教学",
                        "cover_object_key": (
                            f"muyimusic/stores/{store.id}/products/cover.jpg"
                        ),
                        "product_type": "video",
                        "skus": [
                            {
                                "name": "全期观看",
                                "price_cents": 9900,
                                "lesson_count": 0,
                                "validity_days": 365,
                                "sort_order": 10,
                            }
                        ],
                        "videos": [
                            {
                                "title": "第一章 认识键盘",
                                "object_key": f"{video_prefix}chapter1.mp4",
                                "duration_seconds": 720,
                                "sort_order": 10,
                            },
                            {
                                "title": "第二章 基础指法",
                                "object_key": f"{video_prefix}chapter2.mp4",
                                "duration_seconds": 840,
                                "sort_order": 20,
                            },
                        ],
                    },
                )
                assert video_response.status_code == 201
                video_product = video_response.json()
                assert video_product["product_type"] == "video"
                assert len(video_product["videos"]) == 2
                assert video_product["videos"][0]["title"] == "第一章 认识键盘"
                product_id = video_product["id"]
                video_id = video_product["videos"][0]["id"]
                video2_id = video_product["videos"][1]["id"]

                # 未发布 → 公开详情不可见
                hidden = await client.get(
                    f"/api/v1/app/stores/{store.id}/products/{product_id}"
                )
                assert hidden.status_code == 404

                # 视频课程没有章节不可发布
                no_chapter_product = await client.post(
                    f"/api/v1/admin/stores/{store.id}/products",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "name": "空视频课",
                        "cover_object_key": (
                            f"muyimusic/stores/{store.id}/products/cover.jpg"
                        ),
                        "product_type": "video",
                        "skus": [
                            {
                                "name": "全期",
                                "price_cents": 9900,
                                "lesson_count": 0,
                                "validity_days": 365,
                            }
                        ],
                    },
                )
                assert no_chapter_product.status_code == 201
                no_chapter_id = no_chapter_product.json()["id"]
                empty_publish = await client.post(
                    f"/api/v1/admin/stores/{store.id}/products/{no_chapter_id}/status",
                    headers=headers,
                    json={"status": "published"},
                )
                assert empty_publish.status_code == 409

                publish_response = await client.post(
                    f"/api/v1/admin/stores/{store.id}/products/{product_id}/status",
                    headers=headers,
                    json={"status": "published"},
                )
                assert publish_response.status_code == 200

                # 公开详情返回章节预览，不含播放地址
                public_response = await client.get(
                    f"/api/v1/app/stores/{store.id}/products/{product_id}"
                )
                assert public_response.status_code == 200
                public_product = public_response.json()
                assert public_product["product_type"] == "video"
                assert len(public_product["video_chapters"]) == 2
                chapter = public_product["video_chapters"][0]
                assert chapter["title"] == "第一章 认识键盘"
                assert chapter["duration_seconds"] == 720
                assert "video_url" not in chapter
                assert "object_key" not in chapter

                # 列表项带视频章节数
                list_response = await client.get(
                    f"/api/v1/app/stores/{store.id}/products",
                    params={"keyword": "钢琴视频课"},
                )
                assert list_response.status_code == 200
                assert list_response.json()["items"][0]["video_chapter_count"] == 2

                # 更新：禁用第一章、新增第三章（全量提交，未提交的第二章保持启用）
                update_response = await client.patch(
                    f"/api/v1/admin/stores/{store.id}/products/{product_id}",
                    headers=headers,
                    json={
                        "videos": [
                            {
                                "id": video_id,
                                "title": "第一章 认识键盘",
                                "object_key": f"{video_prefix}chapter1.mp4",
                                "duration_seconds": 720,
                                "sort_order": 10,
                                "is_active": False,
                            },
                            {
                                "id": video2_id,
                                "title": "第二章 指法练习",
                                "object_key": f"{video_prefix}chapter2.mp4",
                                "duration_seconds": 840,
                                "sort_order": 20,
                            },
                            {
                                "title": "第三章 和声入门",
                                "object_key": f"{video_prefix}chapter3.mp4",
                                "duration_seconds": 900,
                                "sort_order": 30,
                            },
                        ]
                    },
                )
                assert update_response.status_code == 200
                assert len(update_response.json()["videos"]) == 3
                assert (
                    sum(
                        video["is_active"] for video in update_response.json()["videos"]
                    )
                    == 2
                )

                # 更新后公开详情章节数为 2（禁用章节不展示）
                public_after = await client.get(
                    f"/api/v1/app/stores/{store.id}/products/{product_id}"
                )
                assert len(public_after.json()["video_chapters"]) == 2
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
