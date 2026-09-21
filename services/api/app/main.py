from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.http import (
    http_exception_handler,
    request_id_middleware,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.core.observability import configure_sentry


def create_app() -> FastAPI:
    configure_logging()
    # 没配 SENTRY_DSN 时这一步直接跳过（本地和 CI 都不该往外发数据）。
    configure_sentry(get_settings())
    application = FastAPI(
        title="MuYiMusic API",
        version="0.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.middleware("http")(request_id_middleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
    # 必须最后注册：它兜住所有未被上面两个 handler 处理的异常。
    application.add_exception_handler(Exception, unhandled_exception_handler)
    application.include_router(health_router)
    application.include_router(v1_router)
    return application


app = create_app()
