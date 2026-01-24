"""
API v1 router configuration.

Aggregates all v1 API routes.
"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.tables import router as tables_router

router = APIRouter()

# Register route modules
router.include_router(health_router, prefix="/health", tags=["Health"])
router.include_router(auth_router)
router.include_router(tables_router)
