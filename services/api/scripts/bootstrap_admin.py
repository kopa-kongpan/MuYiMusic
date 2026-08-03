import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.security import hash_password
from app.models.admin import AdminUser, Permission, Role

STORE_PERMISSION_CODE = "stores:manage"
PLATFORM_ADMIN_ROLE_CODE = "platform_admin"


async def bootstrap_admin(username: str, password: str) -> bool:
    async with get_session_factory()() as session:
        existing_user = await session.scalar(
            select(AdminUser).where(AdminUser.username == username)
        )
        if existing_user is not None:
            return False

        permission = await session.scalar(
            select(Permission).where(Permission.code == STORE_PERMISSION_CODE)
        )
        if permission is None:
            permission = Permission(
                code=STORE_PERMISSION_CODE,
                name="管理门店",
            )
            session.add(permission)

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
        if permission not in role.permissions:
            role.permissions.append(permission)

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
