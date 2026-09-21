# 后端测试说明

## 怎么跑

```bash
# 全量
pytest

# 单个文件（不跑覆盖率，快）
pytest tests/test_appointment_conflict.py

# 带覆盖率（覆盖率是显式开启的，不在 addopts 里）
pytest --cov --cov-report=term-missing
```

测试直连本地 Postgres（`deploy/` 里的 compose，端口 15432），不使用
内存库——CHECK 约束、`SELECT ... FOR UPDATE`、事务隔离这些行为在
SQLite 上和生产不一致，测不出真问题。

## 两种隔离方式

### 1. `api_context()`（默认，绝大多数测试用这个）

见 `conftest.py`。每个用例开一条连接、开一个事务，
session 用 `join_transaction_mode="create_savepoint"` 绑上去，
用例结束整体回滚。数据不落盘，用例之间互不污染，不需要清理代码。

```python
async with api_context() as ctx:
    world = await build_booking_world(ctx.session)
    user, headers = await create_user_login(ctx.client, ctx.session, "学员")
    ...
```

`conftest.py` 里的工厂：`make_store` / `make_admin` / `make_platform_admin` /
`make_product` / `make_schedule` / `make_entitlement`，以及把
「门店 + 商品 + 教师 + 有权限的管理员」打包好的 `build_booking_world()`。

### 2. 真实连接 + 手工清理（只有并发测试用）

`test_concurrency.py` **不能**用 `api_context()`：
它把所有请求压在同一条连接、同一个事务里，`FOR UPDATE` 拿的是
事务自己已经持有的锁，永远不会真正竞争。那样写出来的并发测试是串行的，
必然通过但什么都没验证。

所以并发测试用 `get_session_factory()` 开真实 session、真实提交，
在 `finally` 里按外键顺序清理（`appointments`、`course_entitlements`
对 `users`/`stores` 都是 RESTRICT，不能指望级联）。

## 已覆盖的核心场景

| 文件                               | 覆盖内容                                                                                       |
| ---------------------------------- | ---------------------------------------------------------------------------------------------- |
| `test_appointment_conflict.py`     | 名额上限、同学员时段重叠、紧邻时段边界、教师停用、幂等键跨排课复用                             |
| `test_appointment_cancellation.py` | 截止时间前后取消、管理员绕过截止、重复取消幂等、名额释放后可被候补、越权取消、取消归因字段     |
| `test_class_credits.py`            | 正常消课、缺席扣课、撤销恢复、重复撤销拦截、课程未结束不可消课、课时耗尽后不可预约             |
| `test_permissions.py`              | 权限码缺失 403、跨门店 404（不泄露存在性）、平台域与门店域隔离、token 类型混用、停用管理员失效 |
| `test_concurrency.py`              | 并发抢同一名额不超卖、幂等键并发重放只落一条、失败请求完整回滚不留幽灵占位                     |

## 待补

按覆盖率缺口排序（`pytest --cov` 看 `Missing` 列）：

- `notification_delivery_service`（最低）——微信订阅消息投递、重试、失败降级
- `schedule_service` —— 排课创建/改期/停课对已有预约的影响
- `product_service` —— 上下架状态流转、SKU 与课程权益绑定
- `user_service` —— 权益发放、课时手工调整的审计
- 视频课程播放权限（`video_*`）
- 订单状态流转
