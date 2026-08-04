# MuYiMusic API

FastAPI 模块化单体服务。v0.2 已包含管理员认证、RBAC、管理员门店授权、门店管理、首页内容管理、对象存储直传签名、公开门店首页和审计日志。

运行、迁移和初始管理员配置参见仓库 `docs/第一版门店闭环说明.md`；首页内容接口、权限和对象存储配置参见 `docs/第二版首页内容闭环说明.md`。

对象存储使用 S3v4 兼容签名。`OBJECT_STORAGE_ENDPOINT` 必须是供应商提供的 S3 兼容 API Endpoint，不能使用控制台地址或 CDN 访问域名；CDN 域名单独配置为 `OBJECT_STORAGE_PUBLIC_BASE_URL`。
