"""可观测性：访问日志、500 错误契约、Sentry 初始化。

这三样在 2026-09-15 之前都是缺的：
- 未捕获异常返回的是 text/plain 的 "Internal Server Error"，
  不带 request_id，也不符合 app/schemas/error.py 的错误契约；
- `configure_logging()` 的处理链里有 `merge_contextvars`，
  但没有任何地方往 contextvars 里绑过值，日志和请求对不上；
- `sentry-sdk[fastapi]` 在依赖里、`SENTRY_DSN` 写进了 .env.example、
  compose 和生产部署文档，但 `sentry_sdk.init()` 从没被调用过。
"""

import json
import logging
from typing import Any
from uuid import uuid4

import pytest
import structlog
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.observability import _scrub_event, configure_sentry
from app.main import app
from app.schemas.error import ErrorResponse

_BOOM_PATH = "/__test_boom"


def _access_entries(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    """从 caplog 里取出访问日志。

    structlog 走 stdlib logger，caplog 才能抓到；JSONRenderer 的输出是
    一整条 JSON 字符串，所以解析 message 而不是读 record 的属性。
    """
    return [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "app.access"
    ]


@pytest.fixture
def boom_route():
    """临时挂一个必然抛异常的路由，测完摘掉。

    直接改造某个真实接口去抛异常会污染其他用例，所以单独挂一条。
    """
    router = APIRouter()

    @router.get(_BOOM_PATH)
    async def _boom() -> dict[str, str]:
        raise RuntimeError("用于测试的未预期异常")

    app.include_router(router)
    try:
        yield
    finally:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != _BOOM_PATH
        ]
        app.openapi_schema = None


@pytest.mark.asyncio
async def test_unhandled_exception_returns_error_contract(boom_route) -> None:
    """未捕获异常必须返回统一错误契约，而不是裸的 text/plain 500。"""
    async with AsyncClient(
        # raise_app_exceptions=False 才能拿到响应而不是异常本身。
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            _BOOM_PATH, headers={"X-Request-ID": "given-request-id"}
        )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    # 用响应模型本身校验，字段名对不上就会在这里失败。
    payload = ErrorResponse.model_validate(response.json())
    assert payload.code == "INTERNAL_ERROR"
    # 客户端传来的 request_id 要被沿用，这样用户报错时能直接对上服务端日志。
    assert payload.request_id == "given-request-id"
    assert response.headers["x-request-id"] == "given-request-id"


@pytest.mark.asyncio
async def test_unhandled_exception_body_leaks_no_internals(boom_route) -> None:
    """响应体里不能出现异常类型或异常消息——堆栈里常有 SQL 和参数值。"""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.get(_BOOM_PATH)

    body = response.text
    assert "RuntimeError" not in body
    assert "用于测试的未预期异常" not in body
    assert "Traceback" not in body


@pytest.mark.asyncio
async def test_failed_request_is_logged_at_warning_level(
    boom_route,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """500 请求必须留下访问日志，而且级别是 warning。

    两条都是实现里写进注释、但此前没有任何用例守住的行为：

    - 未捕获异常时 `call_next` 会抛出，如果只在正常返回路径上记日志，
      崩掉的请求就「进来了但没有任何记录」——这是最难排查的一种情况，
      运维只能看到用户报错，日志里却什么都搜不到。
    - 级别用 warning 而不是 info，是为了能直接按级别过滤捞出所有
      服务端故障；退回 info 之后这个筛选条件就失效了，500 会淹没在
      正常流量里。
    """
    with caplog.at_level(logging.INFO, logger="app.access"):
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client:
            response = await client.get(_BOOM_PATH)

    assert response.status_code == 500
    # 按 event 过滤：异常路径上 app.access 会产出两条记录——中间件的
    # http_request 访问日志，和兜底 handler 的 unhandled_exception
    # （后者带堆栈，排在后面）。这里要断言的是前者。
    entries = [
        entry for entry in _access_entries(caplog) if entry["event"] == "http_request"
    ]
    assert entries, "500 请求没有留下访问日志"
    entry = entries[-1]
    assert entry["status_code"] == 500
    assert entry["level"] == "warning", f"5xx 没有用 warning 级别：{entry}"


@pytest.mark.asyncio
async def test_access_log_carries_request_id_and_route_template(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """访问日志要带 request_id、路由模板、状态码和耗时。"""
    with caplog.at_level(logging.INFO, logger="app.access"):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                "/api/v1/app/me", headers={"X-Request-ID": "trace-me-123"}
            )

    # 客户端传来的 id 要原样回到响应头，否则前端拿不到能上报的追踪号。
    assert response.headers["x-request-id"] == "trace-me-123"

    entries = _access_entries(caplog)
    assert entries, "没有产生任何访问日志"
    entry = entries[-1]
    assert entry["event"] == "http_request"
    assert entry["request_id"] == "trace-me-123"
    assert entry["method"] == "GET"
    assert entry["path"] == "/api/v1/app/me"
    assert entry["status_code"] == 401  # 没带 token，本来就该 401
    assert isinstance(entry["duration_ms"], int | float)


@pytest.mark.asyncio
async def test_access_log_collapses_path_parameters_into_template(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """带路径参数的接口要按路由模板记，不能原样记 UUID。

    上一条用例打的是 /api/v1/app/me——它没有路径参数，模板和真实路径
    完全一样，所以那条用例其实分辨不出 `_route_path()` 到底有没有做还原。
    这条专门打一个带参数的路由把缺口补上：真实路径里的 UUID 若被原样
    写进日志，日志聚合时每个 UUID 都会成为独立的一组，统计不出接口
    维度的 QPS 和错误率。
    """
    schedule_id = uuid4()
    with caplog.at_level(logging.INFO, logger="app.access"):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # 不带 token 会 401，但路由此时已经匹配上，path_params 已填充。
            response = await client.post(
                f"/api/v1/app/schedules/{schedule_id}/appointments", json={}
            )

    assert response.status_code == 401
    entry = _access_entries(caplog)[-1]
    assert entry["path"] == "/api/v1/app/schedules/{schedule_id}/appointments"
    assert str(schedule_id) not in entry["path"]


@pytest.mark.asyncio
async def test_health_check_is_not_access_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """/health 每 5 秒被探活一次，记下来会把真实请求冲掉。"""
    with caplog.at_level(logging.INFO, logger="app.access"):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert not _access_entries(caplog), "/health 被写进了访问日志"
    # 不记日志 ≠ 不回 request_id：探活失败时运维仍要能拿着这个 id 查链路。
    # 这也是唯一覆盖「成功响应回写 X-Request-ID」的地方——
    # 500 那条走的是 handler 自己的 headers= 参数，管不到中间件这一行。
    assert response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_contextvars_do_not_leak_into_next_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """contextvars 必须逐请求清理，否则上一个请求绑的字段会串到下一个。

    断言的是「访问日志实际带了什么」，而不是请求结束后 `get_contextvars()`
    的残留：中间件每次都会无条件绑 request_id，所以即使 clear 被摘掉，
    事后读到的仍是本请求自己的 id，串号根本看不出来。

    污染源必须放在客户端调用之前。`BaseHTTPMiddleware` 把 `call_next`
    放进子任务，路由内部绑的字段传不回中间件（实测确认过），
    所以只有「外层已有残留」这个方向可观测——而它也正是真实的故障形态：
    同一协程被复用时，上一个请求绑的 user_id / store_id 会留在里面。
    """
    structlog.contextvars.bind_contextvars(stale_field="来自上一个请求")
    try:
        with caplog.at_level(logging.INFO, logger="app.access"):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                await client.get("/api/v1/app/me")
    finally:
        # 无论断言是否通过都要清掉，否则污染后续用例。
        structlog.contextvars.clear_contextvars()

    entry = _access_entries(caplog)[-1]
    assert "stale_field" not in entry, f"上一个请求的字段串进了本次日志：{entry}"
    assert entry["request_id"]


def test_create_app_wires_sentry(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_app() 必须真的调用 configure_sentry。

    下面两条 Sentry 用例都是直接调 configure_sentry()，所以即使有人把
    main.py 里的调用删掉，它们依然全绿——Sentry 会静默失效，而这正是
    这一整块代码要解决的问题本身（原本就是「依赖装了、DSN 配了、
    init 从没被调用」）。这条用例专门守住接线。
    """
    import app.main as main_module

    calls: list[Settings] = []
    monkeypatch.setattr(
        main_module,
        "configure_sentry",
        lambda settings: bool(calls.append(settings)),
    )

    main_module.create_app()

    assert len(calls) == 1, "create_app() 没有调用 configure_sentry"
    # 必须传真实配置。get_settings() 带 lru_cache，同一实例可以直接比身份；
    # 若传的是临时构造的 Settings，线上的 DSN 就读不到。
    assert calls[0] is get_settings()


def test_sentry_is_skipped_without_dsn() -> None:
    """没配 DSN 时不初始化——本地和 CI 都不该往外发数据。"""
    settings = Settings(
        _env_file=None,
        sentry_dsn=None,
        database_url="postgresql+asyncpg://u:p@localhost/db",
    )
    assert configure_sentry(settings) is False


def test_sentry_initializes_when_dsn_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配了 DSN 就必须真的调用 sentry_sdk.init()。

    这条测试存在的理由：init() 曾经完全没被调用过，
    运维按文档填了 DSN 却一条错误都收不到，而且毫无报错提示。
    这里拦住真实的 init（不建立到 sentry.io 的连接），只断言它被调到、
    以及传进去的参数正确。
    """
    import sentry_sdk

    captured: dict[str, Any] = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: captured.update(kwargs))

    settings = Settings(
        _env_file=None,
        sentry_dsn="https://public@o0.ingest.sentry.io/0",
        app_env="production",
        database_url="postgresql+asyncpg://u:p@localhost/db",
    )
    assert configure_sentry(settings) is True

    assert captured["dsn"] == "https://public@o0.ingest.sentry.io/0"
    assert captured["environment"] == "production"
    # PII 必须关掉：默认行为会把请求体、header、cookie 一起上报，
    # 里面有 Authorization 和学员手机号。
    assert captured["send_default_pii"] is False
    assert 0 < captured["traces_sample_rate"] <= 1


def test_scrub_event_filters_credentials() -> None:
    """兜底清洗：凭证类 header、cookies、请求体都不能发给第三方。"""
    event: Any = {
        "request": {
            "headers": {
                "Authorization": "Bearer real-token",
                "X-Api-Key": "secret",
                "User-Agent": "curl/8",
            },
            "cookies": {"session": "abc"},
            "data": {"password": "hunter2"},
        }
    }
    scrubbed: Any = _scrub_event(event, {})

    headers = scrubbed["request"]["headers"]
    # 大小写不敏感：真实请求头的大小写并不固定。
    assert headers["Authorization"] == "[Filtered]"
    assert headers["X-Api-Key"] == "[Filtered]"
    # 非敏感 header 要保留，否则排障时看不到任何上下文。
    assert headers["User-Agent"] == "curl/8"
    assert "cookies" not in scrubbed["request"]
    assert "data" not in scrubbed["request"]


def test_scrub_event_tolerates_missing_request() -> None:
    """before_send 里一旦抛异常，Sentry 会静默丢掉整个事件。"""
    assert _scrub_event({}, {}) == {}  # type: ignore[arg-type]
