#!/usr/bin/env bash
# MuYiMusic 生产数据库备份。
#
# 通过 pg_dump 导出全量 SQL，压缩后可选上传对象存储，并清理过期本地副本。
# 数据库当前只有几十 MB，全量备份足够，无需增量。
#
# 用法：
#   deploy/scripts/backup-postgres.sh
#
# 建议 crontab（每小时一次，输出写入日志）：
#   17 * * * * cd /opt/muyimusic && deploy/scripts/backup-postgres.sh >> /var/log/muyimusic-backup.log 2>&1

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/muyimusic}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
COMPOSE_FILES=(-f deploy/compose.yaml -f deploy/compose.prod.yaml)

if [[ ! -f .env ]]; then
	echo "错误：未找到 .env" >&2
	exit 1
fi

mkdir -p "$BACKUP_DIR"

timestamp="$(date +%Y%m%d-%H%M%S)"
target="$BACKUP_DIR/muyimusic-$timestamp.sql.gz"

echo "[$(date '+%F %T')] 开始备份 -> $target"

# 经容器内 pg_dump 导出，不依赖宿主机安装 PostgreSQL 客户端。
# 先写临时文件，成功后再改名，避免 cron 中断留下半个备份被误当成可用副本。
docker compose --env-file .env "${COMPOSE_FILES[@]}" exec -T postgres \
	sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' |
	gzip -9 >"$target.partial"

mv "$target.partial" "$target"

size="$(du -h "$target" | cut -f1)"
echo "[$(date '+%F %T')] 备份完成，大小 $size"

# 校验能否正常解压，损坏的压缩包等于没有备份。
if ! gzip -t "$target"; then
	echo "错误：备份文件校验失败，已保留待排查：$target" >&2
	exit 1
fi

# 可选上传对象存储。需先安装并配置 coscmd 或 aws cli。
if [[ -n "${BACKUP_COS_PATH:-}" ]]; then
	if command -v coscmd >/dev/null 2>&1; then
		echo "[$(date '+%F %T')] 上传到 COS：$BACKUP_COS_PATH"
		coscmd upload "$target" "$BACKUP_COS_PATH/$(basename "$target")"
	else
		echo "警告：已设置 BACKUP_COS_PATH 但未安装 coscmd，跳过上传" >&2
	fi
fi

# 清理过期本地备份。
deleted="$(find "$BACKUP_DIR" -name 'muyimusic-*.sql.gz' -type f -mtime "+$RETENTION_DAYS" -print -delete | wc -l)"
if [[ "$deleted" -gt 0 ]]; then
	echo "[$(date '+%F %T')] 已清理 $deleted 个超过 $RETENTION_DAYS 天的备份"
fi

echo "[$(date '+%F %T')] 当前保留 $(find "$BACKUP_DIR" -name 'muyimusic-*.sql.gz' -type f | wc -l) 个备份"
