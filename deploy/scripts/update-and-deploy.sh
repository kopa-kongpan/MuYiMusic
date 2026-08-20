#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
BRANCH="${1:-main}"
REMOTE="${GIT_REMOTE:-origin}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/compose.yaml}"
ENV_FILE="${ENV_FILE:-.env}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8080}"
ADMIN_BASE_URL="${ADMIN_BASE_URL:-http://127.0.0.1:5173}"
H5_BASE_URL="${H5_BASE_URL:-http://127.0.0.1:10086}"

cd "${REPO_ROOT}"

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

fail() {
  log "错误：$*"
  exit 1
}

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-30}"
  local attempt

  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl --fail --silent --show-error --output /dev/null "${url}"; then
      log "${name} 验证通过：${url}"
      return 0
    fi
    sleep 2
  done

  fail "${name} 在 $((attempts * 2)) 秒内未就绪：${url}"
}

check_job_exit_code() {
  local service="$1"
  local container_id
  local exit_code

  container_id="$(compose ps -aq "${service}")"
  [[ -n "${container_id}" ]] || fail "未找到 ${service} 容器"
  exit_code="$(docker inspect --format '{{.State.ExitCode}}' "${container_id}")"
  [[ "${exit_code}" == "0" ]] || fail "${service} 容器退出码为 ${exit_code}"
  log "${service} 容器执行成功"
}

command -v git >/dev/null || fail "未安装 git"
command -v docker >/dev/null || fail "未安装 docker"
command -v curl >/dev/null || fail "未安装 curl"
[[ -f "${ENV_FILE}" ]] || fail "缺少环境文件：${REPO_ROOT}/${ENV_FILE}"

if [[ -n "$(git status --porcelain)" ]]; then
  fail "Git 工作区存在未提交改动，请先处理后再部署"
fi

current_branch="$(git branch --show-current)"
if [[ "${current_branch}" != "${BRANCH}" ]]; then
  log "切换分支：${current_branch:-detached HEAD} -> ${BRANCH}"
  git switch "${BRANCH}"
fi

before_revision="$(git rev-parse --short HEAD)"
log "从 ${REMOTE}/${BRANCH} 拉取代码，当前版本 ${before_revision}"
git pull --ff-only "${REMOTE}" "${BRANCH}"
after_revision="$(git rev-parse --short HEAD)"
log "代码更新完成：${before_revision} -> ${after_revision}"

log "开始构建并启动 Docker 服务"
compose up -d --build

check_job_exit_code migrate
check_job_exit_code bootstrap

required_services=(postgres redis api worker nginx admin h5)
running_services="$(compose ps --status running --services)"
for service in "${required_services[@]}"; do
  if ! grep -Fxq "${service}" <<<"${running_services}"; then
    compose ps
    fail "长期服务未运行：${service}"
  fi
done
log "全部长期服务均已运行"

wait_for_http "API 健康检查" "${API_BASE_URL}/health"
wait_for_http "公开门店 API" "${API_BASE_URL}/api/v1/app/stores?page=1&page_size=1"
wait_for_http "管理后台" "${ADMIN_BASE_URL}/"
wait_for_http "H5" "${H5_BASE_URL}/"

compose ps
log "部署完成，当前版本：$(git rev-parse --short HEAD)"
