"""expand audit resource identifiers for object storage keys

Revision ID: 20260827_0012
Revises: 20260825_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0012"
down_revision: str | None = "20260825_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "audit_logs",
        "resource_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=512),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "audit_logs",
        "resource_id",
        existing_type=sa.String(length=512),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
