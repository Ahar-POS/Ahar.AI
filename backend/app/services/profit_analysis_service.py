"""
Profit Analysis Service - Business logic for profit/loss analysis at granular level.

Provides tool implementations for profit-analysis skill:
- get_top_items: Rank items by revenue, profit, margin, volume
- get_item_details: Deep dive into specific item performance
- get_ingredient_costs: Ingredient-level cost tracking and trends
- compare_periods: Time-based comparisons
- identify_losses: Loss source identification

All monetary calculations in paise, converted to rupees for display.
"""

import logging
from datetime import datetime, timedelta
from app.utils.timezone import now_ist
from typing import Dict, List, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.services.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)


class ProfitAnalysisService:
    """Service for granular profit & loss analysis"""

    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.pricing = get_pricing_service()

    async def get_top_items(
        self,
        restaurant_id: str,
        metric: str,
        period_days: int = None,
        limit: int = 10,
        order: str = "desc",
        category: Optional[str] = None,
        start_date_str: Optional[str] = None,
        end_date_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get top/bottom performers by metric

        Args:
            restaurant_id: Restaurant identifier
            metric: revenue, profit, margin, volume, avg_order_value
            period_days: Number of days to analyze (relative mode)
            limit: Max items to return
            order: desc (top) or asc (bottom)
            category: Optional category filter
            start_date_str: Explicit start date YYYY-MM-DD (explicit mode)
            end_date_str: Explicit end date YYYY-MM-DD (explicit mode)

        Returns:
            List of items with metrics
        """
        # Determine date mode
        if start_date_str and end_date_str:
            # Explicit date mode
            start_date = datetime.fromisoformat(start_date_str)
            end_date = datetime.fromisoformat(end_date_str).replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            # Relative mode
            end_date = now_ist()
            start_date = end_date - timedelta(days=period_days or 30)

        # Build aggregation pipeline
        pipeline: List[Dict] = [
            {
                "$match": {
                    "restaurant_id": restaurant_id,
                    "order_date": {"$gte": start_date, "$lte": end_date},
                    "status": {"$ne": "cancelled"}
                }
            },
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.menu_item_id",
                    "item_name": {
                        "$first": {
                            "$ifNull": ["$items.name_snapshot", "$items.menu_item_name"]
                        }
                    },
                    "quantity_sold": {"$sum": "$items.quantity"},
                    "total_revenue": {
                        "$sum": {"$multiply": ["$items.price_snapshot", "$items.quantity"]}
                    }
                }
            }
        ]

        # Execute aggregation
        cursor = self.db.orders.aggregate(pipeline)
        items_data = await cursor.to_list(length=None)

        if not items_data:
            return []

        # Get COGS for each item
        enriched_items = []
        for item in items_data:
            item_id = item["_id"]

            # Calculate COGS — price as-of period end so the ranking reflects
            # the cost regime in force during the analysis window.
            cogs_data = await self._calculate_item_cogs(
                item_id, item["quantity_sold"], as_of=end_date
            )

            total_revenue = item["total_revenue"]
            total_cogs = cogs_data["total_cogs"]
            quantity = item["quantity_sold"]

            profit = total_revenue - total_cogs
            margin_pct = (profit / total_revenue * 100) if total_revenue > 0 else 0
            avg_order_value = total_revenue / quantity if quantity > 0 else 0

            enriched_items.append({
                "item_id": item_id,
                "item_name": item["item_name"],
                "revenue": total_revenue / 100,  # paise to rupees
                "profit": profit / 100,
                "margin_percentage": round(margin_pct, 1),
                "volume": quantity,
                "avg_order_value": round(avg_order_value / 100, 2),
                "cogs_per_serving": round(cogs_data["cogs_per_serving"] / 100, 2)
            })

        # Filter by category if specified
        if category:
            # Get menu items in category
            category_items = await self._get_items_in_category(category)
            # Use menu_item_id not MongoDB _id
            category_ids = {item["menu_item_id"] for item in category_items}
            enriched_items = [i for i in enriched_items if i["item_id"] in category_ids]

        # Sort by requested metric
        sort_key = metric if metric != "margin" else "margin_percentage"
        reverse = (order == "desc")
        enriched_items.sort(key=lambda x: x[sort_key], reverse=reverse)

        return enriched_items[:limit]

    async def get_item_details(
        self,
        restaurant_id: str,
        item_name: str,
        period_days: int = None,
        start_date_str: Optional[str] = None,
        end_date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed performance for specific item

        Args:
            restaurant_id: Restaurant identifier
            item_name: Name of item (partial match)
            period_days: Analysis period (relative mode)
            start_date_str: Explicit start date YYYY-MM-DD (explicit mode)
            end_date_str: Explicit end date YYYY-MM-DD (explicit mode)

        Returns:
            Dict with revenue, profit, margin, COGS breakdown, trends
        """
        # Find item by name
        menu_item = await self.db.menu_items.find_one({
            "restaurant_id": restaurant_id,
            "name": {"$regex": item_name, "$options": "i"}
        })

        if not menu_item:
            return {"error": f"Item '{item_name}' not found"}

        # Use menu_item_id (e.g., "MENU001") not MongoDB _id
        item_id = menu_item["menu_item_id"]

        # Determine date mode
        if start_date_str and end_date_str:
            # Explicit date mode
            start_date = datetime.fromisoformat(start_date_str)
            end_date = datetime.fromisoformat(end_date_str).replace(hour=23, minute=59, second=59, microsecond=999999)
            # Calculate effective period_days for trend calculation
            effective_period_days = (end_date - start_date).days
        else:
            # Relative mode (default)
            effective_period_days = period_days or 30
            end_date = now_ist()
            start_date = end_date - timedelta(days=effective_period_days)

        # Get sales data
        pipeline = [
            {
                "$match": {
                    "restaurant_id": restaurant_id,
                    "order_date": {"$gte": start_date, "$lte": end_date},
                    "status": {"$ne": "cancelled"}
                }
            },
            {"$unwind": "$items"},
            {"$match": {"items.menu_item_id": item_id}},
            {
                "$group": {
                    "_id": None,
                    "quantity_sold": {"$sum": "$items.quantity"},
                    "total_revenue": {
                        "$sum": {"$multiply": ["$items.price_snapshot", "$items.quantity"]}
                    }
                }
            }
        ]

        cursor = self.db.orders.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if not result or result[0]["quantity_sold"] == 0:
            return {
                "item_name": menu_item["name"],
                "error": f"No sales found for '{menu_item['name']}' from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            }

        sales_data = result[0]
        quantity_sold = sales_data["quantity_sold"]
        total_revenue = sales_data["total_revenue"]

        # Calculate COGS with breakdown — historical price for historical sales.
        cogs_data = await self._calculate_item_cogs(
            item_id, quantity_sold, detailed=True, as_of=end_date
        )

        total_cogs = cogs_data["total_cogs"]
        profit = total_revenue - total_cogs
        margin_pct = (profit / total_revenue * 100) if total_revenue > 0 else 0

        # Get trend (compare to previous period)
        trend_data = await self._get_item_trend(restaurant_id, item_id, effective_period_days)

        return {
            "item_name": menu_item["name"],
            "category": menu_item.get("category", "Unknown"),
            "period_days": effective_period_days,
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "metrics": {
                "revenue": total_revenue / 100,
                "profit": profit / 100,
                "margin_percentage": round(margin_pct, 1),
                "volume": quantity_sold,
                "avg_order_value": round((total_revenue / quantity_sold) / 100, 2),
            },
            "cogs_breakdown": {
                "total_cogs": total_cogs / 100,
                "cogs_per_serving": cogs_data["cogs_per_serving"] / 100,
                "raw_materials": cogs_data["raw_materials"] / 100,
                "packaging": cogs_data["packaging"] / 100,
                "ingredients": cogs_data.get("ingredients", [])  # Detailed list
            },
            "trend": trend_data
        }

    async def get_ingredient_costs(
        self,
        restaurant_id: str,
        period_days: int = None,
        sort_by: str = "total_cost",
        limit: int = 10,
        category: Optional[str] = None,
        start_date_str: Optional[str] = None,
        end_date_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get ingredient-level cost analysis

        Args:
            restaurant_id: Restaurant identifier
            period_days: Analysis period (relative mode)
            sort_by: total_cost, unit_cost, volume, cost_change
            limit: Max ingredients to return
            category: Optional ingredient category filter
            start_date_str: Explicit start date YYYY-MM-DD (explicit mode)
            end_date_str: Explicit end date YYYY-MM-DD (explicit mode)

        Returns:
            List of ingredients with cost data
        """
        # Determine date mode
        if start_date_str and end_date_str:
            # Explicit date mode
            start_date = datetime.fromisoformat(start_date_str)
            end_date = datetime.fromisoformat(end_date_str).replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            # Relative mode
            end_date = now_ist()
            start_date = end_date - timedelta(days=period_days or 7)

        # Get items sold in period
        pipeline = [
            {
                "$match": {
                    "restaurant_id": restaurant_id,
                    "order_date": {"$gte": start_date, "$lte": end_date},
                    "status": {"$ne": "cancelled"}
                }
            },
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.menu_item_id",
                    "quantity_sold": {"$sum": "$items.quantity"}
                }
            }
        ]

        cursor = self.db.orders.aggregate(pipeline)
        items_sold = {d["_id"]: d["quantity_sold"] async for d in cursor}

        # Get recipes and calculate ingredient usage
        recipes_cursor = self.db.recipe_bom.find({"restaurant_id": restaurant_id})
        recipes = await recipes_cursor.to_list(length=None)

        # Inventory provides metadata (name/category/unit); price comes from pricing_service.
        inventory_cursor = self.db.raw_material_inventory.find({"restaurant_id": restaurant_id})
        inventory = {i["material_id"]: i async for i in inventory_cursor}

        # Calculate ingredient costs
        ingredient_costs: Dict[str, Dict] = {}

        for recipe in recipes:
            menu_item_id = recipe["menu_item_id"]
            quantity_sold = items_sold.get(menu_item_id, 0)

            if quantity_sold == 0:
                continue

            for ingredient in recipe.get("ingredients", []):
                material_id = ingredient["material_id"]
                ing_quantity = ingredient.get("quantity_per_serving") or ingredient.get("quantity", 0)
                inv_item = inventory.get(material_id)

                if not inv_item:
                    continue

                # Filter by category if specified
                if category and inv_item.get("category", "").lower() != category.lower():
                    continue

                # Price as-of the period end so historical analyses reflect
                # the cost that was actually in effect during that window.
                unit_cost = await self.pricing.get_price_at(material_id, end_date)
                if unit_cost is None:
                    continue
                total_cost = ing_quantity * unit_cost * quantity_sold

                if material_id not in ingredient_costs:
                    ingredient_costs[material_id] = {
                        "material_id": material_id,
                        "material_name": inv_item["material_name"],
                        "category": inv_item.get("category", "Unknown"),
                        "unit_cost": unit_cost,
                        "total_cost": 0,
                        "volume": 0,
                        "unit": inv_item.get("unit", "unit"),
                        "dishes_using": set()
                    }

                ingredient_costs[material_id]["total_cost"] += total_cost
                ingredient_costs[material_id]["volume"] += ing_quantity * quantity_sold
                ingredient_costs[material_id]["dishes_using"].add(menu_item_id)

        # Convert to list and calculate cost trends
        result = []
        for ing_id, data in ingredient_costs.items():
            # Get cost trend (compare to previous week)
            trend = await self._get_ingredient_cost_trend(ing_id, period_days)

            result.append({
                "material_id": data["material_id"],
                "material_name": data["material_name"],
                "category": data["category"],
                "total_cost": data["total_cost"] / 100,
                "unit_cost": data["unit_cost"] / 100,
                "volume": round(data["volume"], 2),
                "unit": data["unit"],
                "dishes_count": len(data["dishes_using"]),
                "cost_change_pct": trend.get("change_pct", 0)
            })

        # Sort by requested metric
        sort_keys = {
            "total_cost": "total_cost",
            "unit_cost": "unit_cost",
            "volume": "volume",
            "cost_change": "cost_change_pct"
        }
        result.sort(key=lambda x: x[sort_keys.get(sort_by, "total_cost")], reverse=True)

        return result[:limit]

    async def compare_periods(
        self,
        restaurant_id: str,
        # Existing day-based parameters
        period1_days: int = None,
        period2_days: int = None,
        period2_offset: int = None,
        # NEW: Explicit date parameters for month comparisons
        period1_start: Optional[str] = None,
        period1_end: Optional[str] = None,
        period2_start: Optional[str] = None,
        period2_end: Optional[str] = None,
        # Common parameters
        metric: str = "revenue",
        item_name: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compare metrics between two time periods

        Supports two modes:
        1. Relative (day-based): period1_days=30, period2_days=30, period2_offset=30
        2. Explicit (date-based): period1_start='2026-11-01', period1_end='2026-11-30', etc.

        Use explicit mode for calendar month comparisons.

        Args:
            restaurant_id: Restaurant identifier
            period1_days: Recent period length (for relative mode)
            period2_days: Comparison period length (for relative mode)
            period2_offset: Days back to start period 2 (for relative mode)
            period1_start: ISO date for period 1 start (for explicit mode)
            period1_end: ISO date for period 1 end (for explicit mode)
            period2_start: ISO date for period 2 start (for explicit mode)
            period2_end: ISO date for period 2 end (for explicit mode)
            metric: revenue, profit, margin, volume, cogs
            item_name: Optional specific item
            category: Optional category

        Returns:
            Comparison data with changes
        """
        # Determine which mode
        if period1_start and period1_end and period2_start and period2_end:
            # Explicit date mode
            p1_start = datetime.fromisoformat(period1_start)
            p1_end = datetime.fromisoformat(period1_end).replace(hour=23, minute=59, second=59, microsecond=999999)
            p2_start = datetime.fromisoformat(period2_start)
            p2_end = datetime.fromisoformat(period2_end).replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            # Relative day mode (existing logic)
            now = now_ist()
            p1_end = now
            p1_start = now - timedelta(days=period1_days or 30)
            p2_end = now - timedelta(days=period2_offset or (period1_days or 30))
            p2_start = p2_end - timedelta(days=period2_days or 30)

        # Get data for both periods
        p1_data = await self._get_period_metrics(restaurant_id, p1_start, p1_end, item_name, category)
        p2_data = await self._get_period_metrics(restaurant_id, p2_start, p2_end, item_name, category)

        # Calculate changes
        metric_key = metric if metric != "margin" else "margin_pct"
        p1_value = p1_data.get(metric_key, 0)
        p2_value = p2_data.get(metric_key, 0)

        change_abs = p1_value - p2_value
        change_pct = ((p1_value - p2_value) / p2_value * 100) if p2_value > 0 else 0

        return {
            "comparison": {
                "period1": {
                    "start": p1_start.strftime("%Y-%m-%d"),
                    "end": p1_end.strftime("%Y-%m-%d"),
                    "value": p1_value
                },
                "period2": {
                    "start": p2_start.strftime("%Y-%m-%d"),
                    "end": p2_end.strftime("%Y-%m-%d"),
                    "value": p2_value
                }
            },
            "change": {
                "absolute": change_abs,
                "percentage": round(change_pct, 1),
                "trend": "growing" if change_pct > 5 else "declining" if change_pct < -5 else "stable"
            },
            "metric": metric,
            "item_name": item_name,
            "category": category
        }

    async def identify_losses(
        self,
        restaurant_id: str,
        category: Optional[str] = None,
        period_days: int = None,
        min_margin_threshold: float = 25,
        start_date_str: Optional[str] = None,
        end_date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Identify sources of profit loss

        Args:
            restaurant_id: Restaurant identifier
            category: Optional category focus
            period_days: Analysis period (relative mode)
            min_margin_threshold: Margin % threshold for flagging
            start_date_str: Explicit start date YYYY-MM-DD (explicit mode)
            end_date_str: Explicit end date YYYY-MM-DD (explicit mode)

        Returns:
            Dict with loss sources categorized
        """
        # Determine date mode
        if start_date_str and end_date_str:
            # Explicit date mode
            start_date = datetime.fromisoformat(start_date_str)
            end_date = datetime.fromisoformat(end_date_str).replace(hour=23, minute=59, second=59, microsecond=999999)
            effective_period_days = (end_date - start_date).days
        else:
            # Relative mode
            end_date = now_ist()
            effective_period_days = period_days or 30
            start_date = end_date - timedelta(days=effective_period_days)

        # Get all items with metrics
        items = await self.get_top_items(
            restaurant_id=restaurant_id,
            metric="revenue",
            period_days=effective_period_days if not start_date_str else None,
            limit=100,
            order="desc",
            category=category,
            start_date_str=start_date_str,
            end_date_str=end_date_str
        )

        # Categorize issues
        low_margin_items = [i for i in items if i["margin_percentage"] < min_margin_threshold]
        negative_margin_items = [i for i in items if i["margin_percentage"] < 0]

        # Get high-cost ingredients
        high_cost_ingredients = await self.get_ingredient_costs(
            restaurant_id=restaurant_id,
            period_days=effective_period_days,
            sort_by="total_cost",
            limit=5,
            category=None  # All ingredients
        )

        # Get waste data (if tracked)
        waste_data = await self._get_waste_analysis(restaurant_id, effective_period_days)

        # Calculate total recoverable
        recoverable = sum(
            (min_margin_threshold - i["margin_percentage"]) / 100 * i["revenue"]
            for i in low_margin_items
        )

        return {
            "period_days": period_days,
            "category": category or "All",
            "summary": {
                "low_margin_items_count": len(low_margin_items),
                "negative_margin_items_count": len(negative_margin_items),
                "high_cost_ingredients_count": len(high_cost_ingredients),
                "waste_items_count": len(waste_data.get("items", [])),
                "estimated_recoverable_monthly": round(recoverable * (30 / period_days), 2)
            },
            "low_margin_items": low_margin_items[:10],  # Top 10 worst
            "negative_margin_items": negative_margin_items,
            "high_cost_ingredients": high_cost_ingredients,
            "waste_analysis": waste_data
        }

    # ===== Helper Methods =====

    async def _calculate_item_cogs(
        self,
        menu_item_id: str,
        quantity_sold: int,
        detailed: bool = False,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculate COGS for menu item.

        If `as_of` is provided, use the price effective on that date so
        historical profit reflects historical cost. Otherwise use today's price.
        """
        # Get recipe
        recipe = await self.db.recipe_bom.find_one({"menu_item_id": menu_item_id})

        if not recipe:
            return {
                "total_cogs": 0,
                "cogs_per_serving": 0,
                "raw_materials": 0,
                "packaging": 0,
                "ingredients": []
            }

        # Inventory still serves as the source of truth for material metadata
        # (name, unit, category) — but the unit_cost comes from pricing_service.
        inventory_cursor = self.db.raw_material_inventory.find({})
        inventory = {i["material_id"]: i async for i in inventory_cursor}

        # Calculate raw material cost per serving
        raw_materials_cost = 0
        ingredient_details = []

        for ingredient in recipe.get("ingredients", []):
            material_id = ingredient["material_id"]
            quantity = ingredient.get("quantity_per_serving") or ingredient.get("quantity", 0)
            inv_item = inventory.get(material_id)

            unit_cost = (
                await self.pricing.get_price_at(material_id, as_of)
                if as_of is not None
                else await self.pricing.get_current_price(material_id)
            )
            if unit_cost is None:
                continue

            cost = quantity * unit_cost
            raw_materials_cost += cost

            if detailed:
                ingredient_details.append({
                    "name": (inv_item or {}).get("material_name", material_id),
                    "quantity": quantity,
                    "unit": (inv_item or {}).get("unit", "unit"),
                    "cost_per_serving": cost / 100
                })

        # Get packaging cost per serving
        packaging_bom = await self.db.packaging_bom.find_one({"menu_item_id": menu_item_id})
        packaging_cost = 0

        if packaging_bom:
            pkg_materials_cursor = self.db.packaging_materials.find({})
            pkg_materials = {p["packaging_id"]: p async for p in pkg_materials_cursor}

            for pkg in packaging_bom.get("packaging", []):
                pkg_id = pkg["packaging_material_id"]
                pkg_item = pkg_materials.get(pkg_id)
                if pkg_item:
                    packaging_cost += pkg_item["unit_cost_inr"]

        cogs_per_serving = raw_materials_cost + packaging_cost
        total_cogs = cogs_per_serving * quantity_sold

        return {
            "total_cogs": total_cogs,
            "cogs_per_serving": cogs_per_serving,
            "raw_materials": raw_materials_cost * quantity_sold,
            "packaging": packaging_cost * quantity_sold,
            "ingredients": ingredient_details
        }

    async def _get_items_in_category(self, restaurant_id: str, category: str) -> List[Dict]:
        """Get menu items in category"""
        cursor = self.db.menu_items.find({
            "restaurant_id": restaurant_id,
            "category": {"$regex": category, "$options": "i"}
        })
        return await cursor.to_list(length=None)

    async def _get_item_trend(self, restaurant_id: str, menu_item_id: str, period_days: int) -> Dict[str, Any]:
        """Calculate trend by comparing to previous period"""
        # This period
        end1 = now_ist()
        start1 = end1 - timedelta(days=period_days)

        # Previous period
        end2 = start1
        start2 = end2 - timedelta(days=period_days)

        p1_data = await self._get_item_period_metrics(restaurant_id, menu_item_id, start1, end1)
        p2_data = await self._get_item_period_metrics(restaurant_id, menu_item_id, start2, end2)

        revenue_change = ((p1_data["revenue"] - p2_data["revenue"]) / p2_data["revenue"] * 100) if p2_data["revenue"] > 0 else 0

        return {
            "trend": "growing" if revenue_change > 5 else "declining" if revenue_change < -5 else "stable",
            "revenue_change_pct": round(revenue_change, 1),
            "previous_period_revenue": p2_data["revenue"] / 100
        }

    async def _get_item_period_metrics(
        self,
        restaurant_id: str,
        menu_item_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get metrics for item in specific period"""
        pipeline = [
            {
                "$match": {
                    "restaurant_id": restaurant_id,
                    "order_date": {"$gte": start_date, "$lte": end_date},
                    "status": {"$ne": "cancelled"}
                }
            },
            {"$unwind": "$items"},
            {"$match": {"items.menu_item_id": menu_item_id}},
            {
                "$group": {
                    "_id": None,
                    "revenue": {"$sum": {"$multiply": ["$items.price_snapshot", "$items.quantity"]}},
                    "volume": {"$sum": "$items.quantity"}
                }
            }
        ]

        cursor = self.db.orders.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if not result:
            return {"revenue": 0, "volume": 0}

        return result[0]

    async def _get_ingredient_cost_trend(self, material_id: str, period_days: int) -> Dict[str, Any]:
        """Cost change pct between today and `period_days` ago, via cost_history."""
        period_days = period_days or 30
        now = now_ist()
        prev = now - timedelta(days=period_days)
        current = await self.pricing.get_price_at(material_id, now)
        baseline = await self.pricing.get_price_at(material_id, prev)
        if not current or not baseline:
            return {"change_pct": 0}
        change_pct = ((current - baseline) / baseline) * 100
        return {"change_pct": round(change_pct, 1)}

    async def _get_period_metrics(
        self,
        restaurant_id: str,
        start_date: datetime,
        end_date: datetime,
        item_name: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get aggregate metrics for a period"""
        match_stage: Dict[str, Any] = {
            "restaurant_id": restaurant_id,
            "order_date": {"$gte": start_date, "$lte": end_date},
            "status": {"$ne": "cancelled"}
        }

        pipeline = [
            {"$match": match_stage},
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": None,
                    "revenue": {"$sum": {"$multiply": ["$items.price_snapshot", "$items.quantity"]}},
                    "volume": {"$sum": "$items.quantity"}
                }
            }
        ]

        cursor = self.db.orders.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if not result:
            return {"revenue": 0, "volume": 0, "profit": 0, "margin_pct": 0, "cogs": 0}

        data = result[0]
        revenue = data["revenue"] / 100
        volume = data["volume"]

        # For now, return simplified metrics
        # TODO: Calculate actual COGS and profit for period
        return {
            "revenue": revenue,
            "volume": volume,
            "profit": 0,
            "margin_pct": 0,
            "cogs": 0
        }

    async def _get_waste_analysis(self, restaurant_id: str, period_days: int) -> Dict[str, Any]:
        """Get waste analysis from stock movement log"""
        end_date = now_ist()
        start_date = end_date - timedelta(days=period_days)

        pipeline = [
            {
                "$match": {
                    "restaurant_id": restaurant_id,
                    "movement_type": "WASTE",
                    "created_at": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": "$material_id",
                    "total_quantity": {"$sum": "$quantity"},
                    "total_value": {"$sum": "$value_inr"}
                }
            }
        ]

        cursor = self.db.stock_movement_log.aggregate(pipeline)
        waste_items = await cursor.to_list(length=None)

        return {
            "items": waste_items,
            "total_value": sum(w["total_value"] for w in waste_items) / 100
        }


# Singleton instance
_profit_analysis_service = None


def get_profit_analysis_service() -> ProfitAnalysisService:
    """Get singleton profit analysis service instance"""
    global _profit_analysis_service
    if _profit_analysis_service is None:
        _profit_analysis_service = ProfitAnalysisService()
    return _profit_analysis_service
