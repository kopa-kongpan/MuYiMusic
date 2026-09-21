# CI/CD 现状与待办

> 更新于 2026-09-15。此前版本称「本项目当前缺少持续集成流程」，这是错的：
> `.github/workflows/ci.yml` 从 2025-08-03（commit `6dbdf8f`）起就已存在，
> 本次又做了一轮修正和补全。

## CI 现状：已落地

工作流文件：`.github/workflows/ci.yml`。同一分支只保留最新一次运行
（`concurrency` + `cancel-in-progress`），连续推送不会排队浪费额度。

| Job          | 做什么                                                                                                          | 状态                            |
| ------------ | --------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| `frontend`   | `pnpm check`（lint + typecheck + test）、`build:admin`、`build:weapp`、`build:tt`                               | ✅ 本地逐条验证通过             |
| `backend`    | `ruff check` / `ruff format --check` / `mypy app` / `alembic upgrade head` / `bootstrap_admin` / `pytest --cov` | ✅ 在全新库上按同样顺序验证通过 |
| `migrations` | 干净库上 `upgrade head` → `downgrade base` → `upgrade head`                                                     | ✅ 已验证可回滚                 |
| `compose`    | `docker compose config` 校验编排文件                                                                            | ✅                              |
| `audit`      | `pnpm audit --audit-level high` + `pip-audit`（`continue-on-error`）                                            | ✅ 不阻塞合并                   |

### 这一轮修掉的坑

写工作流时容易「看起来对」但一推就红，下面几条都是实际跑出来才发现的：

1. **后端 job 没有数据库**。测试直连真实 Postgres（CHECK 约束、
   `SELECT ... FOR UPDATE`、事务隔离换成内存库测不出来）。用一个假的
   `DATABASE_URL` 实测：61 个用例里 **49 个直接失败**。已补
   `postgres:17` + `redis:7` service 容器和健康检查。
2. **`APP_ENV` 不能填 `ci`**。h5 登录通道只在 `app_env == "local"` 时开放
   （见 `app/providers/miniapp_identity.py` 的 `_exchange_local`），
   而测试里的学员登录全走这条路。填 `ci` 的话所有需要学员身份的用例都返回
   503「当前登录平台尚未配置」。已固定为 `local`。
3. **`bootstrap_admin` 的调用方式**。`uv run python scripts/bootstrap_admin.py`
   会 `ModuleNotFoundError: No module named 'app'`；仓库其他地方
   （`deploy/compose.yaml`、部署文档）都用 `python -m scripts.bootstrap_admin`。
   已统一成模块形式。
4. **pnpm 版本不要写死**。原来 CI 固定 11.15.1，而根 `package.json` 的
   `packageManager` 已是 9.15.0。现在不传 version，让 corepack 读
   `packageManager`，两处不会再各说一套。
5. **`pip-audit` 不用 `<(...)` 进程替换**。Actions 默认 shell 下行为不稳定，
   而且失败时看不出是导出本身挂了还是扫描挂了。改成先 `uv export` 成文件。

### 顺带修掉的一个既有测试 bug

`tests/test_config.py` 只要环境里存在 `DATABASE_URL` 就会失败——
`_env_file=None` 只屏蔽 `.env` 文件，不屏蔽真实环境变量，而 CI 里
`DATABASE_URL` 恰恰是环境变量。已显式传 `database_url=None, redis_url=None`
（init 参数在 pydantic-settings 里优先级最高）。

## 测试与覆盖率现状

实测数字（`pytest --cov`，2026-09-15）：

- **61 个用例：59 passed, 2 skipped**（2 个 skip 是既有的旧模型用例，有意跳过）
- **总覆盖率 80%**

覆盖率配置里有一条关键设置，删掉会导致数字严重失真：

```toml
[tool.coverage.run]
concurrency = ["greenlet", "thread"]
```

SQLAlchemy 的 asyncio 层靠 greenlet 切换执行上下文。不声明这一项，覆盖率会在
每个 `await` 进入 greenlet 后丢掉追踪，把实际跑过的业务分支全报成 missing
——`appointment_service` 会从真实的 77% 被误报成 36%，总覆盖率从 80% 误报成 68%。
早先文档里「覆盖率偏低」的结论就是这个测量错误的产物。

覆盖率较低的模块（真实数字，可作为下一轮补测的优先级）：

| 模块                            | 覆盖率 |
| ------------------------------- | ------ |
| `notification_delivery_service` | 18%    |
| `product_repository`            | 57%    |
| `notification_service`          | 63%    |
| `product_service`               | 67%    |

## CD 待办（这部分确实还没做）

- [ ] 自动构建 Docker 镜像并推送到容器镜像仓库
- [ ] 部署到生产环境（建议需手动审批的 environment gate）
- [ ] 部署后健康检查与自动回滚
- [ ] 配置所需 GitHub Secrets（镜像仓库凭证、生产数据库连接等）

现有部署方式见 `docs/腾讯云生产部署说明.md`。

## 可选增强

- [ ] 覆盖率阈值门禁（`--cov-fail-under`）。建议先观察几周真实波动再定值，
      现在设死容易变成「为了过线而写测试」。
- [ ] 代码安全扫描（CodeQL）
- [ ] E2E 测试
