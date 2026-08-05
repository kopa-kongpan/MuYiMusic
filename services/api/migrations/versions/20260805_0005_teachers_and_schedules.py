"""add teachers and class schedules

Revision ID: 20260805_0005
Revises: 20260805_0004
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0005"
down_revision: str | None = "20260805_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

schedule_status = postgresql.ENUM(
    "open",
    "closed",
    "cancelled",
    name="schedule_status",
    create_type=False,
)


def upgrade() -> None:
    postgresql.ENUM(
        "open",
        "closed",
        "cancelled",
        name="schedule_status",
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "teachers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("specialties", sa.Text(), server_default="", nullable=False),
        sa.Column("bio", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint("sort_order >= 0", name="ck_teachers_sort_order"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "name", name="uq_teachers_store_name"),
    )
    op.create_index(op.f("ix_teachers_is_active"), "teachers", ["is_active"])
    op.create_index(op.f("ix_teachers_store_id"), "teachers", ["store_id"])
    op.create_index(
        "ix_teachers_store_active_order",
        "teachers",
        ["store_id", "is_active", "sort_order"],
    )

    op.create_table(
        "class_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("course_name", sa.String(length=128), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("reserved_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "status",
            schedule_status,
            server_default="open",
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
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
        sa.CheckConstraint("ends_at > starts_at", name="ck_schedules_time_window"),
        sa.CheckConstraint("capacity > 0", name="ck_schedules_capacity"),
        sa.CheckConstraint(
            "reserved_count >= 0 AND reserved_count <= capacity",
            name="ck_schedules_reserved_count",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["teachers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_class_schedules_ends_at"),
        "class_schedules",
        ["ends_at"],
    )
    op.create_index(
        op.f("ix_class_schedules_product_id"),
        "class_schedules",
        ["product_id"],
    )
    op.create_index(
        op.f("ix_class_schedules_starts_at"),
        "class_schedules",
        ["starts_at"],
    )
    op.create_index(
        op.f("ix_class_schedules_status"),
        "class_schedules",
        ["status"],
    )
    op.create_index(
        op.f("ix_class_schedules_store_id"),
        "class_schedules",
        ["store_id"],
    )
    op.create_index(
        op.f("ix_class_schedules_teacher_id"),
        "class_schedules",
        ["teacher_id"],
    )
    op.create_index(
        "ix_schedules_store_start_status",
        "class_schedules",
        ["store_id", "starts_at", "status"],
    )
    op.create_index(
        "ix_schedules_teacher_time",
        "class_schedules",
        ["teacher_id", "starts_at", "ends_at"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO permissions (id, code, name)
            VALUES (
                '5b50f151-3730-41d5-a755-79e82404e82f',
                'schedules:manage',
                '管理教师与排课'
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
            JOIN permissions ON permissions.code = 'schedules:manage'
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
              AND permissions.code = 'schedules:manage'
            """
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'schedules:manage'"))
    op.drop_index("ix_schedules_teacher_time", table_name="class_schedules")
    op.drop_index("ix_schedules_store_start_status", table_name="class_schedules")
    op.drop_index(
        op.f("ix_class_schedules_teacher_id"),
        table_name="class_schedules",
    )
    op.drop_index(
        op.f("ix_class_schedules_store_id"),
        table_name="class_schedules",
    )
    op.drop_index(
        op.f("ix_class_schedules_status"),
        table_name="class_schedules",
    )
    op.drop_index(
        op.f("ix_class_schedules_starts_at"),
        table_name="class_schedules",
    )
    op.drop_index(
        op.f("ix_class_schedules_product_id"),
        table_name="class_schedules",
    )
    op.drop_index(
        op.f("ix_class_schedules_ends_at"),
        table_name="class_schedules",
    )
    op.drop_table("class_schedules")
    op.drop_index("ix_teachers_store_active_order", table_name="teachers")
    op.drop_index(op.f("ix_teachers_store_id"), table_name="teachers")
    op.drop_index(op.f("ix_teachers_is_active"), table_name="teachers")
    op.drop_table("teachers")
    schedule_status.drop(op.get_bind(), checkfirst=True)
