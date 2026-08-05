"""add course product catalog

Revision ID: 20260804_0003
Revises: 20260804_0002
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0003"
down_revision: str | None = "20260804_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

product_status = postgresql.ENUM(
    "draft",
    "published",
    "offline",
    "archived",
    name="product_status",
    create_type=False,
)


def upgrade() -> None:
    postgresql.ENUM(
        "draft",
        "published",
        "offline",
        "archived",
        name="product_status",
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "is_enabled",
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
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "name", name="uq_categories_store_name"),
    )
    op.create_index(op.f("ix_categories_store_id"), "categories", ["store_id"])
    op.create_index(op.f("ix_categories_is_enabled"), "categories", ["is_enabled"])
    op.create_index(
        "ix_categories_store_public",
        "categories",
        ["store_id", "is_enabled", "sort_order"],
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.String(length=300), server_default="", nullable=False),
        sa.Column("details", sa.Text(), server_default="", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cover_object_key", sa.String(length=1024), nullable=False),
        sa.Column(
            "status",
            product_status,
            server_default="draft",
            nullable=False,
        ),
        sa.Column("sale_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sale_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sales_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("sales_count >= 0", name="ck_products_sales_count"),
        sa.CheckConstraint("sort_order >= 0", name="ck_products_sort_order"),
        sa.CheckConstraint(
            "sale_starts_at IS NULL OR sale_ends_at IS NULL "
            "OR sale_starts_at < sale_ends_at",
            name="ck_products_sale_window",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_products_category_id"), "products", ["category_id"])
    op.create_index(op.f("ix_products_name"), "products", ["name"])
    op.create_index(op.f("ix_products_status"), "products", ["status"])
    op.create_index(op.f("ix_products_store_id"), "products", ["store_id"])
    op.create_index(
        "ix_products_public",
        "products",
        ["store_id", "status", "sort_order"],
    )

    op.create_table(
        "product_skus",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("lesson_count", sa.Integer(), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("price_cents >= 0", name="ck_product_skus_price"),
        sa.CheckConstraint("lesson_count > 0", name="ck_product_skus_lesson_count"),
        sa.CheckConstraint("validity_days > 0", name="ck_product_skus_validity_days"),
        sa.CheckConstraint("sort_order >= 0", name="ck_product_skus_sort_order"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_skus_product_id"),
        "product_skus",
        ["product_id"],
    )
    op.create_index(
        op.f("ix_product_skus_is_active"),
        "product_skus",
        ["is_active"],
    )

    op.create_table(
        "product_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_product_images_sort_order"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_images_product_id"),
        "product_images",
        ["product_id"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO permissions (id, code, name)
            VALUES (
                'ff6a9449-f41f-4d40-aad1-8d55a228b38e',
                'products:manage',
                '管理课程商品'
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
            JOIN permissions ON permissions.code = 'products:manage'
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
              AND permissions.code = 'products:manage'
            """
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'products:manage'"))
    op.drop_index(op.f("ix_product_images_product_id"), table_name="product_images")
    op.drop_table("product_images")
    op.drop_index(op.f("ix_product_skus_is_active"), table_name="product_skus")
    op.drop_index(op.f("ix_product_skus_product_id"), table_name="product_skus")
    op.drop_table("product_skus")
    op.drop_index("ix_products_public", table_name="products")
    op.drop_index(op.f("ix_products_store_id"), table_name="products")
    op.drop_index(op.f("ix_products_status"), table_name="products")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_index(op.f("ix_products_category_id"), table_name="products")
    op.drop_table("products")
    op.drop_index("ix_categories_store_public", table_name="categories")
    op.drop_index(op.f("ix_categories_is_enabled"), table_name="categories")
    op.drop_index(op.f("ix_categories_store_id"), table_name="categories")
    op.drop_table("categories")
    product_status.drop(op.get_bind(), checkfirst=True)
