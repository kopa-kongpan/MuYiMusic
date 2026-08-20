"""add teacher binding codes and teacher cancellation

Revision ID: 20260815_0010
Revises: 20260813_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0010"
down_revision: str | None = "20260813_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE appointment_cancelled_by ADD VALUE IF NOT EXISTS 'teacher'")
    op.create_table(
        "teacher_bind_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("created_by_admin_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"], ["admin_users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["used_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    for column in (
        "teacher_id",
        "created_by_admin_id",
        "expires_at",
        "used_by_user_id",
    ):
        op.create_index(
            f"ix_teacher_bind_codes_{column}", "teacher_bind_codes", [column]
        )


def downgrade() -> None:
    op.drop_table("teacher_bind_codes")
    # PostgreSQL enum values cannot be removed safely in a downgrade.
