"""add operator account management permissions and role

Revision ID: 20260805_0007
Revises: 20260805_0006
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0007"
down_revision: str | None = "20260805_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute(
        sa.text(
            """
            INSERT INTO permissions (id, code, name)
            VALUES (
                '4f2e5e6f-46b4-4f70-9da4-9e61f6de22c7',
                'admins:manage',
                '管理运营账号'
            )
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO roles (id, code, name)
            VALUES (
                'b8ee16ab-cf0b-4e1f-9b4d-7e8a11c1e1fb',
                'store_operator',
                '门店运营'
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
            CROSS JOIN permissions
            WHERE roles.code = 'platform_admin'
              AND permissions.code = 'admins:manage'
            ON CONFLICT DO NOTHING
            """
        )
    )
    operator_permissions = (
        "store_content:manage",
        "products:manage",
        "users:read",
        "schedules:manage",
        "appointments:manage",
        "consumptions:manage",
    )
    for code in operator_permissions:
        op.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT roles.id, permissions.id
                FROM roles
                CROSS JOIN permissions
                WHERE roles.code = 'store_operator'
                  AND permissions.code = :code
                ON CONFLICT DO NOTHING
                """
            ).bindparams(code=code)
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            USING roles
            WHERE role_permissions.role_id = roles.id
              AND roles.code IN ('platform_admin', 'store_operator')
              AND role_permissions.permission_id IN (
                  SELECT id FROM permissions WHERE code = 'admins:manage'
              )
            """
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'admins:manage'"))
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            USING roles
            WHERE role_permissions.role_id = roles.id
              AND roles.code = 'store_operator'
            """
        )
    )
    op.execute(sa.text("DELETE FROM roles WHERE code = 'store_operator'"))
