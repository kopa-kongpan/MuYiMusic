"""add notification center

Revision ID: 20260813_0009
Revises: 20260806_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0009"
down_revision: str | None = "20260806_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    recipient = postgresql.ENUM(
        "user", "teacher", name="notification_recipient_type", create_type=False
    )
    channel = postgresql.ENUM(
        "wechat_subscribe", name="notification_channel", create_type=False
    )
    delivery = postgresql.ENUM(
        "pending",
        "sent",
        "skipped",
        "failed",
        name="notification_delivery_status",
        create_type=False,
    )
    subscription = postgresql.ENUM(
        "accept",
        "reject",
        "ban",
        name="notification_subscription_status",
        create_type=False,
    )
    for enum in (recipient, channel, delivery, subscription):
        enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "teacher_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), server_default="weapp", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "teacher_id", "provider", name="uq_teacher_accounts_teacher_provider"
        ),
        sa.UniqueConstraint(
            "user_id", "teacher_id", name="uq_teacher_accounts_user_teacher"
        ),
    )
    op.create_index(
        "ix_teacher_accounts_teacher_id", "teacher_accounts", ["teacher_id"]
    )
    op.create_index("ix_teacher_accounts_user_id", "teacher_accounts", ["user_id"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("recipient_type", recipient, nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_teacher_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("page_path", sa.String(512), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"], ["appointments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_teacher_id"], ["teachers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_notifications_event_key"),
    )
    for column in (
        "recipient_type",
        "recipient_user_id",
        "recipient_teacher_id",
        "kind",
        "appointment_id",
        "created_at",
    ):
        op.create_index(f"ix_notifications_{column}", "notifications", [column])
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("channel", channel, nullable=False),
        sa.Column("template_key", sa.String(64), nullable=False),
        sa.Column("status", delivery, server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
            ["notification_id"], ["notifications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id", "channel", name="uq_notification_outbox_channel"
        ),
    )
    for column in ("notification_id", "status", "next_attempt_at"):
        op.create_index(
            f"ix_notification_outbox_{column}", "notification_outbox", [column]
        )
    op.create_table(
        "notification_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("template_key", sa.String(64), nullable=False),
        sa.Column("status", subscription, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            "template_key",
            name="uq_notification_subscriptions_template",
        ),
    )
    op.create_index(
        "ix_notification_subscriptions_user_id",
        "notification_subscriptions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("notification_subscriptions")
    op.drop_table("notification_outbox")
    op.drop_table("notifications")
    op.drop_table("teacher_accounts")
    for name in (
        "notification_subscription_status",
        "notification_delivery_status",
        "notification_channel",
        "notification_recipient_type",
    ):
        sa.Enum(name=name).drop(op.get_bind())
