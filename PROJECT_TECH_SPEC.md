# 项目技术规范

> 本文档是本项目的技术选型与 AI 开发约束。所有开发者和 AI 编码代理在修改代码前必须阅读本文档。除非需求明确要求并经过确认，不得替换本文档确定的核心技术。

## 1. 项目范围

本项目包含三个客户端，共用一套后端服务：

1. 微信小程序。
2. 抖音小程序。
3. Web 运营管理后台。

主要业务包括：

- 微信、抖音小程序用户登录。
- 用户及客户信息管理。
- 商品、分类、SKU、价格和库存管理。
- 商品上下架。
- 订单及支付状态管理。
- 图片和文件上传。
- 管理员、角色、权限及操作审计。

## 2. 总体架构

```text
微信小程序 ─┐
            │
抖音小程序 ─┼── REST API / HTTPS ── FastAPI
            │                         ├── PostgreSQL
Web 管理端 ─┘                         ├── Redis
                                      ├── ARQ Worker
                                      └── 对象存储
```

系统采用前后端分离架构。客户端不得直接访问数据库，所有业务数据必须通过 FastAPI 提供的 REST API 访问。

## 3. 固定技术栈

### 3.1 小程序

| 类别 | 技术 |
| --- | --- |
| 跨端框架 | Taro 4.x |
| UI 框架 | React 18.x |
| 开发语言 | TypeScript 5.x，开启严格模式 |
| 构建和依赖管理 | pnpm |
| 样式 | SCSS，尺寸优先使用 `rpx` |
| 客户端状态 | Zustand |
| 服务端状态 | TanStack Query |
| 网络请求 | 基于 `Taro.request` 封装统一请求层 |
| 表单校验 | React Hook Form + Zod，复杂表单使用 |
| 目标平台 | 微信 `weapp`、抖音 `tt` |

约束：

- 页面和组件必须使用 `@tarojs/components`，不得依赖浏览器 DOM。
- 不得在业务代码中直接使用 `window`、`document`、`localStorage`。
- 优先使用 Taro 基础组件和项目自有组件。
- 引入 NutUI React 等 UI 库前必须确认微信、抖音两端兼容性和包体积。
- 平台专属能力必须通过 `platform` 适配层调用，不得散落在页面组件中。
- H5 只用于快速调试通用样式，最终效果以平台开发者工具和真机为准。

### 3.2 Web 管理后台

| 类别 | 技术 |
| --- | --- |
| UI 框架 | React 18.x + TypeScript 5.x |
| 构建工具 | Vite |
| UI 组件 | Ant Design + Pro Components |
| 路由 | React Router |
| 服务端状态 | TanStack Query |
| 客户端状态 | Zustand |
| 表单 | Ant Design Form，复杂校验可结合 Zod |
| 图表 | ECharts |
| 依赖管理 | pnpm |

约束：

- 管理后台是业务操作系统，不使用 Next.js，不采用服务端渲染。
- 列表页统一支持查询、分页、排序、加载态、空状态和错误状态。
- 路由和按钮显示可以根据权限控制，但后端必须再次校验权限。
- 小程序和管理后台不得共享 UI 组件，只共享 API 类型、枚举和纯函数。

### 3.3 Python 后端

| 类别 | 技术 |
| --- | --- |
| Python | Python 3.12+ |
| Web 框架 | FastAPI |
| 数据校验 | Pydantic 2 |
| ORM | SQLAlchemy 2 |
| 数据库迁移 | Alembic |
| 主数据库 | PostgreSQL |
| 缓存及限流 | Redis |
| 异步任务 | ARQ |
| HTTP 客户端 | HTTPX |
| ASGI 服务 | Uvicorn |
| 依赖管理 | uv |
| 测试 | pytest |
| 代码检查 | Ruff + mypy |

约束：

- API 路由只负责参数接收、权限校验和响应组织，业务逻辑放在 service 层。
- 数据库访问集中在 repository/service 层，禁止在路由中编写复杂 SQL。
- 所有数据库结构变更必须提供 Alembic migration。
- 对外 HTTP 请求必须设置超时，并对可重试错误实施有限重试。
- 金额使用最小货币单位的整数存储，例如 `1990` 表示 19.90 元。
- 时间在数据库中使用带时区的 UTC 时间，展示时转换为用户时区。

### 3.4 基础设施

| 类别 | 技术 |
| --- | --- |
| 容器 | Docker |
| 本地编排 | Docker Compose |
| 网关和静态文件 | Nginx |
| 文件存储 | 腾讯云 COS、阿里云 OSS 或火山引擎 TOS，部署时三选一 |
| API 协议 | REST + JSON + OpenAPI |
| 日志 | 结构化 JSON 日志 |
| 错误监控 | Sentry，生产环境启用 |
| CI | GitHub Actions 或部署平台原生流水线 |

## 4. 仓库结构

项目采用 monorepo：

```text
project/
├── apps/
│   ├── miniapp/                  # Taro 微信/抖音小程序
│   └── admin/                    # React Web 管理后台
├── packages/
│   ├── api-client/               # OpenAPI 类型及客户端
│   ├── shared/                   # 前端共享枚举和纯函数
│   └── eslint-config/            # 前端公共代码规范
├── services/
│   └── api/                      # FastAPI 服务
│       ├── app/
│       │   ├── api/
│       │   ├── core/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── repositories/
│       │   ├── services/
│       │   └── providers/
│       ├── migrations/
│       └── tests/
├── deploy/
│   ├── compose.yaml
│   └── nginx/
├── docs/
├── pnpm-workspace.yaml
└── README.md
```

## 5. 小程序跨平台规则

微信和抖音共用页面、业务组件、状态管理和 API 类型，平台差异放在适配器中：

```text
apps/miniapp/src/platform/
├── types.ts
├── index.ts
├── weapp.ts
└── tt.ts
```

统一适配器至少覆盖：

- 登录。
- 手机号授权。
- 支付。
- 分享。
- 订阅消息。
- 客服。
- 平台信息和权限判断。

禁止在页面中大量编写 `process.env.TARO_ENV` 分支。页面只依赖统一的 `PlatformAdapter` 接口。

建议为不同平台使用独立输出目录：

```text
dist/weapp
dist/tt
```

常用命令：

```bash
pnpm dev:weapp
pnpm dev:tt
pnpm dev:h5
pnpm build:weapp
pnpm build:tt
```

## 6. API 规范

API 统一使用 `/api/v1` 前缀，并按调用方分组：

```text
/api/v1/app/*        小程序接口
/api/v1/admin/*      管理后台接口
/api/v1/webhooks/*   微信、抖音及支付回调
```

约束：

- OpenAPI 是前后端接口契约的唯一来源。
- 前端 API 类型从 OpenAPI 生成，不重复手写相同 DTO。
- 列表接口统一采用分页结构。
- 错误响应使用统一错误码、可读消息和请求追踪 ID。
- 所有写操作应考虑重复提交和幂等性。
- 支付回调、创建订单等关键接口必须有幂等设计。

## 7. 认证与权限

### 7.1 小程序用户

小程序登录流程：

1. 客户端从微信或抖音获取临时 `code`。
2. 客户端调用 `/api/v1/app/auth/login`，提交 `platform` 和 `code`。
3. 后端通过平台适配器调用对应的 `code2session`。
4. 后端查找或创建内部用户。
5. 后端签发项目自己的 access token 和 refresh token。

平台账号与内部用户必须分表保存：

```text
users
provider_accounts
```

不得把微信 `openid` 或抖音平台用户标识直接作为系统用户主键。

### 7.2 后台管理员

管理员与小程序用户使用独立账号体系：

```text
admin_users
roles
permissions
admin_user_roles
role_permissions
audit_logs
```

后台采用 RBAC。敏感操作必须记录审计日志，包括操作人、时间、资源、操作内容和结果。

## 8. 核心业务模型

第一阶段至少包含：

```text
users
provider_accounts
admin_users
roles
permissions
categories
products
product_skus
product_images
inventory_records
orders
order_items
payments
refunds
audit_logs
```

商品状态使用生命周期枚举：

```text
draft       草稿
published   已上架
offline     已下架
archived    已归档
```

支付必须使用 provider 适配层。微信支付与抖音支付分别实现创建支付、验签、回调、查询和退款接口。支付是否成功以服务端回调和主动查询为准，不信任客户端结果。

## 9. 文件上传

管理后台和小程序上传文件时，默认采用对象存储直传：

1. 客户端向 FastAPI 申请临时上传凭证或预签名 URL。
2. 客户端直接上传到对象存储。
3. 客户端把对象 key 提交给业务 API。
4. 数据库保存对象 key，不保存临时签名 URL。

不得把大文件全部转发经过 FastAPI 服务。

## 10. 安全和合规

- 密钥、AppSecret、支付证书和数据库密码只能通过环境变量或密钥管理服务提供。
- `.env`、私钥、真实用户数据不得提交到 Git。
- 客户手机号等个人信息需要权限控制、日志审计和界面脱敏。
- 服务端必须实施参数校验、权限校验、限流和必要的幂等控制。
- 小程序需要配置 HTTPS 合法域名、隐私政策、用户授权说明和平台要求的备案信息。
- 日志不得记录 access token、完整手机号、支付密钥或其他敏感信息。

## 11. 测试要求

- 后端核心 service、权限、订单状态和支付回调必须有 pytest 测试。
- API 集成测试使用独立测试数据库。
- 前端纯函数和关键状态逻辑编写单元测试。
- 商品上下架、用户登录、创建订单和支付回调必须覆盖成功及失败路径。
- 小程序发布前必须分别通过微信、抖音开发者工具及真机测试。

## 12. AI 编码规则

AI 在实现需求时必须遵守：

1. 修改代码前阅读本文档、项目 README 和相关现有代码。
2. 优先延续现有模块和代码风格，不擅自引入新的框架或状态管理库。
3. 不得将 Taro 替换为 uni-app，不得将 FastAPI 替换为 Django、Flask 或其他后端框架。
4. 不得将管理后台替换为 Next.js、Umi 或低代码框架。
5. 新依赖必须有明确必要性，不得为简单功能引入大型依赖。
6. 平台差异必须在 provider/platform 适配层处理。
7. 新增数据库字段或表时，同时创建 Alembic migration。
8. 新增或修改 API 时，同步更新 OpenAPI 客户端及相关测试。
9. 不得硬编码密钥、平台 AppID、域名或生产配置。
10. 不得用模拟数据掩盖未完成的后端功能。
11. 完成代码后运行相关 lint、类型检查和测试，并报告未执行的验证项。
12. 未经明确要求，不做与当前需求无关的大规模重构。

## 13. 非目标技术

除非需求明确变更，本项目不使用：

- uni-app。
- Vue。
- React Native。
- Next.js 或服务端渲染。
- Django Admin 作为正式运营后台。
- GraphQL。
- 微服务拆分。
- Kubernetes。

第一阶段采用模块化单体 FastAPI 服务。只有在实际业务规模和团队边界证明有必要时，才考虑拆分服务。

## 14. 决策优先级

发生冲突时按以下优先级处理：

1. 当前明确的产品需求和安全要求。
2. 本技术规范。
3. 仓库中的既有架构和代码约定。
4. 官方文档与官方 SDK。
5. 第三方开源示例。

任何核心技术变更必须先更新本文档，并说明变更原因、迁移成本和兼容性影响。
