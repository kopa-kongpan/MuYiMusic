"""add appointments and lesson consumptions

Revision ID: 20260805_0006
Revises: 20260805_0005
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0006"
down_revision: str | None = "20260805_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

appointment_status = postgresql.ENUM(
    "reserved",
    "cancelled",
    "completed",
    "no_show",
    name="appointment_status",
    create_type=False,
)
appointment_cancelled_by = postgresql.ENUM(
    "user",
    "admin",
    name="appointment_cancelled_by",
    create_type=False,
)
consumption_kind = postgresql.ENUM(
    "attended",
    "no_show",
    name="consumption_kind",
    create_type=False,
)
consumption_status = postgresql.ENUM(
    "applied",
    "reversed",
    name="consumption_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for values, name in (
        (("reserved", "cancelled", "completed", "no_show"), "appointment_status"),
        (("user", "admin"), "appointment_cancelled_by"),
        (("attended", "no_show"), "consumption_kind"),
        (("applied", "reversed"), "consumption_status"),
    ):
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.add_column(
        "course_entitlements",
        sa.Column("reserved_lessons", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_entitlements_reserved_lessons",
        "course_entitlements",
        "reserved_lessons >= 0 AND reserved_lessons <= remaining_lessons",
    )

    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("appointment_no", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            appointment_status,
            server_default="reserved",
            nullable=False,
        ),
        sa.Column("booking_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("cancel_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("cancelled_by", appointment_cancelled_by, nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("no_show_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["entitlement_id"],
            ["course_entitlements.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["class_schedules.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_no"),
        sa.UniqueConstraint(
            "user_id",
            "booking_idempotency_key",
            name="uq_appointments_user_booking_key",
        ),
        sa.UniqueConstraint(
            "user_id",
            "cancel_idempotency_key",
            name="uq_appointments_user_cancel_key",
        ),
    )
    for column in ("entitlement_id", "schedule_id", "status", "store_id", "user_id"):
        op.create_index(op.f(f"ix_appointments_{column}"), "appointments", [column])
    op.create_index(
        "ix_appointments_user_status_created",
        "appointments",
        ["user_id", "status", "created_at"],
    )
    op.create_index(
        "ix_appointments_store_schedule_status",
        "appointments",
        ["store_id", "schedule_id", "status"],
    )
    op.create_index(
        "uq_appointments_user_schedule_reserved",
        "appointments",
        ["user_id", "schedule_id"],
        unique=True,
        postgresql_where=sa.text("status = 'reserved'"),
    )

    op.create_table(
        "lesson_consumptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("kind", consumption_kind, nullable=False),
        sa.Column(
            "status",
            consumption_status,
            server_default="applied",
            nullable=False,
        ),
        sa.Column("lessons", sa.Integer(), server_default="1", nullable=False),
        sa.Column("operator_admin_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reversed_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("reversal_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("lessons > 0", name="ck_consumptions_lessons"),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["entitlement_id"],
            ["course_entitlements.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["operator_admin_id"],
            ["admin_users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_admin_id"],
            ["admin_users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "store_id",
            "idempotency_key",
            name="uq_consumptions_store_key",
        ),
        sa.UniqueConstraint(
            "store_id",
            "reversal_idempotency_key",
            name="uq_consumptions_store_reversal_key",
        ),
    )
    for column in (
        "appointment_id",
        "entitlement_id",
        "operator_admin_id",
        "reversed_by_admin_id",
        "status",
        "store_id",
        "user_id",
    ):
        op.create_index(
            op.f(f"ix_lesson_consumptions_{column}"),
            "lesson_consumptions",
            [column],
        )
    op.create_index(
        "uq_consumptions_appointment_applied",
        "lesson_consumptions",
        ["appointment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'applied'"),
    )

    permission_rows = (
        ("f5d27a2d-f253-4ad7-a4ac-4da16a7558bd", "appointments:manage", "管理预约"),
        (
            "810bbf75-8ee1-44be-9301-f2e8e6c8dce5",
            "consumptions:manage",
            "执行消课与缺席",
        ),
        ("b2171415-20cb-4a32-87b9-bd9eb77c54d6", "consumptions:reverse", "撤销消课"),
    )
    for permission_id, code, name in permission_rows:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, name)
                VALUES (CAST(:id AS uuid), :code, :name)
                ON CONFLICT (code) DO NOTHING
                """
            ).bindparams(id=permission_id, code=code, name=name)
        )
        op.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT roles.id, permissions.id
                FROM roles
                JOIN permissions ON permissions.code = :code
                WHERE roles.code = 'platform_admin'
                ON CONFLICT DO NOTHING
                """
            ).bindparams(code=code)
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            USING permissions
            WHERE role_permissions.permission_id = permissions.id
              AND permissions.code IN (
                'appointments:manage',
                'consumptions:manage',
                'consumptions:reverse'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code IN (
              'appointments:manage',
              'consumptions:manage',
              'consumptions:reverse'
            )
            """
        )
    )
    op.drop_index(
        "uq_consumptions_appointment_applied",
        table_name="lesson_consumptions",
    )
    for column in reversed(
        (
            "appointment_id",
            "entitlement_id",
            "operator_admin_id",
            "reversed_by_admin_id",
            "status",
            "store_id",
            "user_id",
        )
    ):
        op.drop_index(
            op.f(f"ix_lesson_consumptions_{column}"),
            table_name="lesson_consumptions",
        )
    op.drop_table("lesson_consumptions")
    op.drop_index(
        "uq_appointments_user_schedule_reserved",
        table_name="appointments",
    )
    op.drop_index("ix_appointments_store_schedule_status", table_name="appointments")
    op.drop_index("ix_appointments_user_status_created", table_name="appointments")
    for column in reversed(
        ("entitlement_id", "schedule_id", "status", "store_id", "user_id")
    ):
        op.drop_index(op.f(f"ix_appointments_{column}"), table_name="appointments")
    op.drop_table("appointments")
    op.drop_constraint(
        "ck_entitlements_reserved_lessons",
        "course_entitlements",
        type_="check",
    )
    op.drop_column("course_entitlements", "reserved_lessons")
    consumption_status.drop(op.get_bind(), checkfirst=True)
    consumption_kind.drop(op.get_bind(), checkfirst=True)
    appointment_cancelled_by.drop(op.get_bind(), checkfirst=True)
    appointment_status.drop(op.get_bind(), checkfirst=True)
