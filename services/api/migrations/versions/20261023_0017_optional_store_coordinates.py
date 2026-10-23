"""Allow stores without geocoded coordinates.

Revision ID: 20261023_0017
Revises: 20261019_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0017"
down_revision: str | None = "20261019_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("stores", "latitude", existing_type=sa.Numeric(9, 6), nullable=True)
    op.alter_column(
        "stores", "longitude", existing_type=sa.Numeric(10, 6), nullable=True
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM stores WHERE latitude IS NULL "
                "OR longitude IS NULL LIMIT 1"
            )
        )
        .first()
    ):
        raise RuntimeError("门店坐标仍有空值，无法恢复必填约束")
    op.alter_column(
        "stores", "longitude", existing_type=sa.Numeric(10, 6), nullable=False
    )
    op.alter_column(
        "stores", "latitude", existing_type=sa.Numeric(9, 6), nullable=False
    )
