"""
Financial analytics and alerts API endpoints.
"""

from typing import Optional
from datetime import datetime, timedelta
from app.utils.timezone import now_ist
from fastapi import APIRouter, Query

from app.core.database import get_database
from app.utils.response import success_response, error_response
from app.services.orchestrator import get_orchestrator

router = APIRouter()


@router.get("/alerts")
async def get_financial_alerts(
    status: Optional[str] = Query("active", description="Alert status filter"),
    alert_type: Optional[str] = Query(None, description="Alert type filter"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of alerts")
):
    """
    Get financial alerts with optional filters

    Args:
        status: Filter by status (active, resolved, all)
        alert_type: Filter by type (revenue_anomaly, high_cogs, etc.)
        limit: Maximum results

    Returns:
        List of financial alerts
    """
    try:
        db = get_database()

        # Build query
        query = {}
        if status and status != "all":
            query["status"] = status
        if alert_type:
            query["alert_type"] = alert_type

        # Fetch alerts
        cursor = db.financial_alerts.find(query).sort("created_at", -1).limit(limit)
        alerts = await cursor.to_list(length=limit)

        # Convert ObjectId to string for JSON serialization
        for alert in alerts:
            alert["_id"] = str(alert["_id"])
            if "agent_decision_id" in alert:
                alert["agent_decision_id"] = str(alert["agent_decision_id"])
            # Format dates
            if "created_at" in alert:
                alert["created_at"] = alert["created_at"].isoformat()

        return success_response(
            data=alerts,
            message=f"Found {len(alerts)} financial alerts"
        )

    except Exception as e:
        return error_response(
            code="FETCH_ALERTS_FAILED",
            message="Failed to fetch financial alerts",
            details={"error": str(e)}
        )


@router.get("/alerts/summary")
async def get_alerts_summary():
    """
    Get summary of financial alerts by type and severity

    Returns:
        Alert counts and statistics
    """
    try:
        db = get_database()

        # Count by type
        type_pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {"_id": "$alert_type", "count": {"$sum": 1}}}
        ]
        type_cursor = db.financial_alerts.aggregate(type_pipeline)
        by_type = {doc["_id"]: doc["count"] async for doc in type_cursor}

        # Count by severity
        severity_pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
        ]
        severity_cursor = db.financial_alerts.aggregate(severity_pipeline)
        by_severity = {doc["_id"]: doc["count"] async for doc in severity_cursor}

        # Total counts
        total_active = await db.financial_alerts.count_documents({"status": "active"})
        total_all = await db.financial_alerts.count_documents({})

        return success_response(
            data={
                "total_active_alerts": total_active,
                "total_all_time": total_all,
                "by_type": by_type,
                "by_severity": by_severity
            },
            message="Alert summary retrieved"
        )

    except Exception as e:
        return error_response(
            code="SUMMARY_FAILED",
            message="Failed to generate alert summary",
            details={"error": str(e)}
        )


@router.get("/metrics")
async def get_financial_metrics(
    days_back: int = Query(7, ge=1, le=90, description="Days to analyze")
):
    """
    Get current financial metrics

    Args:
        days_back: Number of days to analyze

    Returns:
        Revenue, COGS, profit margins, and food cost percentage
    """
    try:
        db = get_database()

        end_date = now_ist()
        start_date = end_date - timedelta(days=days_back)

        # Get total revenue
        revenue_pipeline = [
            {
                "$match": {
                    "order_date": {"$gte": start_date, "$lte": end_date},
                    "status": {"$ne": "cancelled"}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_revenue": {"$sum": "$total_amount"},
                    "order_count": {"$sum": 1}
                }
            }
        ]

        cursor = db.orders.aggregate(revenue_pipeline)
        revenue_result = await cursor.to_list(length=1)

        if not revenue_result:
            return success_response(
                data={
                    "period_days": days_back,
                    "total_revenue": 0,
                    "total_orders": 0,
                    "avg_order_value": 0,
                    "avg_daily_revenue": 0,
                    "message": "No order data available for this period"
                }
            )

        total_revenue = revenue_result[0]["total_revenue"]
        order_count = revenue_result[0]["order_count"]
        avg_order_value = total_revenue / order_count if order_count > 0 else 0

        return success_response(
            data={
                "period_days": days_back,
                "total_revenue": total_revenue / 100,  # Paise to rupees
                "total_orders": order_count,
                "avg_order_value": avg_order_value / 100,
                "avg_daily_revenue": (total_revenue / days_back) / 100
            },
            message="Financial metrics retrieved"
        )

    except Exception as e:
        return error_response(
            code="METRICS_FAILED",
            message="Failed to fetch financial metrics",
            details={"error": str(e)}
        )


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """
    Mark an alert as resolved

    Args:
        alert_id: Alert ID to resolve

    Returns:
        Updated alert
    """
    try:
        from bson import ObjectId
        db = get_database()

        result = await db.financial_alerts.update_one(
            {"_id": ObjectId(alert_id)},
            {
                "$set": {
                    "status": "resolved",
                    "resolved_at": now_ist()
                }
            }
        )

        if result.modified_count == 0:
            return error_response(
                code="ALERT_NOT_FOUND",
                message=f"Alert {alert_id} not found or already resolved"
            )

        return success_response(
            data={"alert_id": alert_id, "status": "resolved"},
            message="Alert marked as resolved"
        )

    except Exception as e:
        return error_response(
            code="RESOLVE_FAILED",
            message="Failed to resolve alert",
            details={"error": str(e)}
        )


@router.get("/agent/status")
async def get_agent_status():
    """
    Get financial agent execution status and last run info

    Returns:
        Agent status and recent decisions
    """
    try:
        db = get_database()

        # Get last decision
        cursor = db.agent_decisions.find(
            {"agent_name": "financial_agent"}
        ).sort("timestamp", -1).limit(1)

        last_decision = await cursor.to_list(length=1)

        if not last_decision:
            return success_response(
                data={
                    "status": "never_run",
                    "message": "Financial agent has not run yet"
                }
            )

        decision = last_decision[0]
        decision["_id"] = str(decision["_id"])
        if "timestamp" in decision:
            decision["timestamp"] = decision["timestamp"].isoformat()

        return success_response(
            data={
                "status": "active",
                "last_run": decision,
                "scheduled_time": "23:00 UTC (11 PM daily)"
            },
            message="Financial agent status retrieved"
        )

    except Exception as e:
        return error_response(
            code="STATUS_FAILED",
            message="Failed to get agent status",
            details={"error": str(e)}
        )
