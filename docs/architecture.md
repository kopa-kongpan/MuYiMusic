# 工程基座说明

## 边界

- `apps/miniapp` 与 `apps/admin` 不共享 UI，只依赖共享 API 类型、枚举和纯函数。
- `services/api/app/api` 只承载 HTTP 路由和响应组织。
- 后续业务逻辑进入 `services`，数据访问进入 `repositories`。
- 微信、抖音及支付差异分别通过前端 `platform` 与后端 `providers` 适配层隔离。
- 所有数据库结构变更必须通过 `services/api/migrations` 管理。

## 当前状态

当前仅包含可运行入口、工具链、健康检查和空模块目录。业务数据模型、业务路由、权限、支付、上传及外部平台调用均尚未实现。

