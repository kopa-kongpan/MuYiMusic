"""add payment reconciliation and confirmed WeChat fulfillment outbox

Revision ID: 20261019_0016
Revises: 20261009_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0016"
down_revision: str | None = "20261009_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

fulfillment_status = postgresql.ENUM(
    "pending",
    "sent",
    "failed",
    "cancelled",
    name="fulfillment_status",
    create_type=False,
)


def upgrade() -> None:
    op.add_column("payments", sa.Column("payer_openid", sa.String(128), nullable=True))
    op.add_column(
        "payments",
        sa.Column(
            "reconcile_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "payments",
        sa.Column("next_reconcile_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "payments", sa.Column("last_reconcile_error", sa.String(128), nullable=True)
    )
    op.create_index("ix_payments_next_reconcile_at", "payments", ["next_reconcile_at"])
    fulfillment_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "wechat_fulfillments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("payment_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("confirmed_by_admin_id", sa.Uuid(), nullable=False),
        sa.Column("logistics_type", sa.Integer(), nullable=False),
        sa.Column("item_description", sa.String(120), nullable=False),
        sa.Column("evidence", sa.String(500), nullable=False),
        sa.Column("payer_openid", sa.String(128), nullable=False),
        sa.Column(
            "status", fulfillment_status, nullable=False, server_default="pending"
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(128), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["confirmed_by_admin_id"], ["admin_users.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("logistics_type IN (3, 4)", name="ck_fulfillment_logistics"),
        sa.CheckConstraint("attempts >= 0", name="ck_fulfillment_attempts"),
    )
    op.create_index("ix_wechat_fulfillments_status", "wechat_fulfillments", ["status"])
    op.create_index(
        "ix_wechat_fulfillments_next_attempt_at",
        "wechat_fulfillments",
        ["next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_table("wechat_fulfillments")
    fulfillment_status.drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_payments_next_reconcile_at", table_name="payments")
    op.drop_column("payments", "last_reconcile_error")
    op.drop_column("payments", "next_reconcile_at")
    op.drop_column("payments", "reconcile_attempts")
    op.drop_column("payments", "payer_openid")
