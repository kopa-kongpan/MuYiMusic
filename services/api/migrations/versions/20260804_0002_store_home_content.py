"""add store authorization and home content

Revision ID: 20260804_0002
Revises: 20260803_0001
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0002"
down_revision: str | None = "20260803_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

content_block_type = postgresql.ENUM(
    "image",
    "video",
    "shortcut",
    name="content_block_type",
    create_type=False,
)
content_block_status = postgresql.ENUM(
    "enabled",
    "disabled",
    name="content_block_status",
    create_type=False,
)
content_jump_type = postgresql.ENUM(
    "none",
    "internal",
    "web_url",
    name="content_jump_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "image",
        "video",
        "shortcut",
        name="content_block_type",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "enabled",
        "disabled",
        name="content_block_status",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "none",
        "internal",
        "web_url",
        name="content_jump_type",
    ).create(bind, checkfirst=True)

    op.create_table(
        "admin_user_stores",
        sa.Column("admin_user_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["admin_users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("admin_user_id", "store_id"),
    )
    op.create_index(
        op.f("ix_admin_user_stores_store_id"),
        "admin_user_stores",
        ["store_id"],
        unique=False,
    )

    op.create_table(
        "store_content_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("block_type", content_block_type, nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("media_object_key", sa.String(length=1024), nullable=True),
        sa.Column(
            "jump_type",
            content_jump_type,
            server_default="none",
            nullable=False,
        ),
        sa.Column("jump_target", sa.String(length=500), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "status",
            content_block_status,
            server_default="enabled",
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR starts_at < ends_at",
            name="ck_store_content_blocks_display_window",
        ),
        sa.CheckConstraint(
            "block_type = 'shortcut' OR media_object_key IS NOT NULL",
            name="ck_store_content_blocks_media_required",
        ),
        sa.CheckConstraint(
            "block_type <> 'shortcut' OR "
            "(jump_type <> 'none' AND jump_target IS NOT NULL)",
            name="ck_store_content_blocks_shortcut_target",
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_store_content_blocks_block_type"),
        "store_content_blocks",
        ["block_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_store_content_blocks_status"),
        "store_content_blocks",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_store_content_blocks_store_id"),
        "store_content_blocks",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_store_content_blocks_public",
        "store_content_blocks",
        ["store_id", "status", "sort_order"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO permissions (id, code, name)
            VALUES (
                '7b8818ee-8527-42be-a3f6-0cdb08a2d23f',
                'store_content:manage',
                '管理门店首页内容'
            )
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT roles.id, permissions.id
            FROM roles
            JOIN permissions ON permissions.code = 'store_content:manage'
            WHERE roles.code = 'platform_admin'
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            USING permissions
            WHERE role_permissions.permission_id = permissions.id
              AND permissions.code = 'store_content:manage'
            """
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'store_content:manage'"))
    op.drop_index("ix_store_content_blocks_public", table_name="store_content_blocks")
    op.drop_index(
        op.f("ix_store_content_blocks_store_id"),
        table_name="store_content_blocks",
    )
    op.drop_index(
        op.f("ix_store_content_blocks_status"),
        table_name="store_content_blocks",
    )
    op.drop_index(
        op.f("ix_store_content_blocks_block_type"),
        table_name="store_content_blocks",
    )
    op.drop_table("store_content_blocks")
    op.drop_index(op.f("ix_admin_user_stores_store_id"), table_name="admin_user_stores")
    op.drop_table("admin_user_stores")
    content_jump_type.drop(op.get_bind(), checkfirst=True)
    content_block_status.drop(op.get_bind(), checkfirst=True)
    content_block_type.drop(op.get_bind(), checkfirst=True)
