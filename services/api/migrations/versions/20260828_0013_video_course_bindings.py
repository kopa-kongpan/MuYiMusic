"""split video courses from offline course products

Revision ID: 20260828_0013
Revises: 20260827_0012
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260828_0013"
down_revision: str | None = "20260827_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

access_mode = postgresql.ENUM(
    "all",
    "selected",
    name="video_course_access_mode",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("all", "selected", name="video_course_access_mode").create(
        bind,
        checkfirst=True,
    )
    op.create_table(
        "video_courses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.String(length=300), server_default="", nullable=False),
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
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "store_id",
            "name",
            name="uq_video_courses_store_name",
        ),
    )
    op.create_index(op.f("ix_video_courses_store_id"), "video_courses", ["store_id"])
    op.create_index(
        op.f("ix_video_courses_category_id"),
        "video_courses",
        ["category_id"],
    )
    op.create_index(op.f("ix_video_courses_name"), "video_courses", ["name"])
    op.create_index(
        op.f("ix_video_courses_is_active"),
        "video_courses",
        ["is_active"],
    )

    op.create_table(
        "video_course_lessons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_course_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
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
        sa.CheckConstraint(
            "lesson_number > 0",
            name="ck_video_course_lessons_lesson_number",
        ),
        sa.ForeignKeyConstraint(
            ["video_course_id"],
            ["video_courses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "video_course_id",
            "lesson_number",
            name="uq_video_course_lessons_number",
        ),
    )
    op.create_index(
        op.f("ix_video_course_lessons_video_course_id"),
        "video_course_lessons",
        ["video_course_id"],
    )
    op.create_index(
        op.f("ix_video_course_lessons_is_active"),
        "video_course_lessons",
        ["is_active"],
    )

    op.create_table(
        "product_video_course_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("video_course_id", sa.Uuid(), nullable=False),
        sa.Column("access_mode", access_mode, server_default="all", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_course_id"],
            ["video_courses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id",
            "video_course_id",
            name="uq_product_video_course_bindings_course",
        ),
    )
    op.create_index(
        op.f("ix_product_video_course_bindings_product_id"),
        "product_video_course_bindings",
        ["product_id"],
    )
    op.create_index(
        op.f("ix_product_video_course_bindings_video_course_id"),
        "product_video_course_bindings",
        ["video_course_id"],
    )
    op.create_table(
        "product_video_course_binding_lessons",
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("video_course_lesson_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["product_video_course_bindings.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_course_lesson_id"],
            ["video_course_lessons.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("binding_id", "video_course_lesson_id"),
    )

    legacy_products = bind.execute(
        sa.text(
            """
            SELECT id, store_id, category_id, name, summary, created_at, updated_at
            FROM products
            WHERE product_type = 'video'
            ORDER BY created_at, id
            """
        )
    ).mappings()
    for product in legacy_products:
        video_course_id = uuid4()
        binding_id = uuid4()
        bind.execute(
            sa.text(
                """
                INSERT INTO video_courses
                    (id, store_id, category_id, name, summary, is_active,
                     created_at, updated_at)
                VALUES
                    (:id, :store_id, :category_id, :name, :summary, true,
                     :created_at, :updated_at)
                """
            ),
            {
                "id": video_course_id,
                "store_id": product["store_id"],
                "category_id": product["category_id"],
                "name": (f"{product['name']}（历史视频-{str(product['id'])[:8]}）"),
                "summary": product["summary"],
                "created_at": product["created_at"],
                "updated_at": product["updated_at"],
            },
        )
        videos = list(
            bind.execute(
                sa.text(
                    """
                    SELECT id, title, object_key, duration_seconds, is_active,
                           created_at, updated_at
                    FROM product_videos
                    WHERE product_id = :product_id
                    ORDER BY sort_order, created_at, id
                    """
                ),
                {"product_id": product["id"]},
            ).mappings()
        )
        for lesson_number, video in enumerate(videos, start=1):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO video_course_lessons
                        (id, video_course_id, lesson_number, title, object_key,
                         duration_seconds, is_active, created_at, updated_at)
                    VALUES
                        (:id, :video_course_id, :lesson_number, :title, :object_key,
                         :duration_seconds, :is_active, :created_at, :updated_at)
                    """
                ),
                {
                    **video,
                    "video_course_id": video_course_id,
                    "lesson_number": lesson_number,
                },
            )
        bind.execute(
            sa.text(
                """
                INSERT INTO product_video_course_bindings
                    (id, product_id, video_course_id, access_mode, created_at)
                VALUES (:id, :product_id, :video_course_id, 'all', :created_at)
                """
            ),
            {
                "id": binding_id,
                "product_id": product["id"],
                "video_course_id": video_course_id,
                "created_at": product["created_at"],
            },
        )
        fallback_lessons = max(len(videos), 1)
        bind.execute(
            sa.text(
                """
                UPDATE product_skus
                SET lesson_count = :fallback_lessons
                WHERE product_id = :product_id AND lesson_count = 0
                """
            ),
            {
                "product_id": product["id"],
                "fallback_lessons": fallback_lessons,
            },
        )

    bind.execute(
        sa.text(
            "UPDATE products SET product_type = 'course' WHERE product_type = 'video'"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE order_items SET product_type = 'course' "
            "WHERE product_type = 'video'"
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE order_items oi
            SET lesson_count = GREATEST(COALESCE(ps.lesson_count, 1), 1)
            FROM product_skus ps
            WHERE oi.product_sku_id = ps.id AND oi.lesson_count = 0
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE order_items SET lesson_count = 1
            WHERE lesson_count = 0
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE course_entitlements ce
            SET product_type = 'course',
                total_lessons = GREATEST(COALESCE(ps.lesson_count, 1), 1),
                remaining_lessons = GREATEST(COALESCE(ps.lesson_count, 1), 1),
                status = CASE
                    WHEN ce.status = 'exhausted' THEN 'active'
                    ELSE ce.status
                END
            FROM product_skus ps
            WHERE ce.product_sku_id = ps.id AND ce.total_lessons = 0
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE course_entitlements
            SET product_type = 'course', total_lessons = 1, remaining_lessons = 1,
                status = CASE WHEN status = 'exhausted' THEN 'active' ELSE status END
            WHERE total_lessons = 0
            """
        )
    )
    bind.execute(
        sa.text(
            "UPDATE course_entitlements SET product_type = 'course' "
            "WHERE product_type = 'video'"
        )
    )

    op.drop_constraint("ck_product_skus_lesson_count", "product_skus", type_="check")
    op.create_check_constraint(
        "ck_product_skus_lesson_count",
        "product_skus",
        "lesson_count > 0",
    )
    op.drop_constraint("ck_order_items_lesson_count", "order_items", type_="check")
    op.create_check_constraint(
        "ck_order_items_lesson_count",
        "order_items",
        "lesson_count > 0",
    )
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
    op.drop_index(op.f("ix_product_videos_is_active"), table_name="product_videos")
    op.drop_index(op.f("ix_product_videos_product_id"), table_name="product_videos")
    op.drop_table("product_videos")


def downgrade() -> None:
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
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
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
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO product_videos
                (id, product_id, title, object_key, duration_seconds, sort_order,
                 is_active, created_at, updated_at)
            SELECT gen_random_uuid(), b.product_id, l.title, l.object_key,
                   l.duration_seconds, l.lesson_number, l.is_active,
                   l.created_at, l.updated_at
            FROM product_video_course_bindings b
            JOIN video_course_lessons l ON l.video_course_id = b.video_course_id
            LEFT JOIN product_video_course_binding_lessons bl
              ON bl.binding_id = b.id AND bl.video_course_lesson_id = l.id
            WHERE b.access_mode = 'all' OR bl.binding_id IS NOT NULL
            """
        )
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
    op.drop_constraint("ck_order_items_lesson_count", "order_items", type_="check")
    op.create_check_constraint(
        "ck_order_items_lesson_count",
        "order_items",
        "lesson_count >= 0",
    )
    op.drop_constraint("ck_product_skus_lesson_count", "product_skus", type_="check")
    op.create_check_constraint(
        "ck_product_skus_lesson_count",
        "product_skus",
        "lesson_count >= 0",
    )
    bind.execute(
        sa.text(
            """
            UPDATE products p SET product_type = 'video'
            WHERE EXISTS (
                SELECT 1 FROM product_video_course_bindings b
                WHERE b.product_id = p.id
            )
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE product_skus ps SET lesson_count = 0
            FROM products p
            WHERE ps.product_id = p.id AND p.product_type = 'video'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE order_items oi
            SET product_type = 'video', lesson_count = 0
            FROM products p
            WHERE oi.product_id = p.id AND p.product_type = 'video'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE course_entitlements ce
            SET product_type = 'video', total_lessons = 0,
                remaining_lessons = 0, reserved_lessons = 0
            FROM products p
            WHERE ce.product_id = p.id AND p.product_type = 'video'
            """
        )
    )
    op.drop_table("product_video_course_binding_lessons")
    op.drop_index(
        op.f("ix_product_video_course_bindings_video_course_id"),
        table_name="product_video_course_bindings",
    )
    op.drop_index(
        op.f("ix_product_video_course_bindings_product_id"),
        table_name="product_video_course_bindings",
    )
    op.drop_table("product_video_course_bindings")
    op.drop_index(
        op.f("ix_video_course_lessons_is_active"),
        table_name="video_course_lessons",
    )
    op.drop_index(
        op.f("ix_video_course_lessons_video_course_id"),
        table_name="video_course_lessons",
    )
    op.drop_table("video_course_lessons")
    op.drop_index(op.f("ix_video_courses_is_active"), table_name="video_courses")
    op.drop_index(op.f("ix_video_courses_name"), table_name="video_courses")
    op.drop_index(op.f("ix_video_courses_category_id"), table_name="video_courses")
    op.drop_index(op.f("ix_video_courses_store_id"), table_name="video_courses")
    op.drop_table("video_courses")
    access_mode.drop(bind, checkfirst=True)
