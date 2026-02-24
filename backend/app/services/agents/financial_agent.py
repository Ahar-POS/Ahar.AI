"""
Financial Analysis Agent

Autonomous agent for financial tracking, profit analysis, and budget monitoring.
Generates daily financial insights and alerts on revenue anomalies.

Responsibilities:
1. Daily revenue analysis and trend detection
2. Profit margin tracking by menu item
3. COGS (Cost of Goods Sold) calculation
4. Revenue anomaly detection
5. Budget variance monitoring
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import statistics

from app.services.agents.base_agent import BaseAgent, Action, AgentDecision
from app.core.database import get_database

logger = logging.getLogger(__name__)


class FinancialAgent(BaseAgent):
    """
    Financial management agent with revenue analysis and profit tracking

    Responsibilities:
    1. Analyze daily/weekly revenue trends
    2. Calculate profit margins per menu item
    3. Track COGS and food cost percentage
    4. Detect revenue anomalies (unusual spikes/drops)
    5. Monitor budget vs actuals
    6. Alert on high-cost low-margin items
    """

    def __init__(self):
        super().__init__(agent_name="financial_agent")

        self.db = get_database()

        # System prompt guides Claude's analysis
        self.system_prompt = """You are a financial analysis agent for a restaurant.

Your task: Analyze revenue, costs, and profitability to identify trends, anomalies, and opportunities.

Process:
1. Get revenue summary (daily, weekly, monthly trends)
2. Calculate profit margins by menu item
3. Analyze COGS and food cost percentages
4. Detect revenue anomalies (unusual patterns)
5. Flag high-cost low-margin items
6. Generate actionable financial insights

Decision Rules:
- Flag anomaly if: daily revenue deviates >30% from 7-day moving average
- Alert if: food cost % >35% (industry standard: 28-35%)
- Recommend price adjustment if: margin <25% for premium items
- Alert if: top items have declining sales trend

Output: Financial insights with alerts, recommendations, and reasoning."""

        # Define tools for Claude to call
        self.tools = [
            {
                "name": "get_revenue_summary",
                "description": "Get revenue summary for specified period (daily, weekly, monthly)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "enum": ["daily", "weekly", "monthly"],
                            "description": "Time period for analysis"
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days to look back (default: 30)"
                        }
                    },
                    "required": ["period"]
                }
            },
            {
                "name": "get_profit_margins",
                "description": "Calculate profit margins by menu item (revenue - COGS)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days to analyze (default: 7)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "detect_revenue_anomalies",
                "description": "Detect unusual revenue patterns using statistical analysis",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "threshold_pct": {
                            "type": "number",
                            "description": "Anomaly threshold percentage (default: 30)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_cost_breakdown",
                "description": "Get COGS breakdown by category and ingredient",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days to analyze (default: 7)"
                        }
                    },
                    "required": []
                }
            }
        ]

    async def _gather_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Gather data for prompt building. This agent gets most data via tools."""
        return {}

    async def _build_prompt(self, data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Build prompt for Claude"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        trigger = context.get("trigger", "scheduled")

        prompt = f"""Today is {today}. Perform daily financial analysis (trigger: {trigger}).

Tasks:
1. Call get_revenue_summary with period="daily" and days_back=30 to get revenue trends
2. Call get_profit_margins with days_back=7 to analyze item profitability
3. Call detect_revenue_anomalies to identify unusual patterns
4. Call get_cost_breakdown with days_back=7 to analyze food costs

Analysis Goals:
- Identify revenue trends (growing, declining, stable)
- Flag revenue anomalies (unusual spikes or drops requiring attention)
- Calculate food cost percentage (target: <35%)
- Find high-cost low-margin items (recommend price adjustments or cost reduction)
- Detect top-performing items (protect/promote these)
- Identify underperforming items (improve or remove)

Important Considerations:
- Revenue anomalies >30% deviation warrant investigation
- Food cost >35% is concerning (industry standard: 28-35%)
- Premium items should have >25% profit margin
- Declining trends in top items are high priority

Output: Create financial_alert actions for issues requiring attention. Include clear reasoning and recommended actions."""

        return prompt

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute tool calls from Claude"""

        if tool_name == "get_revenue_summary":
            return await self._get_revenue_summary(
                tool_input.get("period", "daily"),
                tool_input.get("days_back", 30)
            )

        elif tool_name == "get_profit_margins":
            return await self._get_profit_margins(
                tool_input.get("days_back", 7)
            )

        elif tool_name == "detect_revenue_anomalies":
            return await self._detect_revenue_anomalies(
                tool_input.get("threshold_pct", 30)
            )

        elif tool_name == "get_cost_breakdown":
            return await self._get_cost_breakdown(
                tool_input.get("days_back", 7)
            )

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _parse_response(self, response: Any) -> AgentDecision:
        """Parse Claude's final response into AgentDecision"""
        tool_results = getattr(self, "_last_tool_results", {})
        final_text = ""
        if response.content:
            for block in response.content:
                if getattr(block, "text", None):
                    final_text += block.text

        return await self._parse_agent_response(final_text, tool_results)

    async def _get_revenue_summary(self, period: str, days_back: int) -> Dict[str, Any]:
        """
        Get revenue summary with trends

        Returns daily/weekly/monthly revenue with moving averages
        """
        logger.info(f"Tool: get_revenue_summary (period={period}, days_back={days_back})")

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        # Aggregate revenue by date
        pipeline = [
            {
                "$match": {
                    "order_date": {"$gte": start_date, "$lte": end_date},
                    "status": {"$ne": "cancelled"}
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$order_date"
                        }
                    },
                    "revenue": {"$sum": "$total_amount"},
                    "order_count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]

        cursor = self.db.orders.aggregate(pipeline)
        daily_data = await cursor.to_list(length=None)

        if not daily_data:
            return {
                "period": period,
                "total_revenue": 0,
                "avg_daily_revenue": 0,
                "trend": "no_data",
                "daily_breakdown": []
            }

        # Calculate metrics
        revenues = [d["revenue"] for d in daily_data]
        total_revenue = sum(revenues)
        avg_revenue = total_revenue / len(revenues)

        # Calculate 7-day moving average for trend detection
        moving_avg = []
        for i in range(len(revenues)):
            window_start = max(0, i - 6)
            window_data = revenues[window_start:i+1]
            moving_avg.append(sum(window_data) / len(window_data))

        # Detect trend (last 7 days vs previous 7 days)
        if len(revenues) >= 14:
            recent_avg = sum(revenues[-7:]) / 7
            previous_avg = sum(revenues[-14:-7]) / 7
            trend_pct = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0

            if trend_pct > 10:
                trend = "growing"
            elif trend_pct < -10:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
            trend_pct = 0

        return {
            "period": period,
            "days_analyzed": len(daily_data),
            "total_revenue": total_revenue / 100,  # Convert paise to rupees
            "avg_daily_revenue": avg_revenue / 100,
            "trend": trend,
            "trend_percentage": round(trend_pct, 1),
            "daily_breakdown": [
                {
                    "date": d["_id"],
                    "revenue": d["revenue"] / 100,
                    "order_count": d["order_count"],
                    "moving_avg_7d": moving_avg[i] / 100
                }
                for i, d in enumerate(daily_data)
            ]
        }

    async def _get_profit_margins(self, days_back: int) -> List[Dict[str, Any]]:
        """
        Calculate profit margins by menu item

        Profit = Revenue - COGS (Cost of Goods Sold)
        COGS = Sum of ingredient costs per serving
        """
        logger.info(f"Tool: get_profit_margins (days_back={days_back})")

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        # Get revenue by menu item
        revenue_pipeline = [
            {
                "$match": {
                    "order_date": {"$gte": start_date, "$lte": end_date},
                    "status": {"$ne": "cancelled"}
                }
            },
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.menu_item_id",
                    "menu_item_name": {"$first": "$items.name_snapshot"},
                    "quantity_sold": {"$sum": "$items.quantity"},
                    "total_revenue": {"$sum": {"$multiply": ["$items.price_snapshot", "$items.quantity"]}}
                }
            }
        ]

        cursor = self.db.orders.aggregate(revenue_pipeline)
        revenue_data = {d["_id"]: d async for d in cursor}

        # Get COGS from recipe BOM
        recipes_cursor = self.db.recipe_bom.find({})
        recipes = {r["menu_item_id"]: r async for r in recipes_cursor}

        # Get ingredient costs
        inventory_cursor = self.db.raw_material_inventory.find({})
        inventory = {i["material_id"]: i["unit_cost_inr"] async for i in inventory_cursor}

        # Calculate margins
        margins = []
        for menu_item_id, rev_data in revenue_data.items():
            recipe = recipes.get(menu_item_id)
            if not recipe:
                continue

            # Calculate COGS per serving
            cogs_per_serving = 0
            for ingredient in recipe.get("ingredients", []):
                material_id = ingredient["material_id"]
                quantity = ingredient["quantity"]
                unit_cost = inventory.get(material_id, 0)
                cogs_per_serving += quantity * unit_cost

            # Calculate total COGS and profit
            quantity_sold = rev_data["quantity_sold"]
            total_revenue = rev_data["total_revenue"]
            total_cogs = cogs_per_serving * quantity_sold
            total_profit = total_revenue - total_cogs

            # Profit margin %
            margin_pct = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

            margins.append({
                "menu_item_id": menu_item_id,
                "menu_item_name": rev_data["menu_item_name"],
                "quantity_sold": quantity_sold,
                "revenue": total_revenue / 100,  # Paise to rupees
                "cogs": total_cogs / 100,
                "profit": total_profit / 100,
                "margin_percentage": round(margin_pct, 1),
                "cogs_per_serving": cogs_per_serving / 100
            })

        # Sort by profit descending
        margins.sort(key=lambda x: x["profit"], reverse=True)

        return margins

    async def _detect_revenue_anomalies(self, threshold_pct: float) -> Dict[str, Any]:
        """
        Detect revenue anomalies using statistical analysis

        Anomaly = daily revenue deviates >threshold% from 7-day moving average
        """
        logger.info(f"Tool: detect_revenue_anomalies (threshold={threshold_pct}%)")

        # Get last 30 days of revenue
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        pipeline = [
            {
                "$match": {
                    "order_date": {"$gte": start_date, "$lte": end_date},
                    "status": {"$ne": "cancelled"}
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$order_date"
                        }
                    },
                    "revenue": {"$sum": "$total_amount"}
                }
            },
            {"$sort": {"_id": 1}}
        ]

        cursor = self.db.orders.aggregate(pipeline)
        daily_data = await cursor.to_list(length=None)

        if len(daily_data) < 7:
            return {
                "anomalies_detected": 0,
                "anomalies": [],
                "message": "Insufficient data for anomaly detection (need at least 7 days)"
            }

        # Calculate 7-day moving average
        anomalies = []
        for i in range(6, len(daily_data)):  # Start from day 7
            current_revenue = daily_data[i]["revenue"]

            # Calculate moving average from previous 7 days
            window_data = [daily_data[j]["revenue"] for j in range(i-6, i)]
            moving_avg = sum(window_data) / len(window_data)
            std_dev = statistics.stdev(window_data) if len(window_data) > 1 else 0

            # Calculate deviation
            deviation_pct = ((current_revenue - moving_avg) / moving_avg * 100) if moving_avg > 0 else 0

            # Flag if exceeds threshold
            if abs(deviation_pct) > threshold_pct:
                anomaly_type = "spike" if deviation_pct > 0 else "drop"
                severity = "high" if abs(deviation_pct) > 50 else "medium"

                anomalies.append({
                    "date": daily_data[i]["_id"],
                    "revenue": current_revenue / 100,
                    "expected_revenue": moving_avg / 100,
                    "deviation_percentage": round(deviation_pct, 1),
                    "anomaly_type": anomaly_type,
                    "severity": severity,
                    "reasoning": f"{anomaly_type.capitalize()} of {abs(deviation_pct):.1f}% from 7-day average"
                })

        return {
            "anomalies_detected": len(anomalies),
            "anomalies": anomalies,
            "threshold_percentage": threshold_pct,
            "analysis_period_days": len(daily_data)
        }

    async def _get_cost_breakdown(self, days_back: int) -> Dict[str, Any]:
        """
        Get COGS breakdown by category

        Calculates food cost percentage: (COGS / Revenue) * 100
        Industry standard: 28-35%
        """
        logger.info(f"Tool: get_cost_breakdown (days_back={days_back})")

        end_date = datetime.utcnow()
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
                    "total_revenue": {"$sum": "$total_amount"}
                }
            }
        ]

        cursor = self.db.orders.aggregate(revenue_pipeline)
        revenue_result = await cursor.to_list(length=1)
        total_revenue = revenue_result[0]["total_revenue"] if revenue_result else 0

        # Get items sold
        items_pipeline = [
            {
                "$match": {
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

        cursor = self.db.orders.aggregate(items_pipeline)
        items_sold = {d["_id"]: d["quantity_sold"] async for d in cursor}

        # Get recipes and calculate COGS by category
        recipes_cursor = self.db.recipe_bom.find({})
        recipes = await recipes_cursor.to_list(length=None)

        # Get all inventory for costs
        inventory_cursor = self.db.raw_material_inventory.find({})
        inventory = {i["material_id"]: i async for i in inventory_cursor}

        category_costs = {}
        total_cogs = 0

        for recipe in recipes:
            menu_item_id = recipe["menu_item_id"]
            quantity_sold = items_sold.get(menu_item_id, 0)

            if quantity_sold == 0:
                continue

            # Calculate COGS for this menu item
            item_cogs = 0
            for ingredient in recipe.get("ingredients", []):
                material_id = ingredient["material_id"]
                inv_item = inventory.get(material_id)

                if not inv_item:
                    continue

                category = inv_item.get("category", "Other")
                cost = ingredient["quantity"] * inv_item["unit_cost_inr"] * quantity_sold

                item_cogs += cost
                category_costs[category] = category_costs.get(category, 0) + cost

            total_cogs += item_cogs

        # Calculate food cost percentage
        food_cost_pct = (total_cogs / total_revenue * 100) if total_revenue > 0 else 0

        # Format category breakdown
        category_breakdown = [
            {
                "category": cat,
                "total_cost": cost / 100,
                "percentage_of_cogs": round((cost / total_cogs * 100) if total_cogs > 0 else 0, 1)
            }
            for cat, cost in sorted(category_costs.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "period_days": days_back,
            "total_revenue": total_revenue / 100,
            "total_cogs": total_cogs / 100,
            "food_cost_percentage": round(food_cost_pct, 1),
            "target_range": "28-35%",
            "status": "good" if food_cost_pct <= 35 else "high",
            "category_breakdown": category_breakdown
        }

    async def _parse_agent_response(
        self,
        final_text: str,
        tool_results: Dict[str, Any]
    ) -> AgentDecision:
        """
        Parse Claude's final response into AgentDecision

        Creates financial_alert actions for issues requiring attention
        """
        actions = []

        # Extract key insights from tool results
        revenue_summary = tool_results.get("get_revenue_summary", {})
        anomalies_result = tool_results.get("detect_revenue_anomalies", {})
        cost_breakdown = tool_results.get("get_cost_breakdown", {})
        profit_margins = tool_results.get("get_profit_margins", [])

        # 1. Revenue anomaly alerts
        anomalies = anomalies_result.get("anomalies", [])
        for anomaly in anomalies:
            if anomaly["severity"] == "high":
                actions.append(Action(
                    action_type="financial_alert",
                    data={
                        "alert_type": "revenue_anomaly",
                        "severity": anomaly["severity"],
                        "date": anomaly["date"],
                        "details": anomaly
                    },
                    estimated_cost=0,  # Informational
                    reasoning=f"Revenue {anomaly['anomaly_type']} detected on {anomaly['date']}: {anomaly['reasoning']}",
                    confidence=0.9
                ))

        # 2. Food cost alert
        food_cost_pct = cost_breakdown.get("food_cost_percentage", 0)
        if food_cost_pct > 35:
            actions.append(Action(
                action_type="financial_alert",
                data={
                    "alert_type": "high_food_cost",
                    "food_cost_percentage": food_cost_pct,
                    "target_range": "28-35%",
                    "excess_amount": round((food_cost_pct - 35) * cost_breakdown.get("total_revenue", 0) / 100, 2)
                },
                estimated_cost=0,
                reasoning=f"Food cost at {food_cost_pct}% exceeds industry standard (35%). Review pricing or reduce ingredient costs.",
                confidence=0.85
            ))

        # 3. Low margin items
        low_margin_items = [item for item in profit_margins if item["margin_percentage"] < 25]
        if low_margin_items:
            actions.append(Action(
                action_type="financial_alert",
                data={
                    "alert_type": "low_margin_items",
                    "items": low_margin_items[:5],  # Top 5 worst performers
                    "count": len(low_margin_items)
                },
                estimated_cost=0,
                reasoning=f"{len(low_margin_items)} items have margins <25%. Consider price increases or cost reduction.",
                confidence=0.8
            ))

        # 4. Revenue trend alert
        trend = revenue_summary.get("trend")
        if trend == "declining":
            actions.append(Action(
                action_type="financial_alert",
                data={
                    "alert_type": "declining_revenue",
                    "trend_percentage": revenue_summary.get("trend_percentage", 0),
                    "avg_daily_revenue": revenue_summary.get("avg_daily_revenue", 0)
                },
                estimated_cost=0,
                reasoning=f"Revenue declining by {abs(revenue_summary.get('trend_percentage', 0))}%. Investigate cause and take corrective action.",
                confidence=0.75
            ))

        # Build overall decision
        if not actions:
            return AgentDecision(
                actions=[],
                reasoning="Financial health looks good. No critical issues detected.",
                confidence=0.9
            )

        # Summarize findings
        summary_parts = []
        if anomalies:
            summary_parts.append(f"{len(anomalies)} revenue anomalies")
        if food_cost_pct > 35:
            summary_parts.append(f"food cost at {food_cost_pct}%")
        if low_margin_items:
            summary_parts.append(f"{len(low_margin_items)} low-margin items")
        if trend == "declining":
            summary_parts.append("declining revenue trend")

        reasoning = f"Financial analysis completed. Issues detected: {', '.join(summary_parts)}. Review alerts for details."

        return AgentDecision(
            actions=actions,
            reasoning=reasoning,
            confidence=0.85,
            metadata={
                "total_revenue": revenue_summary.get("total_revenue", 0),
                "food_cost_pct": food_cost_pct,
                "trend": trend
            }
        )


# Singleton
_financial_agent = None


def get_financial_agent() -> FinancialAgent:
    """Get singleton financial agent instance"""
    global _financial_agent
    if _financial_agent is None:
        _financial_agent = FinancialAgent()
    return _financial_agent
