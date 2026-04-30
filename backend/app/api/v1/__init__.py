"""
API v1 router configuration.

Aggregates all v1 API routes.
"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.tables import router as tables_router
from app.api.v1.menu import router as menu_router
from app.api.v1.orders import router as orders_router
from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.insights import router as insights_router
from app.api.v1.forecast import router as forecast_router
from app.api.v1.forecast_validation import router as forecast_validation_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.financial import router as financial_router
from app.api.v1.settings import router as settings_router
from app.api.v1.documents import router as documents_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.notifications import router as notifications_router

router = APIRouter()

# Register route modules
router.include_router(health_router, prefix="/health", tags=["Health"])
router.include_router(auth_router)
router.include_router(tables_router)
router.include_router(orders_router)
router.include_router(menu_router)
router.include_router(chatbot_router)
router.include_router(inventory_router)
router.include_router(insights_router)
router.include_router(forecast_router, prefix="/forecast", tags=["Forecast"])
router.include_router(forecast_validation_router, prefix="/forecast/validate", tags=["Forecast Validation"])
router.include_router(approvals_router, prefix="/approvals", tags=["Approvals"])
router.include_router(financial_router, prefix="/financial", tags=["Financial"])
router.include_router(settings_router)
router.include_router(documents_router)
router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(notifications_router)