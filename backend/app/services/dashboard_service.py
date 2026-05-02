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

from bson import ObjectId

from app.utils.timezone import now_ist

from app.core.database import get_database
from app.services.profit_analysis_service import get_profit_analysis_service

logger = logging.getLogger(__name__)


class DashboardService:
    """Aggregates cross-collection data for the owner dashboard."""

    def __init__(self):
        self.db = get_database()

    # ── Zone 1 ──────────────────────────────────────────────────────────────

    async def get_pulse_metrics(self, restaurant_id: str, period: str = "today") -> Dict[str, Any]:
        """
        Zone 1: Key metrics for a specific time period.
        Supported periods: today, last_week, last_month, last_3_months.
        Returns daily averages for historical periods.
        """
        now = now_ist()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        start_date = today_start
        end_date = now
        comparison_start = None
        comparison_end = None
        num_days = 1

        if period == "last_week":
            num_days = 7
            start_date = today_start - timedelta(days=num_days)
            end_date = today_start  # Full days only for historical periods
            comparison_start = start_date - timedelta(days=num_days)
            comparison_end = start_date
        elif period == "last_month":
            num_days = 30
            start_date = today_start - timedelta(days=num_days)
            end_date = today_start
            comparison_start = start_date - timedelta(days=num_days)
            comparison_end = start_date
        elif period == "last_3_months":
            num_days = 90
            start_date = today_start - timedelta(days=num_days)
            end_date = today_start
            comparison_start = start_date - timedelta(days=num_days)
            comparison_end = start_date
        else:  # today
            num_days = 1
            start_date = today_start
            comparison_start = today_start - timedelta(days=7)
            comparison_end = comparison_start + timedelta(days=1)

        # Current period metrics (totals)
        total_revenue, total_covers = await self._get_range_revenue_covers(restaurant_id, start_date, end_date)
        
        # Normalize to daily averages for historical periods
        revenue = total_revenue / num_days
        covers = total_covers / num_days
        
        # Comparison period metrics
        revenue_change_pct = None
        if comparison_start:
            comp_total_revenue, _ = await self._get_range_revenue_covers(restaurant_id, comparison_start, comparison_end)
            # Normalize comparison to daily average (comparison period days = current period days)
            comp_revenue = comp_total_revenue / num_days
            
            if comp_revenue > 0:
                revenue_change_pct = round((revenue - comp_revenue) / comp_revenue * 100, 1)

        avg_ticket = (revenue / covers) if covers > 0 else 0
        
        # For 'today', we want to see the COGS even if movements are at 23:30 (simulated)
        cogs_query_end = end_date
        if period == "today":
            cogs_query_end = today_start + timedelta(days=1)
            
        cogs_pct = await self._get_range_cogs_pct(restaurant_id, start_date, cogs_query_end, total_revenue)
        
        return {
            "period": period,
            "is_average": num_days > 1,
            "revenue_today_paise": int(revenue),
            "revenue_today_inr": round(revenue / 100, 2),
            "revenue_vs_last_week_pct": revenue_change_pct,
            "covers_today": round(covers, 1) if num_days > 1 else int(covers),
            "avg_ticket_paise": int(avg_ticket),
            "avg_ticket_inr": round(avg_ticket / 100, 2),
            "food_cost_pct": cogs_pct,
            "attention_count": await self._get_attention_count(restaurant_id) if period == "today" else 0,
        }

    # ── Zone 2 ──────────────────────────────────────────────────────────────

    async def get_action_queue(self, restaurant_id: str) -> Dict[str, Any]:
        """
        Zone 2: Actionable cards for the owner.

        Aggregates low-stock alerts, pending POs, revenue anomaly alerts,
        expiry-based today's specials suggestions, and promotion suggestions.
        """
        low_stock_cards = await self._get_low_stock_cards(restaurant_id)
        po_cards = await self._get_pending_po_cards(restaurant_id)
        anomaly_cards = await self._get_revenue_anomaly_cards(restaurant_id)
        special_cards = await self._get_expiry_special_cards(restaurant_id)
        promo_cards = await self._get_promotion_suggestion_cards(restaurant_id)

        cards = low_stock_cards + po_cards + anomaly_cards + special_cards + promo_cards
        total = len(cards)

        return {
            "total_cards": total,
            "cards": cards,
        }

    # ── Zone 3 ──────────────────────────────────────────────────────────────

    async def get_menu_performance(self, restaurant_id: str, period_days: int = 7) -> List[Dict[str, Any]]:
        """
        Zone 3: Top items by contribution margin.

        Returns top 20 items with revenue, profit, margin %, volume.
        Annotated with agent alerts where relevant.
        """
        svc = get_profit_analysis_service()
        # Note: ProfitAnalysisService now takes restaurant_id
        items = await svc.get_top_items(
            restaurant_id=restaurant_id,
            metric="profit",
            period_days=period_days,
            limit=20,
            order="desc"
        )

        # Attach any active agent annotations
        annotations = await self._get_menu_annotations(restaurant_id)
        for item in items:
            item["annotation"] = annotations.get(item.get("item_id"))

        return items

    async def get_stock_health(self, restaurant_id: str) -> Dict[str, Any]:
        """
        Zone 3: Inventory health with critical/low/good classification.

        Items sorted: critical first, then low, then good.
        Agent alert annotations attached where available.
        """
        db = self.db
        cursor = db.raw_material_inventory.find({"restaurant_id": restaurant_id})
        all_items = await cursor.to_list(length=None)

        # Fetch active low-stock alerts for annotations
        alert_cursor = db.financial_alerts.find({
            "restaurant_id": restaurant_id,
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

    async def get_pnl_snapshot(self, restaurant_id: str) -> Dict[str, Any]:
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
                    "restaurant_id": restaurant_id,
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
        # Use tomorrow_start to include all of today's simulated movements
        tomorrow_start = today_start + timedelta(days=1)
        cogs_paise = await self._get_movement_value(restaurant_id, month_start, tomorrow_start, "SALE")

        # Waste from stock_movement_log
        waste_paise = await self._get_movement_value(restaurant_id, month_start, tomorrow_start, "WASTE")

        gross_profit_paise = revenue_paise - cogs_paise
        gross_margin_pct = (
            round(gross_profit_paise / revenue_paise * 100, 1)
            if revenue_paise > 0 else None
        )
        cogs_pct = (
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
            "food_cost_pct": cogs_pct,
            "order_count": order_count,
            "cogs_data_available": cogs_paise > 0,
        }

    async def get_revenue_pattern(self, restaurant_id: str) -> Dict[str, Any]:
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
                    "restaurant_id": restaurant_id,
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
                    "restaurant_id": restaurant_id,
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

    # ── Zone 3: Agent Bus ────────────────────────────────────────────────────

    async def get_agent_feed(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """
        Zone 3: Strategic insights produced by backend agents.

        Reads agent_insights collection, returns active insights sorted
        newest first.
        """
        try:
            # Note: agent_insights collection may not yet have restaurant_id in all docs.
            # We filter if present, or just return all for now if multi-tenancy not yet fully implemented for insights.
            query = {"status": "active"}
            # Uncomment when restaurant_id is added to agent_insights
            # query["restaurant_id"] = restaurant_id
            
            cursor = self.db.agent_insights.find(
                query
            ).sort("created_at", -1).limit(50)
            insights = []
            async for doc in cursor:
                doc["id"] = str(doc.pop("_id"))
                if isinstance(doc.get("created_at"), datetime):
                    doc["created_at"] = doc["created_at"].isoformat()
                insights.append(doc)
            return insights
        except Exception as e:
            logger.warning(f"Failed to fetch agent feed: {e}")
            return []

    async def dismiss_insight(self, insight_id: str) -> bool:
        """Mark an agent insight as dismissed so it leaves the active feed."""
        try:
            result = await self.db.agent_insights.update_one(
                {"_id": ObjectId(insight_id)},
                {"$set": {"status": "dismissed"}}
            )
            return result.modified_count == 1
        except Exception as e:
            logger.warning(f"Failed to dismiss insight {insight_id}: {e}")
            return False

    # ── Private helpers ──────────────────────────────────────────────────────

    async def _get_range_revenue_covers(self, restaurant_id: str, start: datetime, end: datetime):
        """Revenue (paise) and order count for a date range."""
        pipeline = [
            {
                "$match": {
                    "restaurant_id": restaurant_id,
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

    async def _get_range_cogs_pct(
        self, restaurant_id: str, start: datetime, end: datetime, revenue_paise: int
    ) -> Optional[float]:
        """COGS % from stock movement log for a date range."""
        if revenue_paise <= 0:
            return None

        cogs = await self._get_movement_value(restaurant_id, start, end, "SALE")
        if cogs <= 0:
            return None

        return round(cogs / revenue_paise * 100, 1)

    async def _get_attention_count(self, restaurant_id: str) -> int:
        """Count of items needing owner attention (low stock + pending POs + active alerts)."""
        try:
            low_stock = await self.db.raw_material_inventory.count_documents(
                {
                    "restaurant_id": restaurant_id,
                    "$expr": {"$lte": ["$current_stock", "$reorder_level"]}
                }
            )
            pending_pos = await self.db.shopping_lists.count_documents(
                {
                    "restaurant_id": restaurant_id,
                    "status": {"$in": ["pending", "partially_approved"]}
                }
            )
            active_alerts = await self.db.financial_alerts.count_documents({
                "restaurant_id": restaurant_id,
                "status": "active"
            })
            return low_stock + pending_pos + active_alerts
        except Exception:
            return 0

    async def _get_low_stock_cards(self, restaurant_id: str) -> List[Dict]:
        """Action cards for items at or below reorder level."""
        try:
            cursor = self.db.raw_material_inventory.find(
                {
                    "restaurant_id": restaurant_id,
                    "$expr": {"$lte": ["$current_stock", "$reorder_level"]}
                }
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

    async def _get_pending_po_cards(self, restaurant_id: str) -> List[Dict]:
        """Action cards for pending purchase orders."""
        try:
            cursor = self.db.shopping_lists.find(
                {
                    "restaurant_id": restaurant_id,
                    "status": {"$in": ["pending", "partially_approved"]}
                }
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

    async def _get_revenue_anomaly_cards(self, restaurant_id: str) -> List[Dict]:
        """Action cards for active revenue anomaly alerts from today only."""
        try:
            now = datetime.now()
            today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            cursor = self.db.financial_alerts.find({
                "restaurant_id": restaurant_id,
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

    async def _get_expiry_special_cards(self, restaurant_id: str) -> List[Dict]:
        """Action cards for expiry-based today's special suggestions."""
        try:
            cursor = self.db.expiry_specials.find(
                {
                    "restaurant_id": restaurant_id,
                    "status": "pending"
                }
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

    async def _get_promotion_suggestion_cards(self, restaurant_id: str) -> List[Dict]:
        """Action cards for pending promotion suggestions from the CX Agent."""
        try:
            cursor = self.db.promotion_suggestions.find(
                {
                    "restaurant_id": restaurant_id,
                    "status": "pending",
                }
            ).sort("created_at", -1).limit(5)
            cards = []
            async for suggestion in cursor:
                cards.append({
                    "card_type": "promotion_suggestion",
                    "suggestion_id": str(suggestion["_id"]),
                    "promo_type": suggestion.get("promo_type"),
                    "menu_item_names": suggestion.get("menu_item_names", []),
                    "discount_pct": suggestion.get("discount_pct", 0),
                    "description": suggestion.get("description", ""),
                    "reasoning": suggestion.get("reasoning", ""),
                    "confidence": suggestion.get("confidence", 0.0),
                    "created_at": (
                        suggestion["created_at"].isoformat()
                        if isinstance(suggestion.get("created_at"), datetime)
                        else suggestion.get("created_at")
                    ),
                })
            return cards
        except Exception:
            # Collection may not exist yet — degrade gracefully
            return []

    async def _get_movement_value(
        self, restaurant_id: str, start: datetime, end: datetime, movement_type: str
    ) -> int:
        """Sum value_inr from stock_movement_log for a type and date range."""
        try:
            pipeline = [
                {
                    "$match": {
                        "restaurant_id": restaurant_id,
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

    async def _get_menu_annotations(self, restaurant_id: str) -> Dict[str, str]:
        """Map of menu_item_id → agent annotation string from active alerts."""
        try:
            cursor = self.db.financial_alerts.find({
                "restaurant_id": restaurant_id,
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
