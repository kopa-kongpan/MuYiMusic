"""add product type video courses and order idempotency keys

Revision ID: 20260806_0008
Revises: 20260805_0007
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0008"
down_revision: str | None = "20260805_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

product_type = postgresql.ENUM(
    "course",
    "video",
    name="product_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("course", "video", name="product_type").create(
        bind,
        checkfirst=True,
    )

    op.add_column(
        "products",
        sa.Column(
            "product_type",
            product_type,
            server_default="course",
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_products_product_type"), "products", ["product_type"])

    op.add_column(
        "order_items",
        sa.Column(
            "product_type",
            product_type,
            server_default="course",
            nullable=False,
        ),
    )
    op.add_column(
        "course_entitlements",
        sa.Column(
            "product_type",
            product_type,
            server_default="course",
            nullable=False,
        ),
    )

    op.drop_constraint(
        "ck_product_skus_lesson_count",
        "product_skus",
        type_="check",
    )
    op.create_check_constraint(
        "ck_product_skus_lesson_count",
        "product_skus",
        "lesson_count >= 0",
    )

    op.drop_constraint(
        "ck_order_items_lesson_count",
        "order_items",
        type_="check",
    )
    op.create_check_constraint(
        "ck_order_items_lesson_count",
        "order_items",
        "lesson_count >= 0",
    )

    op.drop_constraint(
        "ck_entitlements_total_lessons",
        "course_entitlements",
        type_="check",
    )
    op.create_check_constraint(
        "ck_entitlements_total_lessons",
        "course_entitlements",
        "total_lessons >= 0",
    )

    op.add_column(
        "orders",
        sa.Column("create_idempotency_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("pay_idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_unique_constraint(
        "uq_orders_user_create_key",
        "orders",
        ["user_id", "create_idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_orders_user_pay_key",
        "orders",
        ["user_id", "pay_idempotency_key"],
    )

    op.create_table(
        "product_videos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
        sa.CheckConstraint("sort_order >= 0", name="ck_product_videos_sort_order"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_videos_product_id"),
        "product_videos",
        ["product_id"],
    )
    op.create_index(
        op.f("ix_product_videos_is_active"),
        "product_videos",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_product_videos_is_active"), table_name="product_videos")
    op.drop_index(op.f("ix_product_videos_product_id"), table_name="product_videos")
    op.drop_table("product_videos")

    op.drop_constraint(
        "uq_orders_user_pay_key",
        "orders",
        type_="unique",
    )
    op.drop_constraint(
        "uq_orders_user_create_key",
        "orders",
        type_="unique",
    )
    op.drop_column("orders", "pay_idempotency_key")
    op.drop_column("orders", "create_idempotency_key")

    op.drop_constraint(
        "ck_entitlements_total_lessons",
        "course_entitlements",
        type_="check",
    )
    op.create_check_constraint(
        "ck_entitlements_total_lessons",
        "course_entitlements",
        "total_lessons > 0",
    )

    op.drop_constraint(
        "ck_order_items_lesson_count",
        "order_items",
        type_="check",
    )
    op.create_check_constraint(
        "ck_order_items_lesson_count",
        "order_items",
        "lesson_count > 0",
    )

    op.drop_constraint(
        "ck_product_skus_lesson_count",
        "product_skus",
        type_="check",
    )
    op.create_check_constraint(
        "ck_product_skus_lesson_count",
        "product_skus",
        "lesson_count > 0",
    )

    op.drop_column("course_entitlements", "product_type")
    op.drop_column("order_items", "product_type")
    op.drop_index(op.f("ix_products_product_type"), table_name="products")
    op.drop_column("products", "product_type")

    bind = op.get_bind()
    postgresql.ENUM(name="product_type").drop(bind, checkfirst=True)
