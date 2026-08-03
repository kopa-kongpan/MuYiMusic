# MuYiMusic

MuYiMusic 是一个前后端分离的 monorepo，包含微信/抖音小程序、Web 运营管理后台和一套 FastAPI 后端服务。当前仓库只提供工程基座，不包含登录、商品、订单、支付等业务实现。

开发前请先阅读 [PROJECT_TECH_SPEC.md](./PROJECT_TECH_SPEC.md)。

## 目录

```text
apps/miniapp        Taro 4 + React 18 小程序
apps/admin          Vite + React 18 管理后台
packages/api-client OpenAPI 生成客户端的承载包
packages/shared     前端共享枚举与纯函数
packages/eslint-config 前端公共 ESLint 配置
services/api        FastAPI 模块化单体服务
deploy              Docker Compose 与 Nginx 配置
docs                项目文档
```

## 环境要求

- Node.js 20.19+
- pnpm 11
- Python 3.12+
- uv
- Docker 与 Docker Compose

仓库声明了固定 pnpm 版本，可通过 Corepack 启用：

```bash
corepack enable
pnpm install
```

## 前端开发

```bash
pnpm dev:admin
pnpm dev:weapp
pnpm dev:tt
pnpm dev:h5
```

小程序构建输出分别位于 `apps/miniapp/dist/weapp`、`apps/miniapp/dist/tt` 和 `apps/miniapp/dist/h5`。

## 后端开发

```bash
cd services/api
uv sync --dev
uv run uvicorn app.main:app --reload
```

API 默认监听 `http://localhost:8000`，健康检查为 `GET /health`，OpenAPI 文档为 `http://localhost:8000/docs`。

数据库迁移命令：

```bash
cd services/api
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe change"
```

## 本地基础设施

```bash
cp .env.example .env
docker compose -f deploy/compose.yaml up --build
```

Nginx 默认监听 `http://localhost:8080`，并将 `/api/` 与 `/health` 转发至 FastAPI。

## 质量检查

```bash
pnpm check

cd services/api
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

## API 客户端生成

OpenAPI 是接口契约的唯一来源。后端可运行后按以下方式导出契约并生成前端类型：

```bash
cd services/api
uv run python scripts/export_openapi.py
cd ../..
pnpm --filter @muyimusic/api-client generate
```

`packages/api-client/src/generated` 下的文件由工具生成，不应手工维护 DTO。

