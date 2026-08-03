from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

# Business routers will be mounted below /app, /admin, and /webhooks.
