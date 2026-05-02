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
import statistics
from datetime import datetime
from app.utils.timezone import now_ist
from typing import Dict, List, Any, Optional
import json

from app.services.agents.base_agent import BaseAgent, Action, AgentDecision
from app.services.demand_forecaster import get_demand_forecaster
from app.repositories.inventory_repository import get_inventory_repository
from app.core.database import get_database
from app.services.reorder_calculator import effective_reorder_level, compute_order_quantity
from app.services.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)

# How many days of supply to order per category, based on purchase frequency:
#   Fresh items  → daily purchase (1 day)
#   Grocery      → twice a month (~15 days)
#   Consumables/Beverages → once a month (~30 days)
_CATEGORY_RESTOCK_HORIZON: Dict[str, float] = {
    "Vegetables": 1.0,
    "Dairy":      1.0,
    "Proteins":   1.0,
    "Seafood":    1.0,
    "Bakery":     2.0,
    "Grains & Rice": 15.0,
    "Spices":     15.0,
    "Condiments": 15.0,
    "Oils & Fats": 15.0,
    "Packaging":  30.0,
    "Beverages":  30.0,
    "Beer & RTD": 30.0,
    "Cocktails":  30.0,
    "Spirits":    30.0,
    "Wine":       30.0,
}
_DEFAULT_RESTOCK_HORIZON = 7.0  # fallback for unmapped categories


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
        super().__init__(agent_name="inventory_agent", max_tokens=8192)

        self.forecaster = get_demand_forecaster()
        self.inventory_repo = get_inventory_repository()
        self.pricing = get_pricing_service()

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

Forecast Model Guidance (forecast_model field in demand forecast data):
- hybrid_abc_v7_A: LightGBM regression — high-volume item, high confidence (R²≈0.95). Trust quantity.
- hybrid_abc_v7_B: Tweedie regression — mid-volume, moderate confidence (R²≈0.26). Use standard safety buffer.
- hybrid_abc_v7_C: Rolling mean 7-day — low-volume / sparse, lower confidence (R²≈0.30). Add 30% extra safety buffer.
- prophet: Facebook Prophet fallback (item not in v7 training set or insufficient history). Standard safety buffer.
- fallback: Rolling average default (insufficient data for Prophet). Increase safety buffer by 40%; prefer conservative order quantities.
- unknown: Treat same as prophet.

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

    async def execute(self, context: Dict[str, Any]) -> AgentDecision:
        """
        Deterministic execution — bypasses LLM loop entirely.
        The math in _calculate_reorder_needs is sufficient; Claude was only
        acting as a tool-call orchestrator and its text output was never used.
        """
        logger.info("Executing inventory_agent (deterministic mode)")
        try:
            self._execution_context = context
            inventory = await self._get_inventory_status()
            forecasts = await self._get_demand_forecasts()
            reorder_result = await self._calculate_reorder_needs(inventory, forecasts)

            items = reorder_result.get("items_to_reorder", [])
            approval_decisions: Dict[str, Any] = {
                "auto_approve": [],
                "escalate": [i["material_id"] for i in items],
                "defer": [],
                "reasoning": "Approval reasoning skipped — no items",
                "item_reasons": {},
            }
            if items:
                try:
                    material_ids = [i["material_id"] for i in items]
                    baselines = await self._get_historical_price_baselines(material_ids)
                    approval_decisions = await self._reason_about_approvals(items, baselines)
                except Exception as reason_err:
                    logger.warning(
                        f"Approval reasoning failed: {reason_err} — escalating all items"
                    )

            decision = await self._parse_agent_response(
                "", {"calculate_reorder_needs": reorder_result}
            )
            decision.metadata.update({
                "agent_name": self.agent_name,
                "timestamp": now_ist().isoformat(),
                "trigger": context.get("trigger", "unknown"),
                "approval_decisions": approval_decisions,
            })
            await self._write_strategic_insights(reorder_result, context.get("trigger", "scheduled"))
            return decision
        except Exception as e:
            logger.error(f"inventory_agent execution failed: {e}", exc_info=True)
            return AgentDecision(
                actions=[],
                reasoning=f"Agent execution failed: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "agent_name": self.agent_name},
            )

    async def _write_strategic_insights(self, reorder_result: Dict[str, Any], trigger: str = "scheduled") -> None:
        """Write 1-2 strategic insights to agent_insights after daily inventory check."""
        try:
            db = get_database()
            today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
            if trigger == "manual":
                await db.agent_insights.delete_many({
                    "agent": "inventory",
                    "created_at": {"$gte": today_start}
                })
            else:
                existing = await db.agent_insights.find_one({
                    "agent": "inventory",
                    "created_at": {"$gte": today_start}
                })
                if existing:
                    logger.info("Inventory insights already written today — skipping")
                    return

            items = reorder_result.get("items_to_reorder", [])
            urgency_counts = reorder_result.get("urgency_counts", {})
            supplier_breakdown = reorder_result.get("supplier_breakdown", [])
            total_cost_inr = reorder_result.get("total_cost_inr", 0)

            payload = {
                "items_to_reorder": len(items),
                "urgency_counts": urgency_counts,
                "total_reorder_cost_inr": round(total_cost_inr / 100, 2),
                "top_cost_items": sorted(
                    [
                        {
                            "name": i.get("material_name"),
                            "cost_inr": round(i.get("line_total_inr", 0) / 100, 2),
                            "urgency": i.get("urgency"),
                        }
                        for i in items
                    ],
                    key=lambda x: x["cost_inr"],
                    reverse=True,
                )[:5],
                "supplier_summary": [
                    {
                        "supplier": s.get("supplier_name"),
                        "items": s.get("item_count"),
                        "cost_inr": round(s.get("total_cost_inr", 0) / 100, 2),
                    }
                    for s in supplier_breakdown[:4]
                ],
            }

            system_msg = (
                "You are an inventory manager for an Indian restaurant. "
                "Generate 1-2 strategic insights for the owner from today's reorder data. "
                "Focus on cost trends, supplier concentration, or procurement patterns worth acting on. "
                "Output ONLY valid JSON:\n"
                '{"insights": [{"category": "Procurement|StockHealth|Waste|Supplier", '
                '"headline": "max 10 words", "summary": "2-3 sentences with key numbers", '
                '"impact_inr": <integer rupees or null>, "priority": "high|medium|low", '
                '"detail": {"happening": "1 sentence", "why": "1 sentence", '
                '"actions": ["action1", "action2"]}}]}'
            )
            user_msg = f"Today's inventory reorder summary:\n{json.dumps(payload, default=str)}"

            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system_msg,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw_text = response.content[0].text.strip()
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            llm_output = json.loads(raw_text)

            now = now_ist()
            docs = [
                {
                    "agent": "inventory",
                    "category": ins.get("category", "Procurement"),
                    "headline": ins.get("headline", ""),
                    "summary": ins.get("summary", ""),
                    "impact_inr": ins.get("impact_inr"),
                    "priority": ins.get("priority", "medium"),
                    "detail": ins.get("detail", {"happening": "", "why": "", "actions": []}),
                    "status": "active",
                    "created_at": now,
                }
                for ins in llm_output.get("insights", [])[:2]
            ]
            if docs:
                await db.agent_insights.insert_many(docs)
                logger.info(f"Wrote {len(docs)} inventory insights to agent_insights")
        except Exception as e:
            logger.warning(f"Failed to write inventory strategic insights: {e}")

    async def _gather_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Gather data for prompt building. This agent gets most data via tools."""
        return {}

    async def _build_prompt(self, data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Build prompt for Claude

        Guides Claude to call tools and generate shopping list
        """
        today = now_ist().strftime("%Y-%m-%d")
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

        logger.info(f"Inventory agent final response: {final_text[:500]}")
        logger.info(f"Tool results available: {list(tool_results.keys())}")

        return await self._parse_agent_response(final_text, tool_results)

    async def _get_inventory_status(self) -> List[Dict[str, Any]]:
        """
        Get current inventory status

        Returns inventory items with essential fields for reordering
        """
        logger.info("Tool: get_inventory_status")

        items = await self.inventory_repo.get_all(limit=1000)

        # Return simplified view for Claude — `unit_cost_inr` is resolved
        # through the canonical pricing_service so it agrees with every other
        # surface (chatbot, dashboard, shopping list, PO approval card).
        result: List[Dict[str, Any]] = []
        for item in items:
            canonical = await self.pricing.get_current_price(item["material_id"])
            result.append({
                "material_id": item["material_id"],
                "material_name": item["material_name"],
                "category": item["category"],
                "current_stock": item["current_stock"],
                "reorder_level": item["reorder_level"],
                "reorder_qty": item["reorder_qty"],
                "unit": item["unit"],
                "unit_cost_inr": canonical if canonical is not None else item["unit_cost_inr"],
                "lead_time_days": item["lead_time_days"],
                "is_perishable": item["is_perishable"],
                "shelf_life_days": item.get("shelf_life_days"),
                "supplier_id": item["supplier_id"]
            })
        return result

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

        context = getattr(self, "_execution_context", {}) or {}
        forecast_use_cache = bool(context.get("forecast_use_cache", True))

        if not material_ids:
            # Get all forecasts (use cache)
            forecasts = await self.forecaster.forecast_all_ingredients(
                horizon_days=7,
                use_cache=forecast_use_cache,
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
                # forecast_model indicates which predictor was used:
                #   hybrid_abc_v7_A/B/C — v7 Hybrid ABC model (use as-is)
                #   prophet              — Facebook Prophet (reliable but no ABC routing)
                #   fallback             — rolling mean (low confidence; widen safety buffer)
                "forecast_model": f.get("model_type", "unknown"),
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
            lead_time = float(item.get("lead_time_days", 2))
            is_perishable = str(item.get("is_perishable", "No")).strip().lower() == "yes"
            static_reorder = float(item.get("reorder_level", 0))

            # Get forecast
            forecast = forecast_map.get(material_id)
            if not forecast:
                # Fallback path: if item is already below reorder threshold, still include it.
                # This avoids missing shopping lists when forecast cache is stale/incomplete.
                daily_demand = max(item.get("reorder_qty", 0) / 7.0, 0.0)
                demand_std = daily_demand * 0.25
                dyn_reorder = effective_reorder_level(daily_demand, demand_std, lead_time, static_reorder)

                if current_stock > dyn_reorder:
                    logger.warning(f"No forecast for {material_id}, skipping (not low stock)")
                    continue

                logger.warning(f"No forecast for {material_id}, using low-stock fallback")

                days_until_stockout = 0.0 if current_stock <= 0 else float("inf")
                urgency = "URGENT" if current_stock <= 0 else "STANDARD"
                urgency_reason = (
                    "No forecast available; below reorder level - order this week"
                    if urgency == "STANDARD"
                    else "No forecast available; stock is depleted - ORDER TODAY"
                )

                quantity_to_order = compute_order_quantity(
                    daily_demand, demand_std, lead_time, current_stock, is_perishable,
                    shelf_life_days=item.get("shelf_life_days"),
                ) or float(item.get("reorder_qty", 0))
                line_total_inr = quantity_to_order * item["unit_cost_inr"]

                reorder_items.append({
                    "material_id": material_id,
                    "material_name": item["material_name"],
                    "category": item["category"],
                    "unit": item["unit"],
                    "current_stock": current_stock,
                    "reorder_level": round(dyn_reorder, 2),
                    "dynamic_reorder_level": round(dyn_reorder, 2),
                    "days_until_stockout": 0.0 if days_until_stockout == 0.0 else 9999.0,
                    "daily_demand": round(daily_demand, 2),
                    "forecast_horizon_days": 7,
                    "total_demand_next_week": round(daily_demand * 7, 1),
                    "quantity_to_order": round(quantity_to_order, 2),
                    "reorder_qty": float(item.get("reorder_qty", 0)),
                    "unit_cost_inr": item["unit_cost_inr"],
                    "line_total_inr": round(line_total_inr, 2),
                    "urgency": urgency,
                    "urgency_reason": urgency_reason,
                    "supplier_id": item["supplier_id"],
                    "supplier_name": suppliers.get(item["supplier_id"], "Unknown Supplier"),
                    "lead_time_days": item["lead_time_days"],
                    "is_perishable": item["is_perishable"],
                    "shelf_life_days": item.get("shelf_life_days"),
                    "item_status": "pending"
                })
                continue

            # Calculate daily demand and actual σ from 7-day breakdown
            daily_values = [d["predicted"] for d in forecast.get("daily_breakdown", [])]
            daily_demand = (
                sum(daily_values) / len(daily_values)
                if daily_values
                else forecast["predicted_consumption"] / 7.0
            )
            demand_std = (
                statistics.stdev(daily_values)
                if len(daily_values) >= 2
                else daily_demand * 0.25  # fallback when breakdown unavailable
            )

            # Widen safety stock based on forecast model confidence
            # (previously intended for Claude to reason about — now explicit math)
            forecast_model = forecast.get("forecast_model", "unknown")
            if forecast_model == "fallback":
                demand_std *= 1.40
            elif forecast_model == "hybrid_abc_v7_C":
                demand_std *= 1.30
            elif forecast_model == "hybrid_abc_v7_B":
                demand_std *= 1.10

            # Dynamic reorder level — max of safety-stock formula and operator's floor
            dyn_reorder = effective_reorder_level(daily_demand, demand_std, lead_time, static_reorder)

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
                current_stock <= dyn_reorder or
                urgency == "URGENT"
            )

            if should_reorder:
                restock_horizon = _CATEGORY_RESTOCK_HORIZON.get(
                    item.get("category", ""), _DEFAULT_RESTOCK_HORIZON
                )
                quantity_to_order = compute_order_quantity(
                    daily_demand, demand_std, lead_time, current_stock, is_perishable,
                    restock_horizon_days=restock_horizon,
                    shelf_life_days=item.get("shelf_life_days"),
                ) or float(item.get("reorder_qty", 0))
                line_total_inr = quantity_to_order * item["unit_cost_inr"]

                reorder_items.append({
                    "material_id": material_id,
                    "material_name": item["material_name"],
                    "category": item["category"],
                    "unit": item["unit"],

                    # Inventory status
                    "current_stock": current_stock,
                    "reorder_level": round(dyn_reorder, 2),
                    "dynamic_reorder_level": round(dyn_reorder, 2),
                    "days_until_stockout": round(min(days_until_stockout, 9999.0), 1),

                    # Forecasting
                    "daily_demand": round(daily_demand, 2),
                    "forecast_horizon_days": 7,
                    "total_demand_next_week": round(daily_demand * 7, 1),

                    # Reorder details
                    "quantity_to_order": quantity_to_order,
                    "reorder_qty": float(item.get("reorder_qty", 0)),
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
        if days_until_stockout <= 7 or is_perishable:
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
            if is_perishable:
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

    async def _get_historical_price_baselines(
        self, material_ids: List[str]
    ) -> Dict[str, float]:
        """
        Return avg historical price in paise per base unit for each material.

        cost_history stores price_paise_per_base (paise/gram, paise/ml, etc.).
        The shopping list's unit_cost_inr is also paise per the same base unit,
        so no conversion is needed — both are directly comparable.
        """
        db = get_database()
        pipeline = [
            {"$match": {"material_id": {"$in": material_ids}}},
            {"$group": {
                "_id": "$material_id",
                "avg_price_paise": {"$avg": "$price_paise_per_base"},
            }},
        ]
        result: Dict[str, float] = {}
        async for doc in db.cost_history.aggregate(pipeline):
            result[doc["_id"]] = doc["avg_price_paise"]
        return result

    async def _reason_about_approvals(
        self, items: List[Dict], baselines: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Pre-guardrail → single LLM call → post-guardrail.

        Returns {auto_approve, escalate, defer, reasoning, item_reasons}
        where each bucket is a list of material_ids.
        On any LLM failure, escalates all items.
        """
        from app.core.config import get_settings
        settings = get_settings()

        def _fmt_qty(qty: float, unit: str) -> str:
            u = unit.lower()
            if u in ("g", "gram", "grams") and qty >= 1000:
                return f"{qty / 1000:.1f} kg"
            if u == "ml" and qty >= 1000:
                return f"{qty / 1000:.1f} L"
            return f"{qty:.1f} {unit}"
        
        PRICE_VARIANCE_THRESHOLD = 1.15

        # Pre-guardrail: force-escalate only on confirmed price anomaly.
        # Qty spike against reorder_qty is intentionally removed — reorder_qty
        # is a stale seed field that does not reflect actual restaurant-scale demand.
        # The ML forecaster drives quantity; the LLM validates it against
        # daily_demand and days_until_stockout in the item context.
        forced_escalate: Dict[str, str] = {}  # material_id → reason
        for item in items:
            mid = item["material_id"]
            avg_cost = baselines.get(mid)
            current_cost = float(item.get("unit_cost_inr", 0))

            if avg_cost and avg_cost > 0 and current_cost > PRICE_VARIANCE_THRESHOLD * avg_cost:
                diff_pct = (current_cost / avg_cost - 1) * 100
                forced_escalate[mid] = (
                    f"Price increase of {diff_pct:.0f}% vs usual "
                    f"(₹{current_cost/100:.2f}/unit vs historic avg ₹{avg_cost/100:.2f}/unit)"
                )

        # Fetch live Hyperpure prices before LLM reasoning
        from app.services.hyperpure_client import get_hyperpure_client
        try:
            hyperpure = get_hyperpure_client()
            hp_prices = await hyperpure.get_prices(items)
        except Exception as e:
            logger.warning(f"Hyperpure price fetch failed: {e} — proceeding without live prices")
            hp_prices = {}

        # Build context for LLM
        items_for_llm = []
        for i in items:
            mid = i["material_id"]
            avg_cost_rupees = round(baselines[mid] / 100, 2) if mid in baselines else None
            hp_price = hp_prices.get(mid)
            price_delta_pct: Optional[float] = None
            if hp_price is not None and avg_cost_rupees and avg_cost_rupees > 0:
                price_delta_pct = round((hp_price - avg_cost_rupees) / avg_cost_rupees * 100, 1)

            daily_demand = i.get("daily_demand", 0)
            items_for_llm.append({
                "material_id": mid,
                "name": i["material_name"],
                "urgency": i["urgency"],
                "days_until_stockout": i["days_until_stockout"],
                "daily_demand": round(daily_demand, 1),
                "quantity_to_order": i["quantity_to_order"],
                "unit": i["unit"],
                "unit_cost_rupees": round(i.get("unit_cost_inr", 0) / 100, 2),
                "line_total_rupees": round(i.get("line_total_inr", 0) / 100, 2),
                "avg_unit_cost_rupees": avg_cost_rupees,
                "hyperpure_price_rupees": hp_price,
                "price_delta_pct": price_delta_pct,
                "supplier": i.get("supplier_name", "HyperPure"),
                "category": i.get("category", ""),
                "is_perishable": i.get("is_perishable", "No"),
                "force_escalate": mid in forced_escalate,
                "force_reason": forced_escalate.get(mid, ""),
            })

        system_msg = (
            "You are the inventory manager for a large-scale restaurant. Review today's shopping list "
            "and decide for each item: auto_approve (order now), escalate (owner must review), "
            "or defer (weekly digest).\n\n"
            "Decision guidelines:\n"
            "PRICE: This is the only hard signal. If force_escalate=true, you MUST escalate using force_reason.\n"
            "- Price within ±15% of avg_unit_cost_rupees history → safe to auto_approve on price\n"
            "- If avg_unit_cost_rupees is null (no history), treat price as normal\n"
            "- Escalate for price only if the variance is >20% and confirmed abnormal\n\n"
            "QUANTITY: The quantities are ML-forecasted demand for the reorder period.\n"
            "- Do NOT compare quantity_to_order against reorder_qty — reorder_qty is a stale seed value\n"
            "- Instead: quantity_to_order should be roughly consistent with daily_demand × days_until_stockout "
            "(≤3× is normal due to safety stock). Flag if >5× and stockout is >3 days away.\n"
            "- High total cost is normal for this scale — ₹50,000-₹5,00,000 orders are expected\n\n"
            "DEFAULT: URGENT items with reasonable price → auto_approve. "
            "Only escalate when you see a concrete, specific anomaly.\n\n"
            "Output ONLY valid JSON:\n"
            '{"decisions": [{"material_id": "...", "decision": "auto_approve|escalate|defer", '
            '"reason": "One sentence: specific reason (price X vs avg Y, or quantity Z vs daily demand W)"}], '
            '"overall_reasoning": "2-3 sentence summary"}'
        )

        user_msg = (
            f"Today's shopping list ({len(items)} items):\n"
            + json.dumps(items_for_llm, indent=2)
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_msg,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw_text = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                raw_text = "\n".join(
                    lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                )
            llm_output = json.loads(raw_text)
            decisions_by_id = {
                d["material_id"]: d for d in llm_output.get("decisions", [])
            }
            overall_reasoning = llm_output.get("overall_reasoning", "")
        except Exception as e:
            logger.warning(f"LLM reasoning call failed: {e} — escalating all items")
            return {
                "auto_approve": [],
                "escalate": [i["material_id"] for i in items],
                "defer": [],
                "reasoning": "Agent reasoning unavailable — full list sent for review.",
                "item_reasons": {
                    i["material_id"]: "LLM unavailable" for i in items
                },
            }

        # Post-guardrail: force-escalate overrides + budget cap
        auto_approve_candidates: List[tuple] = []  # (material_id, line_total_inr)
        escalate: List[str] = []
        defer: List[str] = []
        item_reasons: Dict[str, str] = {}

        for item in items:
            mid = item["material_id"]
            if mid in forced_escalate:
                escalate.append(mid)
                item_reasons[mid] = forced_escalate[mid]
                continue

            llm_dec = decisions_by_id.get(mid, {})
            decision_val = llm_dec.get("decision", "escalate")
            reason = llm_dec.get("reason", "")

            if decision_val == "auto_approve":
                auto_approve_candidates.append((mid, item.get("line_total_inr", 0)))
                item_reasons[mid] = reason
            elif decision_val == "defer":
                defer.append(mid)
                item_reasons[mid] = reason
            else:
                escalate.append(mid)
                item_reasons[mid] = reason

        # Final auto-approval list
        final_auto = [mid for mid, _ in auto_approve_candidates]

        logger.info(
            f"Approval decisions: {len(final_auto)} auto, "
            f"{len(escalate)} escalate, {len(defer)} defer"
        )
        return {
            "auto_approve": final_auto,
            "escalate": escalate,
            "defer": defer,
            "reasoning": overall_reasoning,
            "item_reasons": item_reasons,
        }

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
            logger.warning(
                "No reorder calculation found in tool results; running deterministic fallback"
            )
            try:
                inventory = tool_results.get("get_inventory_status") or await self._get_inventory_status()
                forecasts = tool_results.get("get_demand_forecasts") or await self._get_demand_forecasts()
                reorder_result = await self._calculate_reorder_needs(inventory, forecasts)
            except Exception as e:
                logger.error(f"Fallback reorder calculation failed: {e}", exc_info=True)
                return AgentDecision(
                    actions=[],
                    reasoning="Unable to calculate reorder needs due to fallback error",
                    confidence=0.0
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
        list_id = f"SL_{now_ist().strftime('%Y-%m-%d')}"

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
