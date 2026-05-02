"""
Customer Experience Agent

Autonomous agent for daily promotion suggestion generation.
Runs every day at 7:30 AM.

Responsibilities:
1. Analyze historic sales by day-of-week
2. Detect item co-occurrence patterns (basket analysis)
3. Surface demand spikes
4. Cross-reference expiring ingredients with menu items
5. Generate 2-4 targeted promotion suggestions
6. Write suggestions to promotion_suggestions collection (status="pending")

Promotion Types:
- EXPIRY_CLEAR: Clear stock before waste (15-30% off)
- SPIKE_LEVERAGE: Accelerate trending items (10-15% off)
- COMBO_DEAL: Frequently co-ordered pairs (10-20% off each)
- PERCENTAGE_OFF: High-volume day-of-week items (8-12% off)
"""

import logging
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any, Dict, List

from app.core.database import get_database
from app.services.agents.base_agent import Action, AgentDecision, BaseAgent
from app.utils.timezone import now_ist

logger = logging.getLogger(__name__)

RESTAURANT_ID = "antera_jubilee_hills"

# Weekday name → integer mapping (matches order_repository.py: 0=Monday, 6=Sunday)
_WEEKDAY_INT: Dict[str, int] = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


class CustomerExperienceAgent(BaseAgent):
    """
    Customer experience agent — daily promotion suggestion engine.

    Extends BaseAgent with tool-calling loop.
    Writes final suggestions to `promotion_suggestions` MongoDB collection.
    """

    def __init__(self):
        super().__init__(agent_name="customer_experience_agent", max_tokens=8192)

        self.db = get_database()

        self.system_prompt = (
            "You are the Customer Experience Agent for Antera restaurant in Hyderabad. "
            "Your goal is to generate 2-4 targeted daily promotion suggestions to drive revenue, "
            "clear expiring inventory, and increase basket size.\n\n"
            "Available promotion types:\n"
            "- EXPIRY_CLEAR: Items using expiring ingredients, 15-30% discount to clear stock before waste\n"
            "- SPIKE_LEVERAGE: Items trending >30% above normal demand, 10-15% off to accelerate volume\n"
            "- COMBO_DEAL: Item pairs with >12% co-occurrence rate, 10-20% off each when ordered together\n"
            "- PERCENTAGE_OFF: High-volume day-of-week items, 8-12% off to boost familiar patterns\n\n"
            "Rules (strictly follow):\n"
            "- Only suggest EXPIRY_CLEAR if get_expiring_ingredients_with_menu_items returns non-empty results\n"
            "- Only suggest SPIKE_LEVERAGE if spike_ratio >= 1.3\n"
            "- Only suggest COMBO_DEAL if cooccurrence_rate >= 0.12\n"
            "- Only suggest PERCENTAGE_OFF for items where data_sufficient=True\n"
            "- Discount floor: 5%, ceiling: 35%\n"
            "- Maximum 4 suggestions total, minimum 1\n"
            "- COMBO_DEAL: both items in pair receive the same discount_pct independently\n"
            "- reasoning: one concise sentence per suggestion explaining why\n"
            "- When you have finished analyzing all data, call save_promotion_suggestions "
            "with your final list."
        )

        self.tools = [
            {
                "name": "get_sales_by_day_of_week",
                "description": (
                    "Get historical sales aggregated by day-of-week. "
                    "Returns average quantity and revenue per menu item for the given weekday."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "day_of_week": {
                            "type": "string",
                            "description": (
                                "Name of the weekday, e.g. 'Monday', 'Saturday'"
                            ),
                        },
                        "weeks_back": {
                            "type": "integer",
                            "description": "How many weeks of history to scan (default 12)",
                        },
                    },
                    "required": ["day_of_week"],
                },
            },
            {
                "name": "get_item_cooccurrence",
                "description": (
                    "Compute item co-occurrence rates from completed orders. "
                    "Returns top item pairs ordered together most frequently."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "min_support": {
                            "type": "number",
                            "description": "Minimum fraction of orders containing both items (default 0.05)",
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Look-back window in days (default 90)",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_expiring_ingredients_with_menu_items",
                "description": (
                    "Find raw materials expiring soon and the menu items that use them. "
                    "Returns empty list if nothing is expiring."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Expiry look-ahead window in days (default 3)",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_demand_spike_items",
                "description": (
                    "Identify menu items whose recent sales velocity is significantly higher "
                    "than their 30-day baseline, indicating a demand spike."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days_back": {
                            "type": "integer",
                            "description": "Recent window in days to compare against 30-day baseline (default 7)",
                        },
                        "spike_threshold": {
                            "type": "number",
                            "description": "Minimum ratio of recent/historical velocity to qualify as spike (default 1.3)",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "save_promotion_suggestions",
                "description": (
                    "Persist final promotion suggestions to MongoDB promotion_suggestions collection "
                    "with status='pending'. Call this once at the end with all suggestions."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "suggestions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "promo_type": {
                                        "type": "string",
                                        "enum": [
                                            "PERCENTAGE_OFF",
                                            "COMBO_DEAL",
                                            "EXPIRY_CLEAR",
                                            "SPIKE_LEVERAGE",
                                        ],
                                    },
                                    "menu_item_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "menu_item_names": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "discount_pct": {"type": "integer"},
                                    "description": {"type": "string"},
                                    "reasoning": {"type": "string"},
                                    "confidence": {"type": "number"},
                                    "sales_context": {"type": "object"},
                                    "expiring_ingredients": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": [
                                    "promo_type",
                                    "menu_item_ids",
                                    "menu_item_names",
                                    "discount_pct",
                                    "description",
                                    "reasoning",
                                    "confidence",
                                ],
                            },
                        }
                    },
                    "required": ["suggestions"],
                },
            },
        ]

    # ===== Abstract method implementations =====

    async def _gather_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pre-flight: check data sufficiency for today's weekday before launching the agent loop.
        Stashes _last_weekday so _parse_response can reference it.
        """
        today = now_ist()
        weekday = today.strftime("%A")  # e.g. "Saturday"
        self._last_weekday = weekday

        weekday_int = _WEEKDAY_INT.get(weekday, -1)
        cutoff_90d = today - timedelta(days=90)

        n_dow_samples = 0
        data_sufficient = False

        try:
            # Flexible query: check for both 'completed' and 'COMPLETED'
            # Also fetch without order_weekday to be robust against missing fields
            cursor = self.db.orders.find(
                {
                    "status": {"$in": ["completed", "COMPLETED"]},
                    "order_date": {"$gte": cutoff_90d},
                },
                {"order_date": 1, "order_weekday": 1}
            )
            
            count = 0
            async for doc in cursor:
                # Use stored weekday if available, else calculate from date
                doc_weekday = doc.get("order_weekday")
                if doc_weekday is None:
                    doc_date = doc.get("order_date")
                    if isinstance(doc_date, datetime):
                        doc_weekday = doc_date.weekday()
                
                if doc_weekday == weekday_int:
                    count += 1

            # Each week contributes ~1 sample for this weekday; cap at 12
            n_dow_samples = min(count // 10, 12)
            data_sufficient = n_dow_samples >= 4
        except Exception as exc:
            logger.error(f"customer_experience_agent _gather_data: {exc}", exc_info=True)
            n_dow_samples = 0
            data_sufficient = False

        return {
            "weekday": weekday,
            "date_str": today.strftime("%Y-%m-%d"),
            "n_dow_samples": n_dow_samples,
            "data_sufficient": data_sufficient,
        }

    async def _build_prompt(self, data: Dict[str, Any], context: Dict[str, Any]) -> str:
        weekday = data["weekday"]
        date_str = data["date_str"]
        n_samples = data["n_dow_samples"]
        data_sufficient = data["data_sufficient"]

        prompt = (
            f"Today is {weekday}, {date_str}. "
            "Analyze sales data and generate promotion suggestions for today.\n\n"
            f'Step 1: Call get_sales_by_day_of_week with day_of_week="{weekday}".\n'
            "Step 2: Call get_item_cooccurrence to find items frequently ordered together.\n"
            "Step 3: Call get_expiring_ingredients_with_menu_items to find items at risk of expiry.\n"
            "Step 4: Call get_demand_spike_items to identify trending items.\n"
            "Step 5: Based on all data gathered, call save_promotion_suggestions with 2-4 suggestions.\n\n"
            f"Historical context: {n_samples} past {weekday}s found in sales data."
        )

        if not data_sufficient:
            prompt += (
                f"\n\nWARNING: Limited historical data for {weekday}. "
                "Skip PERCENTAGE_OFF type unless clearly justified. "
                "EXPIRY_CLEAR and SPIKE_LEVERAGE can still be used if data supports them."
            )

        return prompt

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        if tool_name == "get_sales_by_day_of_week":
            return await self._tool_sales_dow(**tool_input)
        elif tool_name == "get_item_cooccurrence":
            return await self._tool_cooccurrence(**tool_input)
        elif tool_name == "get_expiring_ingredients_with_menu_items":
            return await self._tool_expiring(**tool_input)
        elif tool_name == "get_demand_spike_items":
            return await self._tool_spikes(**tool_input)
        elif tool_name == "save_promotion_suggestions":
            return await self._tool_save_suggestions(**tool_input)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def _parse_response(self, response: Any) -> AgentDecision:
        save_result = self._last_tool_results.get("save_promotion_suggestions", {})
        saved_count = save_result.get("saved_count", 0) if isinstance(save_result, dict) else 0
        suggestion_ids = (
            save_result.get("suggestion_ids", []) if isinstance(save_result, dict) else []
        )

        weekday = self._last_weekday if hasattr(self, "_last_weekday") else "unknown"

        return AgentDecision(
            actions=[
                Action(
                    action_type="promotion_suggestions_created",
                    data={"suggestion_ids": suggestion_ids, "count": saved_count},
                    reasoning=f"Generated {saved_count} promotion suggestions",
                    confidence=0.9,
                    estimated_cost=0,
                )
            ],
            reasoning="Customer Experience Agent completed daily promotion analysis",
            confidence=0.9,
            metadata={
                "agent_name": "customer_experience_agent",
                "weekday": weekday,
            },
        )

    # ===== Private tool implementations =====

    async def _tool_sales_dow(
        self, day_of_week: str, weeks_back: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Aggregate average quantity and revenue per menu item for a given weekday.
        Uses order_weekday (int) for filtering and name_snapshot for item names.
        """
        weekday_int = _WEEKDAY_INT.get(day_of_week, -1)
        if weekday_int == -1:
            return []

        cutoff = now_ist() - timedelta(weeks=weeks_back)

        try:
            # Flexible query: check for both 'completed' and 'COMPLETED'
            # Fetch broader set and filter in Python to handle missing order_weekday
            cursor = self.db.orders.find(
                {
                    "status": {"$in": ["completed", "COMPLETED"]},
                    "order_date": {"$gte": cutoff},
                },
                {"items": 1, "order_date": 1, "order_weekday": 1},
            )
            
            orders = []
            async for doc in cursor:
                # Use stored weekday if available, else calculate from date
                doc_weekday = doc.get("order_weekday")
                if doc_weekday is None:
                    doc_date = doc.get("order_date")
                    if isinstance(doc_date, datetime):
                        doc_weekday = doc_date.weekday()
                
                if doc_weekday == weekday_int:
                    orders.append(doc)

            if not orders:
                return []

            # Determine distinct ISO weeks sampled
            iso_weeks = set()
            for order in orders:
                od = order.get("order_date")
                if isinstance(od, datetime):
                    iso_weeks.add(od.isocalendar()[:2])  # (year, week_number)
            weeks_sampled = len(iso_weeks) if iso_weeks else 1

            # Accumulate totals per item
            item_totals: Dict[str, Dict[str, Any]] = {}
            for order in orders:
                for item in order.get("items", []):
                    mid = str(item.get("menu_item_id", ""))
                    name = item.get("name_snapshot", mid)
                    qty = int(item.get("quantity", 0))
                    price = int(item.get("price_snapshot", 0))
                    revenue = price * qty

                    if mid not in item_totals:
                        item_totals[mid] = {
                            "menu_item_id": mid,
                            "menu_item_name": name,
                            "total_quantity": 0,
                            "total_revenue_paise": 0,
                        }
                    item_totals[mid]["total_quantity"] += qty
                    item_totals[mid]["total_revenue_paise"] += revenue

            data_sufficient = weeks_sampled >= 4
            result = []
            for entry in item_totals.values():
                result.append(
                    {
                        "menu_item_id": entry["menu_item_id"],
                        "menu_item_name": entry["menu_item_name"],
                        "avg_quantity": round(entry["total_quantity"] / weeks_sampled, 2),
                        "avg_revenue_paise": round(
                            entry["total_revenue_paise"] / weeks_sampled, 2
                        ),
                        "weeks_sampled": weeks_sampled,
                        "data_sufficient": data_sufficient,
                    }
                )

            # Sort by avg_quantity descending for readability
            result.sort(key=lambda x: x["avg_quantity"], reverse=True)
            return result

        except Exception as exc:
            logger.error(f"_tool_sales_dow error: {exc}", exc_info=True)
            return []

    async def _tool_cooccurrence(
        self, min_support: float = 0.05, days_back: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Compute item-pair co-occurrence rates from completed orders.
        Returns top-10 pairs meeting min_support threshold.
        """
        cutoff = now_ist() - timedelta(days=days_back)

        try:
            cursor = self.db.orders.find(
                {
                    "status": {"$in": ["completed", "COMPLETED"]},
                    "order_date": {"$gte": cutoff}
                },
                {"items": 1},
            )
            orders = await cursor.to_list(length=None)

            if not orders:
                return []

            total_orders = len(orders)
            pair_counts: Dict[tuple, Dict[str, Any]] = {}

            for order in orders:
                items = order.get("items", [])
                if len(items) < 2:
                    continue

                # Deduplicate items within a single order by menu_item_id
                seen: Dict[str, str] = {}
                for item in items:
                    mid = str(item.get("menu_item_id", ""))
                    name = item.get("name_snapshot", mid)
                    if mid and mid not in seen:
                        seen[mid] = name

                item_list = sorted(seen.keys())
                for id_a, id_b in combinations(item_list, 2):
                    key = (id_a, id_b)
                    if key not in pair_counts:
                        pair_counts[key] = {
                            "item_a_id": id_a,
                            "item_a_name": seen[id_a],
                            "item_b_id": id_b,
                            "item_b_name": seen[id_b],
                            "count": 0,
                        }
                    pair_counts[key]["count"] += 1

            results = []
            for entry in pair_counts.values():
                support = entry["count"] / total_orders
                if support >= min_support:
                    results.append(
                        {
                            "item_a_id": entry["item_a_id"],
                            "item_a_name": entry["item_a_name"],
                            "item_b_id": entry["item_b_id"],
                            "item_b_name": entry["item_b_name"],
                            "cooccurrence_rate": round(support, 4),
                            "support_count": entry["count"],
                        }
                    )

            results.sort(key=lambda x: x["cooccurrence_rate"], reverse=True)
            return results[:10]

        except Exception as exc:
            logger.error(f"_tool_cooccurrence error: {exc}", exc_info=True)
            return []

    async def _tool_expiring(self, days: int = 3) -> List[Dict[str, Any]]:
        """
        Find raw materials expiring within `days` days and resolve which menu items use them.
        Queries recipe_bom by ingredients.material_id and reads menu_item_name inline.
        """
        cutoff = now_ist() + timedelta(days=days)

        try:
            cursor = self.db.raw_material_inventory.find(
                {
                    "current_stock": {"$gt": 0},
                    "expiry_date": {"$exists": True, "$ne": None, "$lte": cutoff},
                }
            ).sort("expiry_date", 1)
            expiring = await cursor.to_list(length=None)

            if not expiring:
                return []

            results = []
            for material in expiring:
                material_id = material.get("material_id", "")
                expiry = material.get("expiry_date")
                if isinstance(expiry, datetime):
                    expiry_str = expiry.strftime("%Y-%m-%d")
                else:
                    expiry_str = str(expiry) if expiry else "unknown"

                # Find recipes that use this ingredient
                recipe_cursor = self.db.recipe_bom.find(
                    {"ingredients.material_id": material_id}
                )
                recipes = await recipe_cursor.to_list(length=None)

                menu_items = []
                seen_ids: set = set()
                for recipe in recipes:
                    mid = recipe.get("menu_item_id", "")
                    mname = recipe.get("menu_item_name", mid)
                    if mid and mid not in seen_ids:
                        seen_ids.add(mid)
                        menu_items.append(
                            {"menu_item_id": mid, "menu_item_name": mname}
                        )

                results.append(
                    {
                        "material_id": material_id,
                        "material_name": material.get("material_name", ""),
                        "expiry_date": expiry_str,
                        "current_stock": material.get("current_stock", 0),
                        "unit": material.get("unit", ""),
                        "menu_items": menu_items,
                    }
                )

            return results

        except Exception as exc:
            logger.error(f"_tool_expiring error: {exc}", exc_info=True)
            return []

    async def _tool_spikes(
        self, days_back: int = 7, spike_threshold: float = 1.3
    ) -> List[Dict[str, Any]]:
        """
        Identify menu items with a demand spike: recent velocity > spike_threshold * historical velocity.
        Baseline window is always 30 days; recent window is days_back.
        """
        now = now_ist()
        recent_cutoff = now - timedelta(days=days_back)
        historical_cutoff = now - timedelta(days=30)

        try:
            # Fetch orders from the last 30 days (covers both windows)
            cursor = self.db.orders.find(
                {
                    "status": {"$in": ["completed", "COMPLETED"]},
                    "order_date": {"$gte": historical_cutoff},
                },
                {"items": 1, "order_date": 1},
            )
            orders = await cursor.to_list(length=None)

            if not orders:
                return []

            # Separate into recent and historical buckets
            recent_totals: Dict[str, Dict[str, Any]] = {}
            historical_totals: Dict[str, Dict[str, Any]] = {}

            for order in orders:
                order_date = order.get("order_date")
                is_recent = isinstance(order_date, datetime) and order_date >= recent_cutoff

                for item in order.get("items", []):
                    mid = str(item.get("menu_item_id", ""))
                    name = item.get("name_snapshot", mid)
                    qty = int(item.get("quantity", 0))

                    # Always count in historical
                    if mid not in historical_totals:
                        historical_totals[mid] = {"name": name, "qty": 0}
                    historical_totals[mid]["qty"] += qty

                    # Conditionally count in recent
                    if is_recent:
                        if mid not in recent_totals:
                            recent_totals[mid] = {"name": name, "qty": 0}
                        recent_totals[mid]["qty"] += qty

            results = []
            for mid, hist in historical_totals.items():
                historical_velocity = hist["qty"] / 30
                if historical_velocity == 0:
                    continue

                recent_qty = recent_totals.get(mid, {}).get("qty", 0)
                recent_velocity = recent_qty / days_back
                spike_ratio = recent_velocity / historical_velocity

                if spike_ratio >= spike_threshold:
                    results.append(
                        {
                            "menu_item_id": mid,
                            "menu_item_name": hist["name"],
                            "current_velocity": round(recent_velocity, 4),
                            "historical_velocity": round(historical_velocity, 4),
                            "spike_ratio": round(spike_ratio, 4),
                        }
                    )

            results.sort(key=lambda x: x["spike_ratio"], reverse=True)
            return results

        except Exception as exc:
            logger.error(f"_tool_spikes error: {exc}", exc_info=True)
            return []

    async def _tool_save_suggestions(
        self, suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Persist promotion suggestions to MongoDB with status='pending'.
        Returns saved_count and inserted ObjectId strings.
        """
        saved_ids: List[str] = []
        now = now_ist()

        try:
            for i, suggestion in enumerate(suggestions):
                suggestion_id = f"PS_{now.strftime('%Y%m%d_%H%M%S')}_{i}"
                doc = {
                    "suggestion_id": suggestion_id,
                    "status": "pending",
                    "restaurant_id": RESTAURANT_ID,
                    "promo_type": suggestion.get("promo_type"),
                    "menu_item_ids": suggestion.get("menu_item_ids", []),
                    "menu_item_names": suggestion.get("menu_item_names", []),
                    "discount_pct": suggestion.get("discount_pct"),
                    "description": suggestion.get("description", ""),
                    "reasoning": suggestion.get("reasoning", ""),
                    "confidence": suggestion.get("confidence", 0.0),
                    "sales_context": suggestion.get("sales_context", {}),
                    "expiring_ingredients": suggestion.get("expiring_ingredients", []),
                    "created_at": now,
                    "reviewed_at": None,
                    "reviewed_by": None,
                    "approval_notes": None,
                }
                result = await self.db.promotion_suggestions.insert_one(doc)
                saved_ids.append(str(result.inserted_id))

            logger.info(
                f"customer_experience_agent: saved {len(saved_ids)} promotion suggestions"
            )
            return {"saved_count": len(saved_ids), "suggestion_ids": saved_ids}

        except Exception as exc:
            logger.error(f"_tool_save_suggestions error: {exc}", exc_info=True)
            return {"saved_count": 0, "suggestion_ids": [], "error": str(exc)}


# ===== Singleton =====

_cx_agent_instance = None


def get_customer_experience_agent() -> CustomerExperienceAgent:
    """Return the singleton CustomerExperienceAgent instance."""
    global _cx_agent_instance
    if _cx_agent_instance is None:
        _cx_agent_instance = CustomerExperienceAgent()
    return _cx_agent_instance
