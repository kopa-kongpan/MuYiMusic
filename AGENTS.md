# MuYiMusic 开发约定

- 始终使用简体中文沟通。
- Python 开发和质量检查统一使用 Conda 环境 `muyimusic`。
- 项目文档统一放入 `docs/`，文件名优先使用中文。
- 每次功能开发完成并通过代码检查后，必须执行 `pnpm deploy:local` 完成本地 Docker 部署。
- Docker 部署必须确认 migration 和管理员初始化容器成功、所有长期服务健康，并通过 `/health`、公开门店 API、管理后台和 H5 验证数据库及应用链路。
- Docker 部署验证通过后才能提交 Git；不得提交 `.env`、真实密钥、构建目录或临时验收数据。
