# MuYiMusic

MuYiMusic 是一个前后端分离的 monorepo，包含微信/抖音小程序、Web 运营管理后台和一套 FastAPI 后端服务。当前已完成 v0.6 预约与消课闭环，包括教师排课、在线预约、取消、正常消课、缺席扣课和撤销。

开发前请先阅读 [项目技术规范](./docs/项目技术规范.md) 和
[第一阶段需求规格](./docs/第一阶段需求规格.md)。
当前版本说明见 [第六版预约与消课闭环说明](./docs/第六版预约与消课闭环说明.md)，完整容器部署见 [本地容器部署说明](./docs/本地容器部署说明.md)。

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
- Python 3.12+ 与 Conda 环境 `muyimusic`
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
conda run --no-capture-output -n muyimusic python -m uvicorn app.main:app --reload --port 8001
```

本地 API 默认监听 `http://localhost:8001`，健康检查为 `GET /health`，OpenAPI 文档为 `http://localhost:8001/docs`。

数据库迁移命令：

```bash
conda run --no-capture-output -n muyimusic alembic upgrade head
conda run --no-capture-output -n muyimusic alembic revision --autogenerate -m "describe change"
```

## 本地基础设施

```bash
Copy-Item .env.example .env
pnpm deploy:local
pnpm deploy:status
```

部署会启动项目独立的 PostgreSQL、Redis、API、管理后台和 H5，并自动执行 migration 与管理员初始化。API 网关为 `http://localhost:8080`，管理后台为 `http://localhost:5173`，H5 为 `http://localhost:10086`。

## 质量检查

```bash
pnpm check

cd services/api
conda run --no-capture-output -n muyimusic ruff check .
conda run --no-capture-output -n muyimusic ruff format --check .
conda run --no-capture-output -n muyimusic mypy app
conda run --no-capture-output -n muyimusic pytest
```

## API 客户端生成

OpenAPI 是接口契约的唯一来源。后端可运行后按以下方式导出契约并生成前端类型：

```bash
cd services/api
conda run --no-capture-output -n muyimusic python -m scripts.export_openapi
cd ../..
pnpm --filter @muyimusic/api-client generate
```

`packages/api-client/src/generated` 下的文件由工具生成，不应手工维护 DTO。
