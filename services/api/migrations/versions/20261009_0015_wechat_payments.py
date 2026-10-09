"""add WeChat payment records

Revision ID: 20261009_0015
Revises: 20260915_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261009_0015"
down_revision: str | None = "20260915_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

payment_provider = postgresql.ENUM(
    "wechat",
    name="payment_provider",
    create_type=False,
)
payment_status = postgresql.ENUM(
    "pending",
    "succeeded",
    "closed",
    "failed",
    "refunded",
    name="payment_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("wechat", name="payment_provider").create(bind, checkfirst=True)
    postgresql.ENUM(
        "pending",
        "succeeded",
        "closed",
        "failed",
        "refunded",
        name="payment_status",
    ).create(bind, checkfirst=True)
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            payment_provider,
            server_default="wechat",
            nullable=False,
        ),
        sa.Column(
            "status",
            payment_status,
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("merchant_order_no", sa.String(length=32), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("prepay_id", sa.String(length=128), nullable=True),
        sa.Column("notify_id", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("amount_cents > 0", name="ck_payments_amount"),
        sa.CheckConstraint("attempt_no > 0", name="ck_payments_attempt_no"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_order_no"),
        sa.UniqueConstraint("transaction_id"),
        sa.UniqueConstraint("notify_id"),
        sa.UniqueConstraint(
            "order_id",
            "attempt_no",
            name="uq_payments_order_attempt",
        ),
    )
    op.create_index(op.f("ix_payments_order_id"), "payments", ["order_id"])
    op.create_index(op.f("ix_payments_provider"), "payments", ["provider"])
    op.create_index(op.f("ix_payments_status"), "payments", ["status"])
    op.create_index(
        "ix_payments_order_created",
        "payments",
        ["order_id", "created_at"],
    )
    op.create_index(
        "uq_payments_order_pending",
        "payments",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_payments_order_pending", table_name="payments")
    op.drop_index("ix_payments_order_created", table_name="payments")
    op.drop_index(op.f("ix_payments_status"), table_name="payments")
    op.drop_index(op.f("ix_payments_provider"), table_name="payments")
    op.drop_index(op.f("ix_payments_order_id"), table_name="payments")
    op.drop_table("payments")
    payment_status.drop(op.get_bind(), checkfirst=True)
    payment_provider.drop(op.get_bind(), checkfirst=True)
