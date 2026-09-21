"""模型声明 vs 数据库实际结构的一致性。

为什么需要这条测试：alembic autogenerate 以 ORM 模型为唯一事实来源，
模型里没声明的索引一律被判为「已被移除」并生成 drop_index。

这不是假设。2026-09-15 实测：当时有 11 个复合索引只存在于迁移文件里、
模型没声明，跑一次 `alembic revision --autogenerate` 就生成了 11 条
drop_index——合并这样一个迁移，生产上所有列表查询用的复合索引会被一次删光，
而且没有任何报错，只会在某天变慢时才被发现。

所以这里直接卡住「模型少声明」这个方向的漂移。
"""

import pytest
from sqlalchemy import text

from app.core.database import Base, get_engine

pytestmark = pytest.mark.asyncio

# alembic 自己的版本表，不由我们的模型管理。
IGNORED_INDEXES = {"alembic_version_pkc"}


def _model_index_names() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for table in Base.metadata.sorted_tables:
        names = {index.name for index in table.indexes if index.name}
        # mapped_column(index=True) 由 SQLAlchemy 自动命名成 ix_<表>_<列>
        names |= {
            f"ix_{table.name}_{column.name}" for column in table.columns if column.index
        }
        result[table.name] = names
    return result


async def test_no_index_exists_only_in_database() -> None:
    """库里有、模型没声明的索引 = 下一次 autogenerate 会把它删掉。"""
    models = _model_index_names()

    async with get_engine().connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "select tablename, indexname from pg_indexes "
                    "where schemaname = 'public'"
                )
            )
        ).all()

    undeclared: dict[str, set[str]] = {}
    for table_name, index_name in rows:
        if index_name in IGNORED_INDEXES:
            continue
        # 主键和唯一约束背后的隐式索引由 PrimaryKeyConstraint /
        # UniqueConstraint 管理，不出现在 table.indexes 里。约束本身的漂移
        # autogenerate 会单独报 drop_constraint，不在这条测试的范围内。
        if index_name.endswith("_pkey") or index_name.endswith("_key"):
            continue
        if index_name.startswith("uq_"):
            continue
        if index_name in models.get(table_name, set()):
            continue
        undeclared.setdefault(table_name, set()).add(index_name)

    assert not undeclared, (
        "下列索引存在于数据库但模型未声明，"
        "跑 alembic autogenerate 会生成 drop_index 把它们删掉：\n"
        + "\n".join(
            f"  {table}: {', '.join(sorted(names))}"
            for table, names in sorted(undeclared.items())
        )
    )


async def test_no_index_declared_only_in_models() -> None:
    """模型声明了、库里没有 = 有迁移没写或没跑。"""
    models = _model_index_names()

    async with get_engine().connect() as connection:
        rows = (
            await connection.execute(
                text("select indexname from pg_indexes where schemaname = 'public'")
            )
        ).all()
    existing = {row[0] for row in rows}

    missing: dict[str, set[str]] = {}
    for table_name, names in models.items():
        absent = names - existing
        if absent:
            missing[table_name] = absent

    assert not missing, (
        "下列索引在模型里声明了但数据库里不存在，说明缺迁移或迁移没跑：\n"
        + "\n".join(
            f"  {table}: {', '.join(sorted(names))}"
            for table, names in sorted(missing.items())
        )
    )
