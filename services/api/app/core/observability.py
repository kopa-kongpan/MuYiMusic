"""Sentry 接入。

`sentry-sdk[fastapi]` 一直在依赖里、`SENTRY_DSN` 也一直写在 .env.example、
compose 和生产部署文档里，但全项目从来没有调用过 `sentry_sdk.init()`——
也就是说运维按文档填了 DSN，却一条错误都收不到。这个模块补上这一步。
"""

from typing import Any, cast

import structlog
from sentry_sdk.types import Event

from app.core.config import Settings

logger = structlog.get_logger(__name__)


def configure_sentry(settings: Settings) -> bool:
    """按配置初始化 Sentry，返回是否真的启用了。

    没配 DSN 就跳过（本地开发和 CI 都不该往外发数据），这是正常路径，
    不是错误。
    """
    if not settings.sentry_dsn:
        return False

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        # 采样率：生产全量追踪会又贵又吵，10% 足够看出接口级的性能趋势；
        # 本地/预发环境量本来就小，全量采更好定位问题。
        traces_sample_rate=0.1 if settings.app_env == "production" else 1.0,
        # 发送前钩子里剥掉敏感数据，见下。
        before_send=_scrub_event,
        # 默认会把请求体、header、cookie 一起带上，里面有 Authorization
        # 和手机号。这里关掉，需要的上下文由业务代码显式 set_context。
        send_default_pii=False,
    )
    logger.info("sentry_initialized", environment=settings.app_env)
    return True


# 这些 header 一旦进了 Sentry 就等于把凭证泄露给第三方。
_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "idempotency-key",
    }
)


def _scrub_event(event: Event, hint: dict[str, Any]) -> Event:
    """兜底清洗：即使 send_default_pii=False，也显式再抹一遍敏感 header。

    依赖单一开关不够稳妥——SDK 升级、或某处 set_context 手动塞了 headers，
    都可能把凭证带出去。这里做第二道防线。
    """
    # Event / Request 在 sentry-sdk 里是 TypedDict，逐键改写要写一堆
    # cast；这里统一按普通 dict 处理，运行期本来就是 dict。
    request = cast(dict[str, Any], event).get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                key: ("[Filtered]" if key.lower() in _SENSITIVE_HEADERS else value)
                for key, value in headers.items()
            }
        # cookies 和 body 整体丢掉，业务上排障用不到，风险却很高。
        request.pop("cookies", None)
        request.pop("data", None)
    return event
