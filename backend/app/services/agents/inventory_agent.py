"""
Inventory Manager Agent

Autonomous agent for inventory reordering and waste prevention.
Generates daily shopping lists grouped by urgency and supplier.

Architecture:
- Extends BaseAgent with tool-calling loop
- Uses DemandForecaster for 7-day predictions
- Classifies items by urgency (URGENT, STANDARD, LOW_PRIORITY)
- Outputs single shopping_list action (not individual POs)

Urgency Levels:
- URGENT: Stockout within lead_time + 1 day (order TODAY)
- STANDARD: Stockout within 7 days OR perishable (order this week)
- LOW_PRIORITY: Stockout >7 days AND non-perishable (weekly digest)
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import json

from app.services.agents.base_agent import BaseAgent, Action, AgentDecision
from app.services.demand_forecaster import get_demand_forecaster
from app.repositories.inventory_repository import get_inventory_repository
from app.core.database import get_database

logger = logging.getLogger(__name__)


class InventoryAgent(BaseAgent):
    """
    Inventory management agent with smart shopping list generation

    Responsibilities:
    1. Check inventory levels vs reorder thresholds
    2. Get 7-day demand forecasts
    3. Calculate days until stockout (with safety buffer)
    4. Classify urgency based on lead time
    5. Generate consolidated shopping list
    6. Flag perishables expiring soon
    """

    def __init__(self):
        super().__init__(agent_name="inventory_agent")

        self.forecaster = get_demand_forecaster()
        self.inventory_repo = get_inventory_repository()

        # System prompt guides Claude's analysis
        self.system_prompt = """You are an inventory management agent for a restaurant.

Your task: Analyze current inventory levels, demand forecasts, and supplier lead times
to generate a consolidated daily shopping list.

Process:
1. Get current inventory status (stock levels, reorder thresholds)
2. Get 7-day demand forecasts for all materials
3. Calculate reorder needs considering:
   - Days until stockout (with 20% safety buffer)
   - Supplier lead times
   - Perishability
4. Classify urgency: URGENT (order today), STANDARD (order this week), LOW_PRIORITY (weekly digest)
5. Group items by supplier for easier batch ordering

Decision Rules:
- Reorder if: current_stock <= reorder_level OR urgency == URGENT
- URGENT: days_until_stockout <= (lead_time_days + 1)
- STANDARD: days_until_stockout <= 7 OR is_perishable
- LOW_PRIORITY: days_until_stockout > 7 AND non-perishable

Output: A single shopping_list with all items, urgency classification, and reasoning."""

        # Define tools for Claude to call
        self.tools = [
            {
                "name": "get_inventory_status",
                "description": "Get current inventory levels for all raw materials",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_demand_forecasts",
                "description": "Get 7-day demand forecasts for materials (from DemandForecaster cache)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "material_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of material IDs to forecast (empty = all materials)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "calculate_reorder_needs",
                "description": "Calculate which items need reordering based on stock, demand, and lead times",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "inventory": {
                            "type": "array",
                            "description": "Array of inventory items with current stock"
                        },
                        "forecasts": {
                            "type": "array",
                            "description": "Array of demand forecasts"
                        }
                    },
                    "required": ["inventory", "forecasts"]
                }
            }
        ]

    async def _gather_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Gather data for prompt building. This agent gets most data via tools."""
        return {}

    async def _build_prompt(self, data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Build prompt for Claude

        Guides Claude to call tools and generate shopping list
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        trigger = context.get("trigger", "scheduled")

        prompt = f"""Today is {today}. Perform daily inventory check (trigger: {trigger}).

Tasks:
1. Call get_inventory_status to get current stock levels
2. Call get_demand_forecasts to get 7-day predictions
3. Call calculate_reorder_needs to determine what to reorder
4. Generate shopping list with urgency classification

Urgency Classification:
- URGENT: Stockout within lead_time + 1 day (need to order TODAY)
- STANDARD: Stockout within 7 days OR perishable items (order this week)
- LOW_PRIORITY: Stockout >7 days AND non-perishable (accumulate for weekly digest)

Important Considerations:
- Lead times: Don't let items stockout before supplier can deliver
- Safety buffer: 20% above forecast (accounts for uncertainty)
- Perishables: Order frequently in smaller batches
- Reorder level: Trigger when current_stock <= reorder_level

Output: Create ONE shopping_list action with all items. Provide clear reasoning."""

        return prompt

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute tool calls from Claude

        Tools:
        - get_inventory_status: Query inventory database
        - get_demand_forecasts: Query forecast cache
        - calculate_reorder_needs: Core reordering logic
        """

        if tool_name == "get_inventory_status":
            return await self._get_inventory_status()

        elif tool_name == "get_demand_forecasts":
            return await self._get_demand_forecasts(tool_input.get("material_ids"))

        elif tool_name == "calculate_reorder_needs":
            return await self._calculate_reorder_needs(
                tool_input["inventory"],
                tool_input["forecasts"]
            )

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _parse_response(self, response: Any) -> AgentDecision:
        """
        Parse Claude's final response into AgentDecision.

        Uses tool results stored by BaseAgent (_last_tool_results), e.g. from
        calculate_reorder_needs, to build the shopping_list action.
        """
        tool_results = getattr(self, "_last_tool_results", {})
        final_text = ""
        if response.content:
            for block in response.content:
                if getattr(block, "text", None):
                    final_text += block.text
        return await self._parse_agent_response(final_text, tool_results)

    async def _get_inventory_status(self) -> List[Dict[str, Any]]:
        """
        Get current inventory status

        Returns inventory items with essential fields for reordering
        """
        logger.info("Tool: get_inventory_status")

        items = await self.inventory_repo.get_all(limit=1000)

        # Return simplified view for Claude
        return [
            {
                "material_id": item["material_id"],
                "material_name": item["material_name"],
                "category": item["category"],
                "current_stock": item["current_stock"],
                "reorder_level": item["reorder_level"],
                "reorder_qty": item["reorder_qty"],
                "unit": item["unit"],
                "unit_cost_inr": item["unit_cost_inr"],
                "lead_time_days": item["lead_time_days"],
                "is_perishable": item["is_perishable"],
                "shelf_life_days": item.get("shelf_life_days"),
                "supplier_id": item["supplier_id"]
            }
            for item in items
        ]

    async def _get_demand_forecasts(
        self,
        material_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get 7-day demand forecasts

        Uses cached forecasts from weekly DemandForecaster run
        Falls back to on-demand generation if cache miss
        """
        logger.info(f"Tool: get_demand_forecasts (materials: {len(material_ids) if material_ids else 'all'})")

        if not material_ids:
            # Get all forecasts (use cache)
            forecasts = await self.forecaster.forecast_all_ingredients(
                horizon_days=7,
                use_cache=True,  # Use cached from weekly run
                enhance_with_ai=False  # Already enhanced in weekly run
            )
        else:
            # Get specific forecasts
            forecasts = []
            for material_id in material_ids:
                # Try cache first
                cached = await self.forecaster.get_cached_forecast(material_id)
                if cached:
                    forecasts.append(cached)
                else:
                    # Generate on-demand if not cached
                    logger.info(f"Cache miss for {material_id}, generating forecast")
                    forecast = await self.forecaster.forecast_ingredient_demand(
                        material_id,
                        horizon_days=7
                    )
                    forecasts.append(forecast)

        # Return simplified view for Claude
        return [
            {
                "material_id": f["material_id"],
                "predicted_consumption": f.get("final_forecast", f["predicted_consumption"]),
                "confidence_score": f["confidence_score"],
                "daily_breakdown": [
                    {
                        "date": day["date"],
                        "predicted": day["predicted"]
                    }
                    for day in f.get("daily_breakdown", [])
                ]
            }
            for f in forecasts
        ]

    async def _calculate_reorder_needs(
        self,
        inventory: List[Dict],
        forecasts: List[Dict]
    ) -> Dict[str, Any]:
        """
        Core reordering logic

        Calculates:
        - Days until stockout (with safety buffer)
        - Urgency classification
        - Reorder recommendations

        Args:
            inventory: Inventory items from get_inventory_status
            forecasts: Forecasts from get_demand_forecasts

        Returns:
            Dict with items_to_reorder, urgency counts, supplier breakdown
        """
        logger.info(f"Tool: calculate_reorder_needs ({len(inventory)} items, {len(forecasts)} forecasts)")

        # Build forecast lookup
        forecast_map = {f["material_id"]: f for f in forecasts}

        # Get supplier info for grouping
        db = get_database()
        suppliers_cursor = db.suppliers.find({})
        suppliers = {s["supplier_id"]: s["supplier_name"] async for s in suppliers_cursor}

        reorder_items = []

        for item in inventory:
            material_id = item["material_id"]
            current_stock = item["current_stock"]
            reorder_level = item["reorder_level"]

            # Get forecast
            forecast = forecast_map.get(material_id)
            if not forecast:
                logger.warning(f"No forecast for {material_id}, skipping")
                continue

            # Calculate daily demand (average over 7 days)
            daily_demand = forecast["predicted_consumption"] / 7.0

            # Days until stockout (with safety buffer)
            days_until_stockout = self._calculate_days_until_stockout(
                current_stock,
                daily_demand
            )

            # Classify urgency
            urgency = self._classify_urgency(
                days_until_stockout,
                item["lead_time_days"],
                item["is_perishable"]
            )

            # Build urgency reason
            urgency_reason = self._build_urgency_reason(
                days_until_stockout,
                item["lead_time_days"],
                item["is_perishable"],
                urgency
            )

            # Should we reorder?
            should_reorder = (
                current_stock <= reorder_level or
                urgency == "URGENT"
            )

            if should_reorder:
                # Calculate line total
                quantity_to_order = item["reorder_qty"]
                line_total_inr = quantity_to_order * item["unit_cost_inr"]

                reorder_items.append({
                    "material_id": material_id,
                    "material_name": item["material_name"],
                    "category": item["category"],
                    "unit": item["unit"],

                    # Inventory status
                    "current_stock": current_stock,
                    "reorder_level": reorder_level,
                    "days_until_stockout": round(days_until_stockout, 1),

                    # Forecasting
                    "daily_demand": round(daily_demand, 2),
                    "forecast_horizon_days": 7,
                    "total_demand_next_week": round(daily_demand * 7, 1),

                    # Reorder details
                    "quantity_to_order": quantity_to_order,
                    "unit_cost_inr": item["unit_cost_inr"],
                    "line_total_inr": line_total_inr,

                    # Urgency
                    "urgency": urgency,
                    "urgency_reason": urgency_reason,

                    # Supplier
                    "supplier_id": item["supplier_id"],
                    "supplier_name": suppliers.get(item["supplier_id"], "Unknown Supplier"),
                    "lead_time_days": item["lead_time_days"],

                    # Additional context
                    "is_perishable": item["is_perishable"],
                    "shelf_life_days": item.get("shelf_life_days"),

                    # Status (for partial approvals later)
                    "item_status": "pending"
                })

        # Calculate urgency counts
        urgency_counts = {
            "urgent": sum(1 for i in reorder_items if i["urgency"] == "URGENT"),
            "standard": sum(1 for i in reorder_items if i["urgency"] == "STANDARD"),
            "low_priority": sum(1 for i in reorder_items if i["urgency"] == "LOW_PRIORITY")
        }

        # Group by supplier
        supplier_breakdown = self._group_by_supplier(reorder_items)

        # Calculate total cost
        total_cost_inr = sum(item["line_total_inr"] for item in reorder_items)

        return {
            "items_to_reorder": reorder_items,
            "urgency_counts": urgency_counts,
            "supplier_breakdown": supplier_breakdown,
            "total_cost_inr": total_cost_inr,
            "summary": (
                f"{len(reorder_items)} items need reordering: "
                f"{urgency_counts['urgent']} URGENT, "
                f"{urgency_counts['standard']} STANDARD, "
                f"{urgency_counts['low_priority']} LOW_PRIORITY. "
                f"Total cost: ₹{total_cost_inr/100:.2f}"
            )
        }

    def _calculate_days_until_stockout(
        self,
        current_stock: float,
        daily_demand: float
    ) -> float:
        """
        Calculate days until stockout with safety buffer

        Safety buffer (20%) accounts for:
        - Forecast uncertainty
        - Demand spikes (busy days, large groups)
        - Supplier delays

        Args:
            current_stock: Current inventory level
            daily_demand: Average daily consumption

        Returns:
            Days until stockout (can be negative if already out)
        """
        if daily_demand <= 0:
            return float('inf')  # No consumption, never stockout

        safety_buffer = 1.2  # 20% above forecast
        adjusted_demand = daily_demand * safety_buffer

        return current_stock / adjusted_demand

    def _classify_urgency(
        self,
        days_until_stockout: float,
        lead_time_days: int,
        is_perishable: str
    ) -> str:
        """
        Classify item urgency

        URGENT: Stockout before supplier can deliver (order TODAY)
        STANDARD: Comfortable margin but order this week
        LOW_PRIORITY: Long runway, accumulate for weekly digest

        Args:
            days_until_stockout: Calculated days until stockout
            lead_time_days: Supplier lead time
            is_perishable: "Yes" or "No"

        Returns:
            Urgency level: URGENT | STANDARD | LOW_PRIORITY
        """
        # Critical: stockout imminent, can't wait for lead time
        if days_until_stockout <= (lead_time_days + 1):
            return "URGENT"

        # Standard: order this week to maintain buffer
        # Perishables: always standard (can't stockpile long-term)
        if days_until_stockout <= 7 or is_perishable == "Yes":
            return "STANDARD"

        # Low priority: non-perishables with long runway
        return "LOW_PRIORITY"

    def _build_urgency_reason(
        self,
        days_until_stockout: float,
        lead_time_days: int,
        is_perishable: str,
        urgency: str
    ) -> str:
        """Build human-readable urgency reason"""
        if urgency == "URGENT":
            return (
                f"Stockout in {days_until_stockout:.1f} days "
                f"(lead time: {lead_time_days} days) - ORDER TODAY"
            )
        elif urgency == "STANDARD":
            if is_perishable == "Yes":
                return f"Perishable item, order this week (stockout in {days_until_stockout:.1f} days)"
            else:
                return f"Stockout in {days_until_stockout:.1f} days - order this week"
        else:
            return f"Non-perishable, stockout in {days_until_stockout:.1f} days - weekly digest"

    def _group_by_supplier(self, items: List[Dict]) -> List[Dict]:
        """
        Group items by supplier for easier batch ordering

        Args:
            items: Reorder items

        Returns:
            List of supplier summaries with item counts and totals
        """
        supplier_map = {}

        for item in items:
            supplier_id = item["supplier_id"]

            if supplier_id not in supplier_map:
                supplier_map[supplier_id] = {
                    "supplier_id": supplier_id,
                    "supplier_name": item["supplier_name"],
                    "item_count": 0,
                    "total_cost_inr": 0,
                    "items": []
                }

            supplier_map[supplier_id]["item_count"] += 1
            supplier_map[supplier_id]["total_cost_inr"] += item["line_total_inr"]
            supplier_map[supplier_id]["items"].append(item["material_id"])

        return list(supplier_map.values())

    async def _parse_agent_response(
        self,
        final_text: str,
        tool_results: Dict[str, Any]
    ) -> AgentDecision:
        """
        Parse Claude's final response into AgentDecision

        Extracts shopping list from calculate_reorder_needs tool result
        Creates shopping_list action with all items
        """
        # Get items from calculate_reorder_needs result
        reorder_result = tool_results.get("calculate_reorder_needs")

        if not reorder_result:
            logger.warning("No reorder calculation found in tool results")
            return AgentDecision(
                actions=[],
                reasoning="No items need reordering",
                confidence=0.9
            )

        items = reorder_result.get("items_to_reorder", [])
        urgency_counts = reorder_result.get("urgency_counts", {})
        total_cost_inr = reorder_result.get("total_cost_inr", 0)

        if not items:
            logger.info("No items need reordering")
            return AgentDecision(
                actions=[],
                reasoning="All inventory levels are adequate. No reordering needed.",
                confidence=0.95
            )

        # Create shopping_list action
        list_id = f"SL_{datetime.utcnow().strftime('%Y-%m-%d')}"

        action = Action(
            action_type="shopping_list",
            data={
                "list_id": list_id,
                "items": items,
                "item_count": len(items),
                "urgency_summary": urgency_counts,
                "supplier_breakdown": reorder_result.get("supplier_breakdown", [])
            },
            estimated_cost=total_cost_inr,
            reasoning=reorder_result.get("summary", "Daily shopping list generated"),
            confidence=0.85
        )

        # Overall decision
        decision = AgentDecision(
            actions=[action],
            reasoning=(
                f"Daily inventory check completed. Generated shopping list with {len(items)} items: "
                f"{urgency_counts.get('urgent', 0)} URGENT, "
                f"{urgency_counts.get('standard', 0)} STANDARD, "
                f"{urgency_counts.get('low_priority', 0)} LOW_PRIORITY. "
                f"Total cost: ₹{total_cost_inr/100:.2f}"
            ),
            confidence=0.85
        )

        return decision


# Singleton
_inventory_agent = None


def get_inventory_agent() -> InventoryAgent:
    """Get singleton inventory agent instance"""
    global _inventory_agent
    if _inventory_agent is None:
        _inventory_agent = InventoryAgent()
    return _inventory_agent
