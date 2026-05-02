"""
Dashboard Service

Aggregates data from multiple collections for the owner dashboard.
Six methods map directly to the six dashboard endpoints.

Zone 1+2 methods (pulse, action_queue) must stay fast (<200ms).
Zone 3 methods (menu_performance, stock_health, pnl_snapshot, revenue_pattern)
are on-demand and can take longer.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.utils.timezone import now_ist

from app.core.database import get_database
from app.services.profit_analysis_service import get_profit_analysis_service

logger = logging.getLogger(__name__)


class DashboardService:
    """Aggregates cross-collection data for the owner dashboard."""

    def __init__(self):
        self.db = get_database()

    # ── Zone 1 ──────────────────────────────────────────────────────────────

    async def get_pulse_metrics(self, period: str = "today") -> Dict[str, Any]:
        """
        Zone 1: Key metrics for a specific time period.
        Supported periods: today, last_week, last_month, last_3_months.
        """
        now = now_ist()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        start_date = today_start
        end_date = now
        comparison_start = None
        comparison_end = None

        if period == "last_week":
            start_date = today_start - timedelta(days=7)
            comparison_start = start_date - timedelta(days=7)
            comparison_end = start_date
        elif period == "last_month":
            start_date = today_start - timedelta(days=30)
            comparison_start = start_date - timedelta(days=30)
            comparison_end = start_date
        elif period == "last_3_months":
            start_date = today_start - timedelta(days=90)
            comparison_start = start_date - timedelta(days=90)
            comparison_end = start_date
        else:  # today
            start_date = today_start
            comparison_start = today_start - timedelta(days=7)
            comparison_end = comparison_start + timedelta(days=1)

        # Current period metrics
        revenue, covers = await self._get_range_revenue_covers(start_date, end_date)
        
        # Comparison period metrics
        revenue_change_pct = None
        if comparison_start:
            comp_revenue, _ = await self._get_range_revenue_covers(comparison_start, comparison_end)
            if comp_revenue > 0:
                revenue_change_pct = round((revenue - comp_revenue) / comp_revenue * 100, 1)

        avg_ticket = (revenue / covers) if covers > 0 else 0
        food_cost_pct = await self._get_range_food_cost_pct(start_date, end_date, revenue)
        
        return {
            "revenue_today_paise": revenue,
            "revenue_today_inr": round(revenue / 100, 2),
            "revenue_vs_last_week_pct": revenue_change_pct,
            "covers_today": covers,
            "avg_ticket_paise": int(avg_ticket),
            "avg_ticket_inr": round(avg_ticket / 100, 2),
            "food_cost_pct": food_cost_pct,
            "attention_count": await self._get_attention_count() if period == "today" else 0,
        }

    # ── Zone 2 ──────────────────────────────────────────────────────────────

    async def get_action_queue(self) -> Dict[str, Any]:
        """
        Zone 2: Actionable cards for the owner.

        Aggregates low-stock alerts, pending POs, revenue anomaly alerts,
        and expiry-based today's specials suggestions.
        """
        low_stock_cards = await self._get_low_stock_cards()
        po_cards = await self._get_pending_po_cards()
        anomaly_cards = await self._get_revenue_anomaly_cards()
        special_cards = await self._get_expiry_special_cards()

        cards = low_stock_cards + po_cards + anomaly_cards + special_cards
        total = len(cards)

        return {
            "total_cards": total,
            "cards": cards,
        }

    # ── Zone 3 ──────────────────────────────────────────────────────────────

    async def get_menu_performance(self, period_days: int = 7) -> List[Dict[str, Any]]:
        """
        Zone 3: Menu items ranked by contribution margin.

        Returns top 20 items with revenue, profit, margin %, volume.
        Annotated with agent alerts where relevant.
        """
        svc = get_profit_analysis_service()
        items = await svc.get_top_items(
            metric="profit",
            period_days=period_days,
            limit=20,
            order="desc"
        )

        # Attach any active agent annotations
        annotations = await self._get_menu_annotations()
        for item in items:
            item["annotation"] = annotations.get(item.get("item_id"))

        return items

    async def get_stock_health(self) -> Dict[str, Any]:
        """
        Zone 3: Inventory health with critical/low/good classification.

        Items sorted: critical first, then low, then good.
        Agent alert annotations attached where available.
        """
        db = self.db
        cursor = db.raw_material_inventory.find({})
        all_items = await cursor.to_list(length=None)

        # Fetch active low-stock alerts for annotations
        alert_cursor = db.financial_alerts.find({
            "status": "active",
            "alert_type": {"$in": ["low_stock", "stockout_risk"]}
        })
        alerts_by_material: Dict[str, str] = {}
        async for alert in alert_cursor:
            mid = alert.get("material_id") or alert.get("details", {}).get("material_id")
            if mid:
                alerts_by_material[mid] = alert.get("message", "Agent flagged")

        classified = []
        for item in all_items:
            stock = item.get("current_stock", 0)
            reorder = item.get("reorder_level", 0)

            if stock <= 0:
                health = "critical"
            elif stock <= reorder:
                health = "low"
            else:
                health = "good"

            classified.append({
                "material_id": item.get("material_id"),
                "material_name": item.get("material_name"),
                "category": item.get("category"),
                "current_stock": stock,
                "reorder_level": reorder,
                "unit": item.get("unit"),
                "health": health,
                "annotation": alerts_by_material.get(item.get("material_id")),
            })

        # Sort: critical → low → good
        order = {"critical": 0, "low": 1, "good": 2}
        classified.sort(key=lambda x: order[x["health"]])

        summary = {
            "critical": sum(1 for i in classified if i["health"] == "critical"),
            "low": sum(1 for i in classified if i["health"] == "low"),
            "good": sum(1 for i in classified if i["health"] == "good"),
        }

        return {"summary": summary, "items": classified}

    async def get_pnl_snapshot(self) -> Dict[str, Any]:
        """
        Zone 3: Month-to-date P&L snapshot.

        Revenue, COGS (from stock movement log), gross margin %, waste callout.
        """
        today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)

        # Revenue this month
        revenue_pipeline = [
            {
                "$match": {
                    "order_date": {"$gte": month_start, "$lte": today_start},
                    "status": {"$ne": "cancelled"}
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$total_amount"}, "orders": {"$sum": 1}}}
        ]
        cursor = self.db.orders.aggregate(revenue_pipeline)
        rev_result = await cursor.to_list(length=1)
        revenue_paise = rev_result[0]["total"] if rev_result else 0
        order_count = rev_result[0]["orders"] if rev_result else 0

        # COGS from stock_movement_log (SALE movements)
        cogs_paise = await self._get_movement_value(month_start, today_start, "SALE")

        # Waste from stock_movement_log
        waste_paise = await self._get_movement_value(month_start, today_start, "WASTE")

        gross_profit_paise = revenue_paise - cogs_paise
        gross_margin_pct = (
            round(gross_profit_paise / revenue_paise * 100, 1)
            if revenue_paise > 0 else None
        )
        food_cost_pct = (
            round(cogs_paise / revenue_paise * 100, 1)
            if revenue_paise > 0 else None
        )

        return {
            "period": {
                "start": month_start.strftime("%Y-%m-%d"),
                "end": today_start.strftime("%Y-%m-%d"),
                "label": month_start.strftime("%B %Y"),
            },
            "revenue_paise": revenue_paise,
            "revenue_inr": round(revenue_paise / 100, 2),
            "cogs_paise": cogs_paise,
            "cogs_inr": round(cogs_paise / 100, 2),
            "waste_paise": waste_paise,
            "waste_inr": round(waste_paise / 100, 2),
            "gross_profit_inr": round(gross_profit_paise / 100, 2),
            "gross_margin_pct": gross_margin_pct,
            "food_cost_pct": food_cost_pct,
            "order_count": order_count,
            "cogs_data_available": cogs_paise > 0,
        }

    async def get_revenue_pattern(self) -> Dict[str, Any]:
        """
        Zone 3: Hourly revenue today vs 30-day historical average.

        Returns 24 hour slots with today's revenue and historical avg.
        Anomaly flag on hours where today deviates > 30% from avg.
        """
        today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
        hist_start = today_start - timedelta(days=30)

        # Today's hourly revenue
        today_pipeline = [
            {
                "$match": {
                    "order_date": today_start,
                    "status": {"$ne": "cancelled"}
                }
            },
            {
                "$group": {
                    "_id": "$order_hour",
                    "revenue": {"$sum": "$total_amount"},
                    "covers": {"$sum": 1}
                }
            }
        ]
        cursor = self.db.orders.aggregate(today_pipeline)
        today_by_hour = {doc["_id"]: doc async for doc in cursor}

        # Historical hourly average (last 30 days, excluding today)
        hist_pipeline = [
            {
                "$match": {
                    "order_date": {"$gte": hist_start, "$lt": today_start},
                    "status": {"$ne": "cancelled"}
                }
            },
            {
                "$group": {
                    "_id": {"hour": "$order_hour", "date": "$order_date"},
                    "daily_revenue": {"$sum": "$total_amount"}
                }
            },
            {
                "$group": {
                    "_id": "$_id.hour",
                    "avg_revenue": {"$avg": "$daily_revenue"},
                    "days_with_data": {"$sum": 1}
                }
            }
        ]
        cursor = self.db.orders.aggregate(hist_pipeline)
        hist_by_hour = {doc["_id"]: doc async for doc in cursor}

        hours = []
        for h in range(24):
            today_rev = today_by_hour.get(h, {}).get("revenue", 0)
            hist_avg = hist_by_hour.get(h, {}).get("avg_revenue", 0)

            anomaly = None
            if hist_avg > 0 and today_rev > 0:
                ratio = today_rev / hist_avg
                if ratio > 1.3:
                    anomaly = "above_normal"
                elif ratio < 0.7:
                    anomaly = "below_normal"

            hours.append({
                "hour": h,
                "label": f"{h:02d}:00",
                "today_revenue_paise": today_rev,
                "today_revenue_inr": round(today_rev / 100, 2),
                "historical_avg_paise": round(hist_avg),
                "historical_avg_inr": round(hist_avg / 100, 2),
                "today_covers": today_by_hour.get(h, {}).get("covers", 0),
                "anomaly": anomaly,
            })

        current_hour = now_ist().hour
        return {
            "hours": hours,
            "current_hour": current_hour,
            "today_total_inr": round(
                sum(h["today_revenue_paise"] for h in hours) / 100, 2
            ),
            "anomalous_hours": [h["hour"] for h in hours if h["anomaly"]],
        }

    # ── Private helpers ──────────────────────────────────────────────────────

    async def _get_range_revenue_covers(self, start: datetime, end: datetime):
        """Revenue (paise) and order count for a date range."""
        pipeline = [
            {
                "$match": {
                    "order_date": {"$gte": start, "$lt": end} if start != end else start,
                    "status": {"$ne": "cancelled"}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "revenue": {"$sum": "$total_amount"},
                    "covers": {"$sum": 1}
                }
            }
        ]
        cursor = self.db.orders.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        if not result:
            return 0, 0
        return result[0]["revenue"], result[0]["covers"]

    async def _get_range_food_cost_pct(
        self, start: datetime, end: datetime, revenue_paise: int
    ) -> Optional[float]:
        """Food cost % from stock movement log for a date range."""
        if revenue_paise <= 0:
            return None

        cogs = await self._get_movement_value(start, end, "SALE")
        if cogs <= 0:
            return None

        return round(cogs / revenue_paise * 100, 1)

    async def _get_attention_count(self) -> int:
        """Count of items needing owner attention (low stock + pending POs + active alerts)."""
        try:
            low_stock = await self.db.raw_material_inventory.count_documents(
                {"$expr": {"$lte": ["$current_stock", "$reorder_level"]}}
            )
            pending_pos = await self.db.shopping_lists.count_documents(
                {"status": {"$in": ["pending", "partially_approved"]}}
            )
            active_alerts = await self.db.financial_alerts.count_documents({"status": "active"})
            return low_stock + pending_pos + active_alerts
        except Exception:
            return 0

    async def _get_low_stock_cards(self) -> List[Dict]:
        """Action cards for items at or below reorder level."""
        try:
            cursor = self.db.raw_material_inventory.find(
                {"$expr": {"$lte": ["$current_stock", "$reorder_level"]}}
            ).sort("current_stock", 1).limit(10)
            items = await cursor.to_list(length=10)

            cards = []
            for item in items:
                stock = item.get("current_stock", 0)
                reorder = item.get("reorder_level", 0)
                cards.append({
                    "card_type": "low_stock",
                    "material_id": item.get("material_id"),
                    "material_name": item.get("material_name"),
                    "current_stock": stock,
                    "reorder_level": reorder,
                    "unit": item.get("unit"),
                    "severity": "critical" if stock <= 0 else "low",
                })
            return cards
        except Exception as e:
            logger.warning(f"Failed to fetch low stock cards: {e}")
            return []

    async def _get_pending_po_cards(self) -> List[Dict]:
        """Action cards for pending purchase orders."""
        try:
            cursor = self.db.shopping_lists.find(
                {"status": {"$in": ["pending", "partially_approved"]}}
            ).sort("generated_at", -1).limit(5)
            lists = await cursor.to_list(length=5)

            cards = []
            for lst in lists:
                items = lst.get("items", [])
                total_items = len(items)
                pending_items = sum(
                    1 for i in items
                    if i.get("status") not in ("approved", "rejected")
                )
                cards.append({
                    "card_type": "po_approval",
                    "po_id": str(lst["_id"]),
                    "list_id": lst.get("list_id"),
                    "status": lst.get("status"),
                    "total_items": total_items,
                    "pending_items": pending_items,
                    "total_cost_inr": round(lst.get("total_cost_inr", 0) / 100, 2),
                    "generated_at": (
                        lst["generated_at"].isoformat()
                        if isinstance(lst.get("generated_at"), datetime)
                        else lst.get("generated_at")
                    ),
                    "supplier_count": len(lst.get("supplier_breakdown", [])),
                })
            return cards
        except Exception as e:
            logger.warning(f"Failed to fetch PO cards: {e}")
            return []

    async def _get_revenue_anomaly_cards(self) -> List[Dict]:
        """Action cards for active revenue anomaly alerts from today only."""
        try:
            now = datetime.now()
            today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            cursor = self.db.financial_alerts.find({
                "status": "active",
                "alert_type": "revenue_anomaly",
                "created_at": {"$gte": today_midnight},
            }).sort("created_at", -1).limit(3)

            cards = []
            async for alert in cursor:
                cards.append({
                    "card_type": "revenue_anomaly",
                    "alert_id": str(alert["_id"]),
                    "message": alert.get("message"),
                    "severity": alert.get("severity", "medium"),
                    "created_at": (
                        alert["created_at"].isoformat()
                        if isinstance(alert.get("created_at"), datetime)
                        else alert.get("created_at")
                    ),
                })
            return cards
        except Exception as e:
            logger.warning(f"Failed to fetch anomaly cards: {e}")
            return []

    async def _get_expiry_special_cards(self) -> List[Dict]:
        """Action cards for expiry-based today's special suggestions."""
        try:
            cursor = self.db.expiry_specials.find(
                {"status": "pending"}
            ).sort("created_at", -1).limit(3)
            cards = []
            async for special in cursor:
                cards.append({
                    "card_type": "expiry_special",
                    "special_id": str(special["_id"]),
                    "suggestion": special.get("suggestion"),
                    "material_name": special.get("material_name"),
                    "expiry_date": special.get("expiry_date"),
                    "created_at": (
                        special["created_at"].isoformat()
                        if isinstance(special.get("created_at"), datetime)
                        else special.get("created_at")
                    ),
                })
            return cards
        except Exception:
            # Collection may not exist yet — degrade gracefully
            return []

    async def _get_movement_value(
        self, start: datetime, end: datetime, movement_type: str
    ) -> int:
        """Sum value_inr from stock_movement_log for a type and date range."""
        try:
            pipeline = [
                {
                    "$match": {
                        "movement_type": movement_type,
                        "created_at": {"$gte": start, "$lt": end}
                    }
                },
                {"$group": {"_id": None, "total": {"$sum": "$value_inr"}}}
            ]
            cursor = self.db.stock_movement_log.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            return int(result[0]["total"]) if result else 0
        except Exception:
            return 0

    async def _get_menu_annotations(self) -> Dict[str, str]:
        """Map of menu_item_id → agent annotation string from active alerts."""
        try:
            cursor = self.db.financial_alerts.find({
                "status": "active",
                "menu_item_id": {"$exists": True}
            })
            annotations: Dict[str, str] = {}
            async for alert in cursor:
                mid = alert.get("menu_item_id")
                if mid:
                    annotations[mid] = alert.get("message", "Agent flagged")
            return annotations
        except Exception:
            return {}


# Singleton
_dashboard_service: Optional[DashboardService] = None


def get_dashboard_service() -> DashboardService:
    """Get singleton dashboard service instance."""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service
