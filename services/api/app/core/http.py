import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

logger = structlog.get_logger("app.access")

# 健康检查每 5 秒一次（deploy/compose.yaml 的 api healthcheck），
# 一天 1.7 万条，全是 200，记下来只会把真正的请求冲掉。
_UNLOGGED_PATHS = frozenset({"/health"})


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """贯穿请求的 request_id，外加一条结构化访问日志。

    request_id 同时绑到 structlog 的 contextvars 上：`configure_logging()`
    的处理链里一直有 `merge_contextvars`，但在此之前没有任何地方往里绑过值，
    所以业务代码打的日志无法和具体请求对应起来——出错时只能看到一条孤立的
    消息，没法顺着 request_id 把整条链路串起来。
    """
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id

    # clear 在前：同一个 worker 线程/协程会被复用，不清掉的话上一个请求
    # 绑的字段会泄漏到下一个请求的日志里。
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    # perf_counter 而不是 time()：后者受系统时钟调整影响，可能算出负耗时。
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # 未捕获异常同样要留下访问日志，否则「请求进来了但没有任何记录」
        # 是最难排查的一种情况。异常本身由 unhandled_exception_handler 记录。
        _log_access(request, status_code=500, started=started)
        raise

    _log_access(request, status_code=response.status_code, started=started)
    response.headers["X-Request-ID"] = request_id
    return response


def _log_access(request: Request, *, status_code: int, started: float) -> None:
    if request.url.path in _UNLOGGED_PATHS:
        return
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    # 5xx 用 warning 级别，这样按级别过滤就能捞出所有服务端故障。
    log = logger.warning if status_code >= 500 else logger.info
    log(
        "http_request",
        method=request.method,
        # 用 route path 而不是原始 URL：/appointments/{id} 这种带 UUID 的
        # 路径如果按原样记，日志聚合时每条都是独立的一组，统计不出接口维度。
        path=_route_path(request),
        status_code=status_code,
        duration_ms=duration_ms,
    )


def _route_path(request: Request) -> str:
    """把真实路径还原成路由模板。

    /stores/<uuid>/appointments → /stores/{store_id}/appointments

    为什么不直接用 `scope["route"].path`：FastAPI 0.141 起 include_router
    不再把子路由摊平到 app.routes 上，而是保留 `_IncludedRouter` 节点，
    `scope["route"]` 拿到的是叶子路由，`.path` 只有最后一段
    （/api/v1/app/me 会变成 /me）。完整前缀藏在
    `scope["fastapi"]["included_router"].include_context.prefix` 里，
    但那是私有属性，升级就可能失效。

    这里改成从 `path_params` 反查——两者都是公开的 ASGI scope 键，
    不依赖任何框架内部结构。路由没匹配上（404）时 path_params 为空，
    直接返回真实路径。
    """
    path = request.url.path
    path_params = request.scope.get("path_params")
    if not path_params:
        return path

    # 按值反查参数名。大小写不敏感：UUID 在 URL 里大小写都合法，
    # 但 path_params 里存的是原样字符串。
    by_value = {str(value).lower(): name for name, value in path_params.items()}
    return "/".join(
        f"{{{by_value[segment.lower()]}}}" if segment.lower() in by_value else segment
        for segment in path.split("/")
    )


def request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else "unknown"


async def http_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    if not isinstance(exception, HTTPException):
        raise exception
    message = exception.detail if isinstance(exception.detail, str) else "请求处理失败"
    return JSONResponse(
        status_code=exception.status_code,
        content={
            "code": f"HTTP_{exception.status_code}",
            "message": message,
            "request_id": request_id(request),
        },
        headers=exception.headers,
    )


async def validation_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    if not isinstance(exception, RequestValidationError):
        raise exception
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "请求参数不符合要求",
            "request_id": request_id(request),
            "details": jsonable_encoder(exception.errors()),
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    """未捕获异常的兜底。

    不注册这个 handler 时，Starlette 返回的是 `text/plain` 的
    "Internal Server Error"，既不带 request_id，也不符合项目统一的
    `{code, message, request_id}` 错误契约（见 app/schemas/error.py）。
    实测确认过：500 响应连 X-Request-ID 响应头都没有，用户报错时
    拿不到任何可用于定位的线索。

    异常详情只进日志，不进响应体——堆栈里常有 SQL 和参数值。
    """
    logger.exception(
        "unhandled_exception",
        method=request.method,
        path=_route_path(request),
        exc_type=type(exception).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务暂时不可用，请稍后重试",
            "request_id": request_id(request),
        },
        headers={"X-Request-ID": request_id(request)},
    )
