"""
Operations Pulse Service — multi-dimensional restaurant health checker.

Called by the orchestrator every hour. Runs 7 checks in parallel and publishes
typed events for each anomaly detected. Replaces the old single-check
RevenueMonitorService.

Events published:
  operations.revenue_anomaly   — hourly revenue below threshold
  operations.channel_dip       — a sales channel (Swiggy/Zomato/Walk-in) is underperforming
  operations.kitchen_slow      — kitchen preparation latency has spiked
  operations.high_cancellations — cancellation rate above baseline + delta
  operations.aov_drop          — average order value below threshold
  operations.table_stale       — occupied table with no active order for >20 min
  operations.dead_period       — no completed orders in last 30 min during operating hours
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.database import get_database
from app.models.order import OrderChannel, OrderStatus
from app.services.event_bus import get_event_bus
from app.utils.timezone import now_ist

logger = logging.getLogger(__name__)

RESTAURANT_ID = "antera_jubilee_hills"

# Some older documents store status in uppercase; match both variants.
_COMPLETED_STATUS = {"$in": [OrderStatus.COMPLETED.value, OrderStatus.COMPLETED.value.upper()]}
_CANCELLED_STATUS = {"$in": [OrderStatus.CANCELLED.value, OrderStatus.CANCELLED.value.upper()]}
_ACTIVE_STATUSES = [
    OrderStatus.SENT_TO_KITCHEN.value, OrderStatus.SENT_TO_KITCHEN.value.upper(),
    OrderStatus.IN_PROGRESS.value, OrderStatus.IN_PROGRESS.value.upper(),
    OrderStatus.DRAFT.value, OrderStatus.DRAFT.value.upper(),
]


class OperationsPulseService:
    """
    Runs all operational health checks and publishes events.
    Each check is self-contained and fails silently to avoid blocking others.
    """

    async def run_all_checks(self, restaurant_id: str = RESTAURANT_ID) -> None:
        """Entry point called by orchestrator on schedule."""
        await asyncio.gather(
            self._check_revenue_anomaly(restaurant_id),
            self._check_channel_revenue(restaurant_id),
            self._check_kitchen_bottleneck(restaurant_id),
            self._check_cancellation_rate(restaurant_id),
            self._check_aov_drop(restaurant_id),
            self._check_occupied_tables_no_orders(restaurant_id),
            self._check_dead_period(restaurant_id),
            return_exceptions=True,  # one failing check doesn't kill the rest
        )
        await get_event_bus().publish("operations.pulse_completed", {
            "completed_at": now_ist().isoformat(),
            "restaurant_id": restaurant_id,
        })

    # ── Check 1: Revenue anomaly ──────────────────────────────────────────────

    async def _check_revenue_anomaly(self, restaurant_id: str) -> None:
        """Compare this hour's revenue to 30-day daily average normalised per operating hour."""
        settings = get_settings()
        db = get_database()
        now = now_ist()
        current_hour = now.hour
        current_weekday = now.weekday()
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        operating_hours = settings.PULSE_DEAD_PERIOD_MINUTES and 12  # assume 12-hr window

        # Current hour revenue (orders placed in this calendar hour today)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        pipeline_today = [
            {"$match": {
                "restaurant_id": restaurant_id,
                "status": _COMPLETED_STATUS,
                "order_date": {"$gte": hour_start},
            }},
            {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}},
        ]
        today_result = await db.orders.aggregate(pipeline_today).to_list(1)
        current_revenue = today_result[0]["total"] if today_result else 0

        # Historical baseline: 30-day daily average / operating_hours → expected per-hour revenue
        history_start = today_midnight - timedelta(days=30)
        pipeline_hist = [
            {"$match": {
                "restaurant_id": restaurant_id,
                "status": _COMPLETED_STATUS,
                "order_date": {"$gte": history_start, "$lt": today_midnight},
            }},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$order_date"}}, "day_total": {"$sum": "$total_amount"}}},
            {"$group": {"_id": None, "avg_daily": {"$avg": "$day_total"}, "day_count": {"$sum": 1}}},
        ]
        hist_result = await db.orders.aggregate(pipeline_hist).to_list(1)

        if not hist_result:
            return
        avg_daily = hist_result[0]["avg_daily"]
        day_count = hist_result[0]["day_count"]
        hist_avg = avg_daily / 12  # per-hour expected revenue (12-hr operating window)

        if day_count < settings.PULSE_MIN_HISTORY_DAYS or hist_avg <= 0:
            return

        ratio = current_revenue / hist_avg
        if ratio >= settings.PULSE_REVENUE_THRESHOLD:
            return

        event: Dict[str, Any] = {
            "alert_type": "revenue_anomaly",
            "hour": current_hour,
            "weekday": current_weekday,
            "current_revenue_inr": round(current_revenue / 100, 2),
            "historical_avg_inr": round(hist_avg / 100, 2),
            "ratio": round(ratio, 3),
            "threshold": settings.PULSE_REVENUE_THRESHOLD,
            "history_days": day_count,
            "severity": "high" if ratio < 0.40 else "medium",
            "detected_at": now.isoformat(),
            "restaurant_id": restaurant_id,
        }
        logger.warning(
            "Revenue anomaly: hour=%d, current=₹%.0f, avg=₹%.0f, ratio=%.2f",
            current_hour, current_revenue / 100, hist_avg / 100, ratio,
        )
        await get_event_bus().publish("operations.revenue_anomaly", event)

    # ── Check 2: Channel-specific revenue dip ─────────────────────────────────

    async def _check_channel_revenue(self, restaurant_id: str) -> None:
        """Detect if any sales channel is underperforming vs its baseline."""
        settings = get_settings()
        db = get_database()
        now = now_ist()
        current_hour = now.hour
        current_weekday = now.weekday()
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        history_start = today_midnight - timedelta(days=30)

        channels = [c.value for c in OrderChannel]
        dipping_channels = []

        for channel in channels:
            # Today's orders for this channel (since midnight)
            today_result = await db.orders.aggregate([
                {"$match": {
                    "restaurant_id": restaurant_id,
                    "status": _COMPLETED_STATUS,
                    "order_channel": channel,
                    "order_date": {"$gte": today_midnight},
                }},
                {"$group": {"_id": None, "total": {"$sum": "$total_amount"}, "count": {"$sum": 1}}},
            ]).to_list(1)

            current_rev = today_result[0]["total"] if today_result else 0
            current_count = today_result[0]["count"] if today_result else 0

            # History: daily average for this channel over last 30 days
            hist_result = await db.orders.aggregate([
                {"$match": {
                    "restaurant_id": restaurant_id,
                    "status": _COMPLETED_STATUS,
                    "order_channel": channel,
                    "order_date": {"$gte": history_start, "$lt": today_midnight},
                }},
                {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$order_date"}}, "day_total": {"$sum": "$total_amount"}}},
                {"$group": {"_id": None, "avg": {"$avg": "$day_total"}, "day_count": {"$sum": 1}}},
            ]).to_list(1)

            if not hist_result:
                continue
            hist_avg = hist_result[0]["avg"]
            day_count = hist_result[0]["day_count"]

            if day_count < settings.PULSE_MIN_HISTORY_DAYS or hist_avg <= 0:
                continue

            # Scale historical daily avg to elapsed hours today for a fair comparison
            elapsed_hours = max(current_hour - 11 + 1, 1)  # hours since 11 AM open
            expected_rev = hist_avg * elapsed_hours / 12
            ratio = current_rev / expected_rev if expected_rev > 0 else 1.0
            if ratio >= settings.PULSE_CHANNEL_THRESHOLD:
                continue

            dipping_channels.append({
                "channel": channel,
                "current_revenue_inr": round(current_rev / 100, 2),
                "current_order_count": current_count,
                "historical_avg_inr": round(hist_avg / 100, 2),
                "ratio": round(ratio, 3),
                "zero_orders": current_count == 0,
            })

        if not dipping_channels:
            return

        logger.warning(
            "Channel dip: %d channel(s) down — worst ratio=%.2f (%s)",
            len(dipping_channels),
            min(c["ratio"] for c in dipping_channels),
            ", ".join(c["channel"] for c in dipping_channels),
        )
        await get_event_bus().publish("operations.channel_dip", {
            "alert_type": "channel_dip",
            "hour": current_hour,
            "channels": dipping_channels,
            "channel_count": len(dipping_channels),
            "worst_ratio": round(min(c["ratio"] for c in dipping_channels), 3),
            "threshold": settings.PULSE_CHANNEL_THRESHOLD,
            "severity": "high" if any(c["zero_orders"] for c in dipping_channels) else "medium",
            "detected_at": now.isoformat(),
            "restaurant_id": restaurant_id,
        })

    # ── Check 3: Kitchen bottleneck ───────────────────────────────────────────

    async def _check_kitchen_bottleneck(self, restaurant_id: str) -> None:
        """Detect if avg kitchen preparation time has spiked vs baseline."""
        settings = get_settings()
        db = get_database()
        now = now_ist()
        window_start = now - timedelta(hours=1)
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        history_start = today_midnight - timedelta(days=30)

        # Average prep time (seconds) for COMPLETED orders in last hour
        recent_result = await db.orders.aggregate([
            {"$match": {
                "restaurant_id": restaurant_id,
                "status": _COMPLETED_STATUS,
                "sent_to_kitchen_at": {"$gte": window_start},
                "completed_at": {"$ne": None},
            }},
            {"$project": {
                "prep_seconds": {"$subtract": ["$completed_at", "$sent_to_kitchen_at"]},
            }},
            {"$group": {"_id": None, "avg_ms": {"$avg": "$prep_seconds"}, "count": {"$sum": 1}}},
        ]).to_list(1)

        if not recent_result or recent_result[0]["count"] < 3:
            return  # too few orders to be meaningful

        avg_recent_ms = recent_result[0]["avg_ms"]

        # Historical baseline — overall avg prep time across last 30 days
        hist_result = await db.orders.aggregate([
            {"$match": {
                "restaurant_id": restaurant_id,
                "status": _COMPLETED_STATUS,
                "order_date": {"$gte": history_start, "$lt": today_midnight},
                "sent_to_kitchen_at": {"$ne": None},
                "completed_at": {"$ne": None},
            }},
            {"$project": {
                "order_date": 1,
                "prep_ms": {"$subtract": ["$completed_at", "$sent_to_kitchen_at"]},
            }},
            {"$group": {"_id": "$order_date", "day_avg_ms": {"$avg": "$prep_ms"}}},
            {"$group": {"_id": None, "avg_ms": {"$avg": "$day_avg_ms"}, "day_count": {"$sum": 1}}},
        ]).to_list(1)

        if not hist_result:
            return
        hist_avg_ms = hist_result[0]["avg_ms"]
        day_count = hist_result[0]["day_count"]

        if day_count < settings.PULSE_MIN_HISTORY_DAYS or hist_avg_ms <= 0:
            return

        multiplier = avg_recent_ms / hist_avg_ms
        if multiplier < settings.PULSE_KITCHEN_LATENCY_MULTIPLIER:
            return

        avg_recent_min = avg_recent_ms / 60000
        hist_avg_min = hist_avg_ms / 60000
        event: Dict[str, Any] = {
            "alert_type": "kitchen_slow",
            "hour": current_hour,
            "avg_prep_minutes": round(avg_recent_min, 1),
            "historical_avg_minutes": round(hist_avg_min, 1),
            "multiplier": round(multiplier, 2),
            "severity": "high" if multiplier >= 2.0 else "medium",
            "detected_at": now.isoformat(),
            "restaurant_id": restaurant_id,
        }
        logger.warning(
            "Kitchen slow: avg=%.1fmin, baseline=%.1fmin, multiplier=%.2f",
            avg_recent_min, hist_avg_min, multiplier,
        )
        await get_event_bus().publish("operations.kitchen_slow", event)

    # ── Check 4: Cancellation rate spike ─────────────────────────────────────

    async def _check_cancellation_rate(self, restaurant_id: str) -> None:
        """Detect if cancellation rate has spiked above baseline + threshold."""
        settings = get_settings()
        db = get_database()
        now = now_ist()
        window_start = now - timedelta(hours=2)
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        history_start = today_midnight - timedelta(days=30)
        current_hour = now.hour
        current_weekday = now.weekday()

        # Current 2-hour window
        recent_result = await db.orders.aggregate([
            {"$match": {
                "restaurant_id": restaurant_id,
                "created_at": {"$gte": window_start},
            }},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "cancelled": {"$sum": {"$cond": [{"$in": ["$status", _CANCELLED_STATUS["$in"]]}, 1, 0]}},
            }},
        ]).to_list(1)

        if not recent_result or recent_result[0]["total"] < 5:
            return  # not enough orders for a meaningful rate

        total = recent_result[0]["total"]
        cancelled = recent_result[0]["cancelled"]
        current_rate = cancelled / total

        # Historical baseline — daily cancellation rate over last 30 days
        hist_result = await db.orders.aggregate([
            {"$match": {
                "restaurant_id": restaurant_id,
                "order_date": {"$gte": history_start, "$lt": today_midnight},
            }},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$order_date"}},
                "total": {"$sum": 1},
                "cancelled": {"$sum": {"$cond": [{"$in": ["$status", _CANCELLED_STATUS["$in"]]}, 1, 0]}},
            }},
            {"$project": {"rate": {"$divide": ["$cancelled", "$total"]}}},
            {"$group": {"_id": None, "avg_rate": {"$avg": "$rate"}, "day_count": {"$sum": 1}}},
        ]).to_list(1)

        if not hist_result:
            return
        hist_rate = hist_result[0]["avg_rate"]
        day_count = hist_result[0]["day_count"]

        if day_count < settings.PULSE_MIN_HISTORY_DAYS:
            return

        spike = current_rate - hist_rate
        if spike < settings.PULSE_CANCELLATION_SPIKE_PP:
            return

        event: Dict[str, Any] = {
            "alert_type": "high_cancellations",
            "hour": current_hour,
            "current_cancellation_rate": round(current_rate, 3),
            "historical_rate": round(hist_rate, 3),
            "spike_pp": round(spike, 3),
            "cancelled_orders": cancelled,
            "total_orders": total,
            "severity": "high" if spike > 0.25 else "medium",
            "detected_at": now.isoformat(),
            "restaurant_id": restaurant_id,
        }
        logger.warning(
            "High cancellations: rate=%.1f%% vs baseline=%.1f%% (spike=+%.1fpp)",
            current_rate * 100, hist_rate * 100, spike * 100,
        )
        await get_event_bus().publish("operations.high_cancellations", event)

    # ── Check 5: Average order value drop ─────────────────────────────────────

    async def _check_aov_drop(self, restaurant_id: str) -> None:
        """Detect if average order value has dropped below 75% of baseline."""
        settings = get_settings()
        db = get_database()
        now = now_ist()
        current_hour = now.hour
        current_weekday = now.weekday()
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        history_start = today_midnight - timedelta(days=30)

        today_result = await db.orders.aggregate([
            {"$match": {
                "restaurant_id": restaurant_id,
                "status": _COMPLETED_STATUS,
                "order_date": {"$gte": today_midnight},
            }},
            {"$group": {"_id": None, "avg_aov": {"$avg": "$total_amount"}, "count": {"$sum": 1}}},
        ]).to_list(1)

        if not today_result or today_result[0]["count"] < 3:
            return

        current_aov = today_result[0]["avg_aov"]

        hist_result = await db.orders.aggregate([
            {"$match": {
                "restaurant_id": restaurant_id,
                "status": _COMPLETED_STATUS,
                "order_date": {"$gte": history_start, "$lt": today_midnight},
            }},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$order_date"}}, "day_aov": {"$avg": "$total_amount"}}},
            {"$group": {"_id": None, "avg_aov": {"$avg": "$day_aov"}, "day_count": {"$sum": 1}}},
        ]).to_list(1)

        if not hist_result:
            return
        hist_aov = hist_result[0]["avg_aov"]
        day_count = hist_result[0]["day_count"]

        if day_count < settings.PULSE_MIN_HISTORY_DAYS or hist_aov <= 0:
            return

        ratio = current_aov / hist_aov
        if ratio >= settings.PULSE_AOV_THRESHOLD:
            return

        event: Dict[str, Any] = {
            "alert_type": "aov_drop",
            "hour": current_hour,
            "current_aov_inr": round(current_aov / 100, 2),
            "historical_aov_inr": round(hist_aov / 100, 2),
            "ratio": round(ratio, 3),
            "severity": "high" if ratio < 0.60 else "medium",
            "detected_at": now.isoformat(),
            "restaurant_id": restaurant_id,
        }
        logger.warning(
            "AoV drop: current=₹%.0f, baseline=₹%.0f, ratio=%.2f",
            current_aov / 100, hist_aov / 100, ratio,
        )
        await get_event_bus().publish("operations.aov_drop", event)

    # ── Check 6: Stale occupied tables ───────────────────────────────────────

    async def _check_occupied_tables_no_orders(self, restaurant_id: str) -> None:
        """Find tables marked OCCUPIED with no active order for >20 min."""
        settings = get_settings()
        db = get_database()
        now = now_ist()
        stale_cutoff = now - timedelta(minutes=settings.PULSE_TABLE_STALE_MINUTES)

        # Occupied tables that have been occupied since before the stale cutoff
        occupied_tables = await db.tables.find({
            "restaurant_id": restaurant_id,
            "status": "occupied",
            "occupied_since": {"$lte": stale_cutoff},
        }).to_list(None)

        if not occupied_tables:
            return

        # Active orders (not yet completed/cancelled) for this restaurant
        active_orders = await db.orders.find({
            "restaurant_id": restaurant_id,
            "status": {"$in": _ACTIVE_STATUSES},
            "table_id": {"$ne": None},
        }, {"table_id": 1}).to_list(None)

        active_table_ids = {str(o["table_id"]) for o in active_orders}

        stale_tables: List[Dict[str, Any]] = []
        for table in occupied_tables:
            table_id = str(table["_id"])
            if table_id not in active_table_ids:
                stale_tables.append({
                    "table_id": table_id,
                    "table_number": table.get("table_number"),
                    "location": table.get("location"),
                    "occupied_since": table.get("occupied_since", "").isoformat()
                    if hasattr(table.get("occupied_since"), "isoformat") else str(table.get("occupied_since", "")),
                })

        if not stale_tables:
            return

        event: Dict[str, Any] = {
            "alert_type": "table_stale",
            "stale_tables": stale_tables,
            "stale_count": len(stale_tables),
            "stale_threshold_minutes": settings.PULSE_TABLE_STALE_MINUTES,
            "severity": "medium",
            "detected_at": now.isoformat(),
            "restaurant_id": restaurant_id,
        }
        logger.warning(
            "Stale tables: %d table(s) occupied with no active orders: %s",
            len(stale_tables), [t["table_number"] for t in stale_tables],
        )
        await get_event_bus().publish("operations.table_stale", event)

    # ── Check 7: Dead period ──────────────────────────────────────────────────

    async def _check_dead_period(self, restaurant_id: str) -> None:
        """Detect if no orders have been completed in last 30 min during operating hours."""
        settings = get_settings()
        db = get_database()
        now = now_ist()
        current_hour = now.hour

        # Fetch operating hours from restaurant settings
        rs = await db.restaurant_settings.find_one({"restaurant_id": restaurant_id})
        if rs:
            opening = rs.get("operating_hours", {}).get("opening_hour", 10)
            closing = rs.get("operating_hours", {}).get("closing_hour", 23)
        else:
            opening, closing = 10, 23

        # Skip check outside operating hours
        if not (opening <= current_hour < closing):
            return

        window_start = now - timedelta(minutes=settings.PULSE_DEAD_PERIOD_MINUTES)
        result = await db.orders.find_one({
            "restaurant_id": restaurant_id,
            "status": _COMPLETED_STATUS,
            "completed_at": {"$gte": window_start},
        })

        if result is not None:
            return  # at least one completed order — not dead

        event: Dict[str, Any] = {
            "alert_type": "dead_period",
            "hour": current_hour,
            "dead_period_minutes": settings.PULSE_DEAD_PERIOD_MINUTES,
            "operating_hours": {"opening": opening, "closing": closing},
            "severity": "high",
            "detected_at": now.isoformat(),
            "restaurant_id": restaurant_id,
        }
        logger.warning(
            "Dead period: no completed orders in last %d min (hour=%d)",
            settings.PULSE_DEAD_PERIOD_MINUTES, current_hour,
        )
        await get_event_bus().publish("operations.dead_period", event)


# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: Optional[OperationsPulseService] = None


def get_operations_pulse() -> OperationsPulseService:
    global _instance
    if _instance is None:
        _instance = OperationsPulseService()
    return _instance
