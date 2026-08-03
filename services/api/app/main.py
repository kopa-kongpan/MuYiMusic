from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.router import router as v1_router


def create_app() -> FastAPI:
    application = FastAPI(
        title="MuYiMusic API",
        version="0.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.include_router(health_router)
    application.include_router(v1_router)
    return application


app = create_app()
