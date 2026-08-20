#!/usr/bin/env bash
# MuYiMusic 数据库恢复。会覆盖目标库现有数据，务必确认后执行。
#
# 用法：
#   deploy/scripts/restore-postgres.sh /var/backups/muyimusic/muyimusic-20260819-011700.sql.gz
#
# 未经演练的备份等于没有备份，建议每季度在测试环境跑一次本脚本。

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"

if [[ $# -ne 1 ]]; then
	echo "用法：$0 <备份文件.sql.gz>" >&2
	exit 1
fi

archive="$1"
COMPOSE_FILES=(-f deploy/compose.yaml -f deploy/compose.prod.yaml)

if [[ ! -f "$archive" ]]; then
	echo "错误：备份文件不存在：$archive" >&2
	exit 1
fi

if ! gzip -t "$archive"; then
	echo "错误：备份文件已损坏：$archive" >&2
	exit 1
fi

echo "即将用以下备份覆盖生产数据库："
echo "  $archive（$(du -h "$archive" | cut -f1)）"
echo
read -r -p "确认恢复？输入 yes 继续：" confirm
if [[ "$confirm" != "yes" ]]; then
	echo "已取消"
	exit 1
fi

# 停掉写入方，避免恢复过程中出现并发写。数据库本身保持运行。
echo "[$(date '+%F %T')] 停止 api 与 worker"
docker compose --env-file .env "${COMPOSE_FILES[@]}" stop api worker

echo "[$(date '+%F %T')] 导入备份"
# 备份使用 --clean --if-exists 导出，自带删除重建语句。
gunzip -c "$archive" |
	docker compose --env-file .env "${COMPOSE_FILES[@]}" exec -T postgres \
		sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'

echo "[$(date '+%F %T')] 重启 api 与 worker"
docker compose --env-file .env "${COMPOSE_FILES[@]}" start api worker

echo "[$(date '+%F %T')] 恢复完成，请验证 /health 与关键业务数据"
