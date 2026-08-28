"""add franchise pages

Revision ID: 20260825_0011
Revises: 20260815_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0011"
down_revision: str | None = "20260815_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "franchise_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("introduction", sa.Text(), nullable=False),
        sa.Column("advantages", sa.Text(), nullable=False),
        sa.Column("support_policy", sa.Text(), nullable=False),
        sa.Column("application_process", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.String(64), nullable=False),
        sa.Column("contact_phone", sa.String(32), nullable=False),
        sa.Column("contact_wechat", sa.String(64), nullable=True),
        sa.Column(
            "is_published",
            sa.Boolean(),
            server_default=sa.false(),
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
        sa.UniqueConstraint("store_id"),
    )


def downgrade() -> None:
    op.drop_table("franchise_pages")
