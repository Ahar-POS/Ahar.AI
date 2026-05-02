"""
Revenue Monitor Service — hourly anomaly detection.

Called by the orchestrator every hour (CronTrigger minute=5).
Publishes 'revenue.anomaly' to the event bus if current-hour revenue
falls below REVENUE_ANOMALY_THRESHOLD × historical same-hour same-weekday average.

Compares same weekday to avoid Monday-vs-Saturday distortion.
Requires REVENUE_ANOMALY_MIN_HISTORY_DAYS matching days before firing.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from app.core.database import get_database
from app.core.config import get_settings
from app.services.event_bus import get_event_bus
from app.utils.timezone import now_ist

logger = logging.getLogger(__name__)

RESTAURANT_ID = "antera_jubilee_hills"


class RevenueMonitorService:

    async def check_hourly_revenue(self) -> Optional[Dict[str, Any]]:
        """
        Compare this hour's revenue against the 30-day historical average
        for the same hour and weekday.

        Returns the anomaly dict if an anomaly is detected, else None.
        Also publishes 'revenue.anomaly' on the event bus when anomaly fires.
        """
        settings = get_settings()
        db = get_database()
        now = now_ist()
        current_hour = now.hour
        current_weekday = now.weekday()

        # Today midnight UTC (matches how order_date is stored)
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # ── 1. Current-hour revenue ──────────────────────────────────────────
        pipeline_today = [
            {"$match": {
                "restaurant_id": RESTAURANT_ID,
                "status": {"$in": ["completed", "COMPLETED"]},
                "order_date": today_midnight,
                "order_hour": current_hour,
            }},
            {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}},
        ]
        today_result = await db.orders.aggregate(pipeline_today).to_list(1)
        current_revenue_paise = today_result[0]["total"] if today_result else 0

        # ── 2. Historical avg — same hour, same weekday, last 30 days ────────
        history_start = today_midnight - timedelta(days=30)

        pipeline_hist = [
            {"$match": {
                "restaurant_id": RESTAURANT_ID,
                "status": {"$in": ["completed", "COMPLETED"]},
                "order_date": {"$gte": history_start, "$lt": today_midnight},
                "order_hour": current_hour,
                "order_weekday": current_weekday,
            }},
            # Sum revenue per matching day
            {"$group": {
                "_id": "$order_date",
                "day_total": {"$sum": "$total_amount"},
            }},
            # Average across those days
            {"$group": {
                "_id": None,
                "avg": {"$avg": "$day_total"},
                "day_count": {"$sum": 1},
            }},
        ]
        hist_result = await db.orders.aggregate(pipeline_hist).to_list(1)

        if not hist_result:
            logger.info(f"Revenue monitor: no history for hour={current_hour} weekday={current_weekday}")
            return None

        hist_avg_paise = hist_result[0]["avg"]
        day_count = hist_result[0]["day_count"]

        if day_count < settings.REVENUE_ANOMALY_MIN_HISTORY_DAYS:
            logger.info(
                f"Revenue monitor: insufficient history ({day_count} days < "
                f"{settings.REVENUE_ANOMALY_MIN_HISTORY_DAYS}) for hour={current_hour}"
            )
            return None

        if hist_avg_paise <= 0:
            return None

        # ── 3. Detect anomaly ────────────────────────────────────────────────
        ratio = current_revenue_paise / hist_avg_paise

        if ratio >= settings.REVENUE_ANOMALY_THRESHOLD:
            logger.debug(
                f"Revenue normal: hour={current_hour}, "
                f"current=₹{current_revenue_paise/100:.0f}, "
                f"avg=₹{hist_avg_paise/100:.0f}, ratio={ratio:.2f}"
            )
            return None

        anomaly: Dict[str, Any] = {
            "alert_type": "revenue_anomaly",
            "hour": current_hour,
            "weekday": current_weekday,
            "current_revenue_inr": round(current_revenue_paise / 100, 2),
            "historical_avg_inr": round(hist_avg_paise / 100, 2),
            "ratio": round(ratio, 3),
            "threshold": settings.REVENUE_ANOMALY_THRESHOLD,
            "history_days": day_count,
            "severity": "high" if ratio < 0.40 else "medium",
            "detected_at": now.isoformat(),
            "restaurant_id": RESTAURANT_ID,
        }

        logger.warning(
            f"Revenue anomaly: hour={current_hour}, "
            f"current=₹{anomaly['current_revenue_inr']:.0f}, "
            f"avg=₹{anomaly['historical_avg_inr']:.0f}, ratio={ratio:.2f}"
        )

        # Publish so orchestrator can trigger financial agent + write alert
        get_event_bus().publish("revenue.anomaly", anomaly)
        return anomaly


_instance: Optional[RevenueMonitorService] = None


def get_revenue_monitor() -> RevenueMonitorService:
    global _instance
    if _instance is None:
        _instance = RevenueMonitorService()
    return _instance
