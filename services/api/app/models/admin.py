from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.store import Store

admin_user_roles = Table(
    "admin_user_roles",
    Base.metadata,
    Column(
        "admin_user_id",
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

admin_user_stores = Table(
    "admin_user_stores",
    Base.metadata,
    Column(
        "admin_user_id",
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "store_id",
        ForeignKey("stores.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    roles: Mapped[list["Role"]] = relationship(
        secondary=admin_user_roles,
        back_populates="admin_users",
        lazy="selectin",
    )
    stores: Mapped[list["Store"]] = relationship(
        secondary=admin_user_stores,
        back_populates="authorized_admins",
        lazy="selectin",
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    admin_users: Mapped[list[AdminUser]] = relationship(
        secondary=admin_user_roles,
        back_populates="roles",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions,
        back_populates="permissions",
    )
