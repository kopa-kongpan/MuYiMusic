import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.security import hash_password
from app.models.admin import AdminUser, Permission, Role

PERMISSIONS = {
    "stores:manage": "管理门店",
    "store_content:manage": "管理门店首页内容",
    "products:manage": "管理课程商品",
    "users:read": "查询用户订单与课程权益",
    "schedules:manage": "管理教师与排课",
    "appointments:manage": "管理预约",
    "consumptions:manage": "执行消课与缺席",
    "consumptions:reverse": "撤销消课",
    "admins:manage": "管理运营账号",
}
PLATFORM_ADMIN_ROLE_CODE = "platform_admin"
STORE_OPERATOR_ROLE_CODE = "store_operator"
STORE_OPERATOR_PERMISSION_CODES = (
    "store_content:manage",
    "products:manage",
    "users:read",
    "schedules:manage",
    "appointments:manage",
    "consumptions:manage",
)


async def bootstrap_admin(username: str, password: str) -> bool:
    async with get_session_factory()() as session:
        existing_user = await session.scalar(
            select(AdminUser)
            .where(AdminUser.username == username)
            .options(selectinload(AdminUser.roles))
        )
        permissions: list[Permission] = []
        for code, name in PERMISSIONS.items():
            permission = await session.scalar(
                select(Permission).where(Permission.code == code)
            )
            if permission is None:
                permission = Permission(code=code, name=name)
                session.add(permission)
            permissions.append(permission)

        role = await session.scalar(
            select(Role)
            .where(Role.code == PLATFORM_ADMIN_ROLE_CODE)
            .options(selectinload(Role.permissions))
        )
        if role is None:
            role = Role(
                code=PLATFORM_ADMIN_ROLE_CODE,
                name="平台管理员",
            )
            session.add(role)
        for permission in permissions:
            if permission not in role.permissions:
                role.permissions.append(permission)

        operator_role = await session.scalar(
            select(Role)
            .where(Role.code == STORE_OPERATOR_ROLE_CODE)
            .options(selectinload(Role.permissions))
        )
        if operator_role is None:
            operator_role = Role(code=STORE_OPERATOR_ROLE_CODE, name="门店运营")
            session.add(operator_role)
        operator_permissions = [
            permission
            for permission in permissions
            if permission.code in STORE_OPERATOR_PERMISSION_CODES
        ]
        for permission in operator_permissions:
            if permission not in operator_role.permissions:
                operator_role.permissions.append(permission)

        if existing_user is not None:
            if role not in existing_user.roles:
                existing_user.roles.append(role)
            await session.commit()
            return False

        admin_user = AdminUser(
            username=username,
            password_hash=hash_password(password),
        )
        admin_user.roles.append(role)
        session.add(admin_user)
        await session.commit()
        return True


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Create the first admin user")
    parser.add_argument(
        "--username",
        default=settings.admin_initial_username,
    )
    return parser.parse_args()


def main() -> None:
    settings = get_settings()
    args = parse_args()
    password = settings.admin_initial_password
    if password is None or len(password) < 12:
        raise SystemExit("ADMIN_INITIAL_PASSWORD must contain at least 12 characters")
    was_created = asyncio.run(bootstrap_admin(args.username, password))
    if was_created:
        print(f"Created admin user: {args.username}")
        return
    print(f"Admin user already exists: {args.username}")


if __name__ == "__main__":
    main()
