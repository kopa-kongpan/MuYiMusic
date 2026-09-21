"""共享测试基建。

现有测试每个用例都手写一遍「connect → begin → AsyncSession(create_savepoint)
→ override get_session → finally rollback」的 15 行样板。这里把它收成
`api_context()`，新测试直接用，老测试不受影响（本文件只新增，不改写既有用法）。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_engine, get_session
from app.core.security import hash_password
from app.main import app
from app.models.admin import AdminUser, Permission, Role
from app.models.product import Category, Product, ProductStatus
from app.models.schedule import ClassSchedule, Teacher
from app.models.store import Store
from app.models.user import CourseEntitlement, EntitlementStatus, User
from app.services.auth_service import PLATFORM_ADMIN_ROLE_CODE

TEST_PASSWORD = "test-password-2026"


@dataclass
class ApiContext:
    """一个用例内共用的 session + client。"""

    session: AsyncSession
    client: AsyncClient


@asynccontextmanager
async def api_context() -> AsyncIterator[ApiContext]:
    """提供事务隔离的 session 与绑定了依赖覆盖的 HTTP client。

    退出时回滚事务，因此用例之间不会互相污染数据。
    """
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
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                yield ApiContext(session=session, client=client)
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


def make_store(name: str) -> Store:
    return Store(
        name=name,
        city="深圳市",
        district="南山区",
        address="测试路 100 号",
        phone="0755-12345678",
        latitude=Decimal("22.543096"),
        longitude=Decimal("114.057865"),
    )


async def make_admin(
    session: AsyncSession,
    *,
    permission_codes: tuple[str, ...],
    stores: tuple[Store, ...],
    label: str = "admin",
) -> AdminUser:
    """建一个持有指定权限码、并被授权到指定门店的管理员。"""
    permissions: list[Permission] = []
    if permission_codes:
        permissions = list(
            (
                await session.scalars(
                    select(Permission).where(Permission.code.in_(permission_codes))
                )
            ).all()
        )
        assert len(permissions) == len(permission_codes), (
            f"权限码缺失：期望 {permission_codes}，"
            f"实际 {[item.code for item in permissions]}"
        )

    role = Role(code=f"{label}-{uuid4()}", name=f"{label} 角色")
    role.permissions.extend(permissions)
    admin = AdminUser(
        username=f"{label}-{uuid4().hex}",
        password_hash=hash_password(TEST_PASSWORD),
    )
    admin.roles.append(role)
    admin.stores.extend(stores)
    session.add(admin)
    await session.flush()
    return admin


async def login_admin(client: AsyncClient, admin: AdminUser) -> dict[str, str]:
    response = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": admin.username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
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
            "code": f"test-{uuid4().hex}",
            "nickname": nickname,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    user = await session.get(User, UUID(payload["user"]["id"]))
    assert user is not None
    return user, {"Authorization": f"Bearer {payload['access_token']}"}


def make_product(store: Store, *, name: str = "少儿钢琴课") -> Product:
    return Product(
        store_id=store.id,
        category=Category(store_id=store.id, name=f"{name}分类"),
        name=name,
        cover_object_key="tests/cover.jpg",
        status=ProductStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )


def make_schedule(
    *,
    store: Store,
    product: Product,
    teacher: Teacher,
    starts_at: datetime,
    capacity: int = 2,
    course_name: str = "少儿钢琴课",
    duration: timedelta = timedelta(hours=1),
) -> ClassSchedule:
    return ClassSchedule(
        store_id=store.id,
        product_id=product.id,
        teacher=teacher,
        course_name=course_name,
        starts_at=starts_at,
        ends_at=starts_at + duration,
        capacity=capacity,
    )


def make_entitlement(
    *,
    user: User,
    store: Store,
    product: Product,
    lessons: int = 4,
    valid_from: datetime | None = None,
    expires_at: datetime | None = None,
    status: EntitlementStatus = EntitlementStatus.ACTIVE,
) -> CourseEntitlement:
    now = datetime.now(UTC)
    return CourseEntitlement(
        user=user,
        store_id=store.id,
        product_id=product.id,
        course_name=product.name,
        total_lessons=lessons,
        remaining_lessons=lessons,
        valid_from=valid_from if valid_from is not None else now - timedelta(days=1),
        expires_at=expires_at if expires_at is not None else now + timedelta(days=180),
        status=status,
    )


@dataclass
class BookingWorld:
    """预约类测试的常用底座：门店 + 商品 + 教师 + 有权限的管理员。"""

    store: Store
    other_store: Store
    product: Product
    teacher: Teacher
    admin: AdminUser


async def build_booking_world(
    session: AsyncSession,
    *,
    permission_codes: tuple[str, ...] = (
        "appointments:manage",
        "consumptions:manage",
        "consumptions:reverse",
        "schedules:manage",
    ),
) -> BookingWorld:
    store = make_store(f"授权门店-{uuid4().hex[:8]}")
    other_store = make_store(f"未授权门店-{uuid4().hex[:8]}")
    session.add_all((store, other_store))
    await session.flush()

    product = make_product(store)
    teacher = Teacher(store_id=store.id, name=f"教师-{uuid4().hex[:8]}")
    session.add_all((product, teacher))
    await session.flush()

    admin = await make_admin(
        session,
        permission_codes=permission_codes,
        stores=(store,),
        label="booking-admin",
    )
    return BookingWorld(
        store=store,
        other_store=other_store,
        product=product,
        teacher=teacher,
        admin=admin,
    )


async def make_platform_admin(
    session: AsyncSession,
    *,
    label: str = "platform-admin",
) -> AdminUser:
    """建一个平台管理员。

    平台域不是靠权限码判定的，而是靠角色码等于 `platform_admin`
    （见 auth_service.has_platform_scope），所以这里复用库里已经播种的
    那条角色记录，而不是新建一个同码角色（code 有唯一约束）。
    """
    role = await session.scalar(
        select(Role).where(Role.code == PLATFORM_ADMIN_ROLE_CODE)
    )
    assert role is not None, (
        f"数据库缺少 {PLATFORM_ADMIN_ROLE_CODE} 角色，"
        "请先执行 scripts/bootstrap_admin.py 播种"
    )
    admin = AdminUser(
        username=f"{label}-{uuid4().hex}",
        password_hash=hash_password(TEST_PASSWORD),
    )
    admin.roles.append(role)
    session.add(admin)
    await session.flush()
    return admin
