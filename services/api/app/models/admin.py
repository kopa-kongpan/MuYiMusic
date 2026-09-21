from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    func,
)
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
    # Index 必须放在它引用的 Column 之后，否则建表时列还不存在。
    # 这条索引迁移里已有，模型不声明的话 autogenerate 会 drop 掉。
    Index("ix_admin_user_stores_store_id", "store_id"),
)


class AdminUser(Base):
    __tablename__ = "admin_users"
    # 建表迁移里有一条独立命名的唯一约束（20260803_0001 的
    # sa.UniqueConstraint("username")），和下面 username 列上的
    # unique=True 各自生成了一个唯一索引。这里如实声明，否则
    # autogenerate 会判定它「已被移除」并生成 drop_constraint。
    # 两者语义重复，可在后续单独的清理迁移里去掉一个。
    __table_args__ = (UniqueConstraint("username", name="admin_users_username_key"),)

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
