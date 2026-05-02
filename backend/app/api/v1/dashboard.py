"""
Owner Dashboard API

Six read-only endpoints for the three-zone owner dashboard.
All require ADMIN role.

Zone 1+2 (pulse, action_queue) — polled every 30s, must stay fast.
Zone 3 (menu_performance, stock_health, pnl_snapshot, revenue_pattern) — on-demand.
"""

import logging
from fastapi import APIRouter, Depends, Query

from app.services.dashboard_service import get_dashboard_service
from app.utils.response import success_response, error_response
from app.core.dependencies import get_admin_user
from app.models.user import UserResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/pulse")
async def get_pulse(
    period: str = Query("today", regex="^(today|last_week|last_month|last_3_months)$"),
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Zone 1: Key metrics for a specific time period.

    Returns revenue, covers, avg ticket, food cost %, attention count.
    """
    try:
        svc = get_dashboard_service()
        data = await svc.get_pulse_metrics(restaurant_id=current_user.restaurant_id, period=period)
        return success_response(data=data, message=f"Pulse metrics for {period} retrieved")
    except Exception as e:
        logger.error(f"Pulse endpoint failed: {e}", exc_info=True)
        return error_response(
            code="PULSE_FAILED",
            message="Failed to retrieve pulse metrics",
            details={"error": str(e)}
        )


@router.get("/action-queue")
async def get_action_queue(
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Zone 2: Actionable cards for the owner.

    Returns low-stock alerts, pending PO approvals, revenue anomalies,
    and expiry-based specials suggestions.
    """
    try:
        svc = get_dashboard_service()
        data = await svc.get_action_queue(restaurant_id=current_user.restaurant_id)
        return success_response(data=data, message="Action queue retrieved")
    except Exception as e:
        logger.error(f"Action queue endpoint failed: {e}", exc_info=True)
        return error_response(
            code="ACTION_QUEUE_FAILED",
            message="Failed to retrieve action queue",
            details={"error": str(e)}
        )


@router.get("/menu-performance")
async def get_menu_performance(
    period_days: int = Query(7, ge=1, le=90, description="Days to analyze"),
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Zone 3: Menu items ranked by contribution margin.

    Returns top 20 items with revenue, profit, margin %, volume,
    and agent annotations where applicable.
    """
    try:
        svc = get_dashboard_service()
        items = await svc.get_menu_performance(restaurant_id=current_user.restaurant_id, period_days=period_days)
        return success_response(
            data={"period_days": period_days, "items": items},
            message=f"Menu performance for last {period_days} days"
        )
    except Exception as e:
        logger.error(f"Menu performance endpoint failed: {e}", exc_info=True)
        return error_response(
            code="MENU_PERF_FAILED",
            message="Failed to retrieve menu performance",
            details={"error": str(e)}
        )


@router.get("/stock-health")
async def get_stock_health(
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Zone 3: Inventory health overview.

    Returns items classified as critical/low/good with agent annotations.
    Items sorted: critical first, then low, then good.
    """
    try:
        svc = get_dashboard_service()
        data = await svc.get_stock_health(restaurant_id=current_user.restaurant_id)
        return success_response(data=data, message="Stock health retrieved")
    except Exception as e:
        logger.error(f"Stock health endpoint failed: {e}", exc_info=True)
        return error_response(
            code="STOCK_HEALTH_FAILED",
            message="Failed to retrieve stock health",
            details={"error": str(e)}
        )


@router.get("/pnl-snapshot")
async def get_pnl_snapshot(
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Zone 3: Month-to-date P&L snapshot.

    Returns revenue, COGS, waste, gross margin %.
    COGS is sourced from stock_movement_log; cogs_data_available flag
    indicates whether the figure is real or missing.
    """
    try:
        svc = get_dashboard_service()
        data = await svc.get_pnl_snapshot(restaurant_id=current_user.restaurant_id)
        return success_response(data=data, message="P&L snapshot retrieved")
    except Exception as e:
        logger.error(f"P&L snapshot endpoint failed: {e}", exc_info=True)
        return error_response(
            code="PNL_FAILED",
            message="Failed to retrieve P&L snapshot",
            details={"error": str(e)}
        )


@router.get("/revenue-pattern")
async def get_revenue_pattern(
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Zone 3: Hourly revenue today vs 30-day historical average.

    Returns 24 hour slots with today vs historical avg and anomaly flags
    (above_normal / below_normal where deviation exceeds 30%).
    """
    try:
        svc = get_dashboard_service()
        data = await svc.get_revenue_pattern(restaurant_id=current_user.restaurant_id)
        return success_response(data=data, message="Revenue pattern retrieved")
    except Exception as e:
        logger.error(f"Revenue pattern endpoint failed: {e}", exc_info=True)
        return error_response(
            code="REVENUE_PATTERN_FAILED",
            message="Failed to retrieve revenue pattern",
            details={"error": str(e)}
        )
