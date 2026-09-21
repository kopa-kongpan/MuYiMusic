"""add composite index for admin appointment list

Revision ID: 20260915_0014
Revises: 20260828_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0014"
down_revision: str | None = "20260828_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_appointments_store_status_created"


def upgrade() -> None:
    """管理端预约列表的复合索引。

    list_admin 按 store_id + status 过滤，再 created_at DESC, id DESC 分页。
    此前只有 store_id、status 两个单列索引，查 completed（生产上会占绝大多数）
    时只能先捞出该门店全部历史预约再排序。

    实测（21.7 万行 / 109MB 的基准库）：
      列表查询    9.7~10.3ms → 0.13~0.31ms
      分页 count  11.1~13.8ms → 8.4ms（走 Index Only Scan，不再回表）
    索引体积约 18MB。

    列顺序与 ORDER BY 完全一致（含 DESC），排序步骤可以整个省掉；
    INCLUDE(schedule_id) 让 count(*) 不必回表拿 join 键。

    用 CONCURRENTLY 建：appointments 是热表，普通 CREATE INDEX 会持有
    SHARE 锁，阻塞整张表的写入。代价是这个迁移不能包在事务里（见下方
    autocommit_block）。
    """
    with op.get_context().autocommit_block():
        op.create_index(
            INDEX_NAME,
            "appointments",
            [
                "store_id",
                "status",
                sa.literal_column("created_at DESC"),
                sa.literal_column("id DESC"),
            ],
            unique=False,
            postgresql_include=("schedule_id",),
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            INDEX_NAME,
            table_name="appointments",
            postgresql_include=("schedule_id",),
            postgresql_concurrently=True,
        )
