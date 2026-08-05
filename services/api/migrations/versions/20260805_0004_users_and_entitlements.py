"""add users orders and course entitlements

Revision ID: 20260805_0004
Revises: 20260804_0003
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0004"
down_revision: str | None = "20260804_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_status = postgresql.ENUM(
    "active",
    "disabled",
    name="user_status",
    create_type=False,
)
identity_provider = postgresql.ENUM(
    "weapp",
    "tt",
    "h5",
    name="identity_provider",
    create_type=False,
)
order_status = postgresql.ENUM(
    "pending",
    "confirmed",
    "cancelled",
    name="order_status",
    create_type=False,
)
entitlement_status = postgresql.ENUM(
    "active",
    "exhausted",
    "expired",
    name="entitlement_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        postgresql.ENUM("active", "disabled", name="user_status"),
        postgresql.ENUM("weapp", "tt", "h5", name="identity_provider"),
        postgresql.ENUM("pending", "confirmed", "cancelled", name="order_status"),
        postgresql.ENUM("active", "exhausted", "expired", name="entitlement_status"),
    ):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nickname", sa.String(length=128), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            user_status,
            server_default="active",
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index(op.f("ix_users_status"), "users", ["status"])

    op.create_table(
        "provider_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", identity_provider, nullable=False),
        sa.Column("provider_subject", sa.String(length=128), nullable=False),
        sa.Column("union_subject", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_provider_accounts_identity",
        ),
    )
    op.create_index(
        op.f("ix_provider_accounts_provider"),
        "provider_accounts",
        ["provider"],
    )
    op.create_index(
        op.f("ix_provider_accounts_union_subject"),
        "provider_accounts",
        ["union_subject"],
    )
    op.create_index(
        op.f("ix_provider_accounts_user_id"),
        "provider_accounts",
        ["user_id"],
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            order_status,
            server_default="pending",
            nullable=False,
        ),
        sa.Column("total_amount_cents", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("total_amount_cents >= 0", name="ck_orders_total_amount"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_no"),
    )
    op.create_index(op.f("ix_orders_status"), "orders", ["status"])
    op.create_index(op.f("ix_orders_store_id"), "orders", ["store_id"])
    op.create_index(op.f("ix_orders_user_id"), "orders", ["user_id"])
    op.create_index(
        "ix_orders_user_store_created",
        "orders",
        ["user_id", "store_id", "created_at"],
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("product_sku_id", sa.Uuid(), nullable=True),
        sa.Column("product_name", sa.String(length=128), nullable=False),
        sa.Column("sku_name", sa.String(length=128), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("total_amount_cents", sa.Integer(), nullable=False),
        sa.Column("lesson_count", sa.Integer(), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=False),
        sa.CheckConstraint("unit_price_cents >= 0", name="ck_order_items_unit_price"),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity"),
        sa.CheckConstraint(
            "total_amount_cents >= 0",
            name="ck_order_items_total_amount",
        ),
        sa.CheckConstraint("lesson_count > 0", name="ck_order_items_lesson_count"),
        sa.CheckConstraint("validity_days > 0", name="ck_order_items_validity_days"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_sku_id"],
            ["product_skus.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"])
    op.create_index(
        op.f("ix_order_items_product_id"),
        "order_items",
        ["product_id"],
    )
    op.create_index(
        op.f("ix_order_items_product_sku_id"),
        "order_items",
        ["product_sku_id"],
    )

    op.create_table(
        "course_entitlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=True),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("product_sku_id", sa.Uuid(), nullable=True),
        sa.Column("course_name", sa.String(length=128), nullable=False),
        sa.Column("total_lessons", sa.Integer(), nullable=False),
        sa.Column("remaining_lessons", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            entitlement_status,
            server_default="active",
            nullable=False,
        ),
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
        sa.CheckConstraint("total_lessons > 0", name="ck_entitlements_total_lessons"),
        sa.CheckConstraint(
            "remaining_lessons >= 0 AND remaining_lessons <= total_lessons",
            name="ck_entitlements_remaining_lessons",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > valid_from",
            name="ck_entitlements_valid_window",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_sku_id"],
            ["product_skus.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_item_id"),
    )
    op.create_index(
        op.f("ix_course_entitlements_product_id"),
        "course_entitlements",
        ["product_id"],
    )
    op.create_index(
        op.f("ix_course_entitlements_product_sku_id"),
        "course_entitlements",
        ["product_sku_id"],
    )
    op.create_index(
        op.f("ix_course_entitlements_status"),
        "course_entitlements",
        ["status"],
    )
    op.create_index(
        op.f("ix_course_entitlements_store_id"),
        "course_entitlements",
        ["store_id"],
    )
    op.create_index(
        op.f("ix_course_entitlements_user_id"),
        "course_entitlements",
        ["user_id"],
    )
    op.create_index(
        "ix_entitlements_user_store_status",
        "course_entitlements",
        ["user_id", "store_id", "status"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO permissions (id, code, name)
            VALUES (
                '737997e9-8d5c-4475-bc45-81fd7620820b',
                'users:read',
                '查询用户订单与课程权益'
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
            JOIN permissions ON permissions.code = 'users:read'
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
              AND permissions.code = 'users:read'
            """
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'users:read'"))
    op.drop_index("ix_entitlements_user_store_status", table_name="course_entitlements")
    op.drop_index(
        op.f("ix_course_entitlements_user_id"),
        table_name="course_entitlements",
    )
    op.drop_index(
        op.f("ix_course_entitlements_store_id"),
        table_name="course_entitlements",
    )
    op.drop_index(
        op.f("ix_course_entitlements_status"),
        table_name="course_entitlements",
    )
    op.drop_index(
        op.f("ix_course_entitlements_product_sku_id"),
        table_name="course_entitlements",
    )
    op.drop_index(
        op.f("ix_course_entitlements_product_id"),
        table_name="course_entitlements",
    )
    op.drop_table("course_entitlements")
    op.drop_index(op.f("ix_order_items_product_sku_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_product_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_user_store_created", table_name="orders")
    op.drop_index(op.f("ix_orders_user_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_store_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_table("orders")
    op.drop_index(op.f("ix_provider_accounts_user_id"), table_name="provider_accounts")
    op.drop_index(
        op.f("ix_provider_accounts_union_subject"),
        table_name="provider_accounts",
    )
    op.drop_index(op.f("ix_provider_accounts_provider"), table_name="provider_accounts")
    op.drop_table("provider_accounts")
    op.drop_index(op.f("ix_users_status"), table_name="users")
    op.drop_table("users")
    entitlement_status.drop(op.get_bind(), checkfirst=True)
    order_status.drop(op.get_bind(), checkfirst=True)
    identity_provider.drop(op.get_bind(), checkfirst=True)
    user_status.drop(op.get_bind(), checkfirst=True)
