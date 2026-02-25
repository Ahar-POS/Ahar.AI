"""
Demand Forecaster Service

Hybrid forecasting system combining statistical models (Prophet) with AI context enhancement.

Three-layer architecture:
1. Statistical Baseline: Prophet time-series forecasting for menu items
2. Menu-to-Ingredient Mapping: Aggregate forecasts to ingredient level
3. AI Context Enhancement: Claude with tools for weather/events adjustments
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import logging
from anthropic import Anthropic

from prophet import Prophet
from prophet.serialize import model_to_json, model_from_json

from app.core.config import get_settings
from app.core.database import get_database
from app.repositories.recipe_repository import get_recipe_repository

logger = logging.getLogger(__name__)


class DemandForecaster:
    """
    Hybrid demand forecasting system

    Combines statistical forecasting (Prophet) with AI-powered context enhancement
    for accurate ingredient-level demand predictions.
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = Anthropic(api_key=self.settings.CLAUDE_API_KEY)
        self.db = None
        self.recipe_repository = get_recipe_repository()

    async def _get_database(self):
        """Get database connection"""
        if self.db is None:
            self.db = get_database()
        return self.db

    # ============================================================================
    # LAYER 1: STATISTICAL BASELINE (PROPHET)
    # ============================================================================

    async def _get_historical_orders(
        self,
        menu_item_id: str,
        lookback_days: int = 90
    ) -> pd.DataFrame:
        """
        Fetch historical order data for a menu item

        Args:
            menu_item_id: Menu item identifier
            lookback_days: Number of days to look back

        Returns:
            DataFrame with columns: ds (date), y (quantity)
        """
        db = await self._get_database()
        orders_collection = db["orders"]

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)

        # Aggregate orders by date
        pipeline = [
            {
                "$match": {
                    "order_date": {
                        "$gte": start_date,
                        "$lte": end_date
                    },
                    "status": {"$ne": "cancelled"}
                }
            },
            {"$unwind": "$items"},
            {
                "$match": {
                    "items.menu_item_id": menu_item_id
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
                    "total_quantity": {"$sum": "$items.quantity"}
                }
            },
            {"$sort": {"_id": 1}}
        ]

        cursor = orders_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)

        if not results:
            logger.warning(f"No historical data found for {menu_item_id}")
            return pd.DataFrame(columns=["ds", "y"])

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                "ds": pd.to_datetime(record["_id"]),
                "y": float(record["total_quantity"])
            }
            for record in results
        ])

        # Fill missing dates with 0
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        df = df.set_index("ds").reindex(date_range, fill_value=0).reset_index()
        df.columns = ["ds", "y"]

        return df

    async def forecast_menu_item(
        self,
        menu_item_id: str,
        horizon_days: int = 7
    ) -> Dict[str, Any]:
        """
        Forecast demand for a menu item using Prophet

        Args:
            menu_item_id: Menu item identifier
            horizon_days: Number of days to forecast

        Returns:
            Dict with forecast data including yhat, yhat_lower, yhat_upper
        """
        logger.info(f"Forecasting menu item {menu_item_id} for {horizon_days} days")

        # Get historical data
        historical = await self._get_historical_orders(menu_item_id, lookback_days=90)

        if len(historical) < 14:
            logger.warning(
                f"Insufficient data for {menu_item_id} ({len(historical)} days)"
            )
            return self._create_fallback_forecast(menu_item_id, horizon_days)

        try:
            # Train Prophet model
            # Suppress Prophet warnings
            import warnings
            warnings.filterwarnings('ignore', category=FutureWarning)

            model = Prophet(
                weekly_seasonality=True,
                yearly_seasonality=False,  # Not enough data
                daily_seasonality=False,
                seasonality_mode='multiplicative',
                changepoint_prior_scale=0.05,  # Conservative for stability
                interval_width=0.80  # 80% confidence interval
            )

            # Suppress Prophet's verbose output
            import logging as py_logging
            py_logging.getLogger('prophet').setLevel(py_logging.ERROR)

            model.fit(historical, algorithm='Newton')

            # Generate forecast
            future = model.make_future_dataframe(periods=horizon_days)
            forecast = model.predict(future)

            # Extract forecast period only
            forecast_period = forecast.tail(horizon_days)

            # Ensure non-negative predictions
            forecast_period["yhat"] = forecast_period["yhat"].clip(lower=0)
            forecast_period["yhat_lower"] = forecast_period["yhat_lower"].clip(lower=0)
            forecast_period["yhat_upper"] = forecast_period["yhat_upper"].clip(lower=0)

            # Calculate confidence score
            confidence = self._calculate_forecast_confidence(
                forecast_period["yhat_lower"].values,
                forecast_period["yhat"].values,
                forecast_period["yhat_upper"].values
            )

            return {
                "menu_item_id": menu_item_id,
                "forecast_date": datetime.utcnow().isoformat(),
                "horizon_days": horizon_days,
                "predictions": [
                    {
                        "date": row["ds"].strftime("%Y-%m-%d"),
                        "predicted_quantity": float(row["yhat"]),
                        "lower_bound": float(row["yhat_lower"]),
                        "upper_bound": float(row["yhat_upper"])
                    }
                    for _, row in forecast_period.iterrows()
                ],
                "total_predicted": float(forecast_period["yhat"].sum()),
                "confidence_score": confidence,
                "historical_avg": float(historical["y"].mean()),
                "model_type": "prophet"
            }

        except Exception as e:
            logger.error(f"Prophet forecasting failed for {menu_item_id}: {e}")
            return self._create_fallback_forecast(menu_item_id, horizon_days)

    def _create_fallback_forecast(
        self,
        menu_item_id: str,
        horizon_days: int
    ) -> Dict[str, Any]:
        """
        Create simple fallback forecast using historical average

        Used when Prophet fails or insufficient data
        """
        logger.info(f"Using fallback forecast for {menu_item_id}")

        # Use a conservative default (e.g., 5 units/day)
        daily_avg = 5.0

        predictions = []
        for i in range(horizon_days):
            date = (datetime.utcnow() + timedelta(days=i+1)).strftime("%Y-%m-%d")
            predictions.append({
                "date": date,
                "predicted_quantity": daily_avg,
                "lower_bound": daily_avg * 0.7,
                "upper_bound": daily_avg * 1.3
            })

        return {
            "menu_item_id": menu_item_id,
            "forecast_date": datetime.utcnow().isoformat(),
            "horizon_days": horizon_days,
            "predictions": predictions,
            "total_predicted": daily_avg * horizon_days,
            "confidence_score": 0.3,  # Low confidence for fallback
            "historical_avg": daily_avg,
            "model_type": "fallback"
        }

    def _calculate_forecast_confidence(
        self,
        lower: np.ndarray,
        pred: np.ndarray,
        upper: np.ndarray
    ) -> float:
        """
        Calculate confidence score based on prediction interval width

        Narrower intervals = higher confidence
        """
        # Average interval width as percentage of prediction
        interval_widths = (upper - lower) / (pred + 1e-6)  # Avoid division by zero
        avg_width = np.mean(interval_widths)

        # Convert to confidence score (0-1)
        # Width of 0.5 (50%) = confidence 0.75
        # Width of 1.0 (100%) = confidence 0.5
        # Width of 2.0 (200%) = confidence 0.25
        confidence = max(0.0, min(1.0, 1.0 - (avg_width / 2)))

        return float(confidence)

    # ============================================================================
    # LAYER 2: MENU-TO-INGREDIENT MAPPING
    # ============================================================================

    async def forecast_ingredient_demand(
        self,
        material_id: str,
        horizon_days: int = 7
    ) -> Dict[str, Any]:
        """
        Forecast ingredient demand by aggregating menu item forecasts

        Args:
            material_id: Raw material identifier
            horizon_days: Number of days to forecast

        Returns:
            Dict with ingredient demand forecast
        """
        logger.info(f"Forecasting ingredient {material_id} for {horizon_days} days")

        # Get all recipes using this ingredient
        recipes = await self.recipe_repository.get_by_ingredient(material_id)

        if not recipes:
            logger.warning(f"No recipes found for ingredient {material_id}")
            return {
                "material_id": material_id,
                "forecast_date": datetime.utcnow().isoformat(),
                "horizon_days": horizon_days,
                "predicted_consumption": 0,
                "confidence_lower": 0,
                "confidence_upper": 0,
                "confidence_score": 0.0,
                "menu_item_breakdown": [],
                "model_type": "no_recipes"
            }

        # Forecast each menu item and aggregate
        total_demand = np.zeros(horizon_days)
        total_lower = np.zeros(horizon_days)
        total_upper = np.zeros(horizon_days)
        breakdown = []
        confidence_scores = []

        for recipe in recipes:
            menu_item_id = recipe["menu_item_id"]

            # Find ingredient quantity in this recipe
            ingredient = next(
                (ing for ing in recipe["ingredients"]
                 if ing["material_id"] == material_id),
                None
            )

            if not ingredient:
                continue

            qty_per_serving = ingredient["quantity_per_serving"]

            # Forecast menu item
            menu_forecast = await self.forecast_menu_item(menu_item_id, horizon_days)

            # Calculate ingredient quantities needed
            for i, pred in enumerate(menu_forecast["predictions"]):
                menu_qty = pred["predicted_quantity"]
                ingredient_qty = menu_qty * qty_per_serving

                total_demand[i] += ingredient_qty
                total_lower[i] += pred["lower_bound"] * qty_per_serving
                total_upper[i] += pred["upper_bound"] * qty_per_serving

            breakdown.append({
                "menu_item_id": menu_item_id,
                "menu_item_name": recipe["menu_item_name"],
                "quantity_per_serving": qty_per_serving,
                "unit": ingredient["unit"],
                "total_menu_items_predicted": menu_forecast["total_predicted"],
                "total_ingredient_needed": menu_forecast["total_predicted"] * qty_per_serving,
                "confidence": menu_forecast["confidence_score"]
            })

            confidence_scores.append(menu_forecast["confidence_score"])

        # Calculate overall confidence (weighted average)
        if confidence_scores:
            avg_confidence = float(np.mean(confidence_scores))
        else:
            avg_confidence = 0.0

        return {
            "material_id": material_id,
            "forecast_date": datetime.utcnow().isoformat(),
            "horizon_days": horizon_days,
            "predicted_consumption": float(total_demand.sum()),
            "confidence_lower": float(total_lower.sum()),
            "confidence_upper": float(total_upper.sum()),
            "confidence_score": avg_confidence,
            "daily_breakdown": [
                {
                    "date": (datetime.utcnow() + timedelta(days=i+1)).strftime("%Y-%m-%d"),
                    "predicted": float(total_demand[i]),
                    "lower": float(total_lower[i]),
                    "upper": float(total_upper[i])
                }
                for i in range(horizon_days)
            ],
            "menu_item_breakdown": breakdown,
            "model_type": "aggregated_prophet"
        }

    # ============================================================================
    # LAYER 3: AI CONTEXT ENHANCEMENT
    # ============================================================================

    async def enhance_with_context(
        self,
        baseline_forecast: Dict[str, Any],
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enhance forecast with weather and events context using Claude

        Args:
            baseline_forecast: Statistical baseline from forecast_ingredient_demand
            location: Location for weather/events (defaults to config)

        Returns:
            Enhanced forecast with AI adjustments
        """
        if location is None:
            location = self.settings.RESTAURANT_LOCATION

        logger.info(f"Enhancing forecast with context for {location}")

        # Get material name
        db = await self._get_database()
        material = await db["raw_material_inventory"].find_one(
            {"material_id": baseline_forecast["material_id"]}
        )
        material_name = material.get("material_name", "Unknown") if material else "Unknown"

        # Build context prompt
        prompt = f"""You are a demand forecasting analyst for a restaurant.

Given this baseline demand forecast for ingredient: {material_name} ({baseline_forecast['material_id']})
- Predicted consumption (next {baseline_forecast['horizon_days']} days): {baseline_forecast['predicted_consumption']:.1f} {material.get('unit', 'units') if material else 'units'}
- Confidence interval: [{baseline_forecast['confidence_lower']:.1f}, {baseline_forecast['confidence_upper']:.1f}]
- Baseline confidence: {baseline_forecast['confidence_score']:.2f}

Location: {location}

Tasks:
1. Use get_weather_forecast to check weather for next {baseline_forecast['horizon_days']} days
2. Use get_local_events to check for holidays or major events
3. Analyze how weather and events will impact restaurant traffic and demand for this ingredient
4. Provide adjusted forecast with reasoning

Consider:
- Rainy/bad weather typically reduces dine-in traffic by 15-25%
- Major holidays/events can increase demand by 30-50%
- Hot weather increases demand for cold beverages and light food
- Cold weather increases demand for hot food and beverages

Return your analysis in JSON format:
{{
    "weather_impact_pct": <number, can be negative>,
    "events_impact_pct": <number, can be negative>,
    "adjusted_forecast": <number>,
    "reasoning": "<detailed explanation>",
    "weather_summary": "<brief summary>",
    "events_summary": "<brief summary>"
}}
"""

        # Define tools for weather and events
        tools = [
            {
                "name": "get_weather_forecast",
                "description": "Get weather forecast for a location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name (e.g., 'Bangalore, India')"
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to forecast (1-7)"
                        }
                    },
                    "required": ["location", "days"]
                }
            },
            {
                "name": "get_local_events",
                "description": "Get upcoming holidays and major events",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City or country name"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date (YYYY-MM-DD)"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date (YYYY-MM-DD)"
                        }
                    },
                    "required": ["location", "start_date", "end_date"]
                }
            }
        ]

        # Tool-calling loop
        messages = [{"role": "user", "content": prompt}]
        max_iterations = 5

        for iteration in range(max_iterations):
            try:
                response = self.client.messages.create(
                    model=self.settings.AGENT_MODEL_DEFAULT,
                    max_tokens=2048,
                    tools=tools,
                    messages=messages
                )

                # Check if we got final response
                if response.stop_reason == "end_turn":
                    # Extract JSON from response
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text

                    # Parse JSON response
                    try:
                        adjustments = json.loads(final_text)
                    except json.JSONDecodeError:
                        # Try to extract JSON from markdown code blocks
                        import re
                        json_match = re.search(r'```json\s*(.*?)\s*```', final_text, re.DOTALL)
                        if json_match:
                            adjustments = json.loads(json_match.group(1))
                        else:
                            logger.warning("Could not parse AI response as JSON")
                            adjustments = {
                                "weather_impact_pct": 0,
                                "events_impact_pct": 0,
                                "adjusted_forecast": baseline_forecast["predicted_consumption"],
                                "reasoning": "Could not parse AI adjustments",
                                "weather_summary": "Unknown",
                                "events_summary": "Unknown"
                            }

                    # Merge with baseline
                    return {
                        **baseline_forecast,
                        "ai_adjustments": adjustments,
                        "final_forecast": adjustments["adjusted_forecast"],
                        "enhancement_status": "success"
                    }

                # Process tool calls
                if response.stop_reason == "tool_use":
                    tool_results = []

                    for block in response.content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input

                            logger.info(f"Executing tool: {tool_name}")

                            # Execute tool
                            if tool_name == "get_weather_forecast":
                                result = await self._get_weather_forecast(
                                    tool_input["location"],
                                    tool_input.get("days", 7)
                                )
                            elif tool_name == "get_local_events":
                                result = await self._get_local_events(
                                    tool_input["location"],
                                    tool_input.get("start_date"),
                                    tool_input.get("end_date")
                                )
                            else:
                                result = {"error": f"Unknown tool: {tool_name}"}

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result)
                            })

                    # Continue conversation with tool results
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})

            except Exception as e:
                logger.error(f"AI context enhancement failed: {e}", exc_info=True)
                return {
                    **baseline_forecast,
                    "final_forecast": baseline_forecast["predicted_consumption"],
                    "enhancement_status": "failed",
                    "enhancement_error": str(e)
                }

        # Max iterations reached
        logger.warning("AI context enhancement reached max iterations")
        return {
            **baseline_forecast,
            "final_forecast": baseline_forecast["predicted_consumption"],
            "enhancement_status": "timeout"
        }

    async def _get_weather_forecast(self, location: str, days: int) -> Dict[str, Any]:
        """
        Fetch weather forecast from OpenWeatherMap API

        Args:
            location: City name
            days: Number of days to forecast

        Returns:
            Weather forecast data
        """
        import httpx

        api_key = self.settings.OPENWEATHERMAP_API_KEY

        if not api_key:
            logger.warning("OpenWeatherMap API key not configured")
            return {
                "error": "Weather API not configured",
                "forecast": []
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openweathermap.org/data/2.5/forecast",
                    params={
                        "q": location,
                        "appid": api_key,
                        "units": "metric",
                        "cnt": min(days * 8, 40)  # 3-hour intervals, max 5 days
                    },
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.error(f"Weather API error: {response.status_code}")
                    return {"error": f"Weather API returned {response.status_code}"}

                data = response.json()

                # Aggregate to daily
                daily_summary = []
                forecast_list = data.get("list", [])

                for i in range(0, len(forecast_list), 8):
                    day_data = forecast_list[i:i+8]
                    if not day_data:
                        continue

                    temps = [d["main"]["temp"] for d in day_data]
                    conditions = [d["weather"][0]["main"] for d in day_data]

                    daily_summary.append({
                        "date": day_data[0]["dt_txt"][:10],
                        "temp_avg": sum(temps) / len(temps),
                        "temp_min": min(temps),
                        "temp_max": max(temps),
                        "condition": max(set(conditions), key=conditions.count),
                        "rain_probability": max(
                            d.get("pop", 0) for d in day_data
                        )
                    })

                return {
                    "location": data.get("city", {}).get("name", location),
                    "forecast": daily_summary
                }

        except Exception as e:
            logger.error(f"Weather API request failed: {e}")
            return {"error": str(e)}

    async def _get_local_events(
        self,
        location: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch local holidays and events

        For MVP, using a simple hardcoded list of major Indian holidays.
        Can be replaced with AbstractAPI or Google Calendar API later.
        """
        # Parse dates
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start = datetime.utcnow()

        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end = start + timedelta(days=7)

        # Major Indian holidays (2026)
        holidays = [
            {"date": "2026-01-26", "name": "Republic Day", "type": "national"},
            {"date": "2026-03-14", "name": "Holi", "type": "festival"},
            {"date": "2026-04-02", "name": "Ram Navami", "type": "festival"},
            {"date": "2026-08-15", "name": "Independence Day", "type": "national"},
            {"date": "2026-10-24", "name": "Diwali", "type": "festival"},
            {"date": "2026-12-25", "name": "Christmas", "type": "festival"}
        ]

        # Filter to date range
        events_in_range = [
            event for event in holidays
            if start <= datetime.strptime(event["date"], "%Y-%m-%d") <= end
        ]

        return {
            "location": location,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "events": events_in_range
        }

    # ============================================================================
    # CACHING AND BATCH OPERATIONS
    # ============================================================================

    async def cache_forecast(self, forecast: Dict[str, Any], ttl_hours: int = 24):
        """
        Cache forecast in demand_forecasts collection

        Args:
            forecast: Forecast data to cache
            ttl_hours: Time to live in hours
        """
        db = await self._get_database()
        collection = db["demand_forecasts"]

        forecast_doc = {
            **forecast,
            "cached_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=ttl_hours)
        }

        # Upsert by material_id
        await collection.update_one(
            {"material_id": forecast["material_id"]},
            {"$set": forecast_doc},
            upsert=True
        )

        logger.info(f"Cached forecast for {forecast['material_id']}")

    async def get_cached_forecast(self, material_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached forecast if not expired

        Args:
            material_id: Raw material identifier

        Returns:
            Cached forecast or None
        """
        db = await self._get_database()
        collection = db["demand_forecasts"]

        forecast = await collection.find_one({
            "material_id": material_id,
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if forecast:
            forecast["id"] = str(forecast.pop("_id"))
            logger.info(f"Using cached forecast for {material_id}")

        return forecast

    async def forecast_all_ingredients(
        self,
        horizon_days: int = 7,
        use_cache: bool = True,
        enhance_with_ai: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate forecasts for all ingredients

        Args:
            horizon_days: Number of days to forecast
            use_cache: Use cached forecasts if available
            enhance_with_ai: Apply AI context enhancement

        Returns:
            List of ingredient forecasts
        """
        logger.info(f"Forecasting all ingredients ({horizon_days} days, AI={enhance_with_ai})")

        # Get all raw materials
        db = await self._get_database()
        materials = await db["raw_material_inventory"].find({}).to_list(length=None)

        forecasts = []

        for material in materials:
            material_id = material["material_id"]

            # Check cache
            if use_cache:
                cached = await self.get_cached_forecast(material_id)
                if cached:
                    forecasts.append(cached)
                    continue

            # Generate forecast
            try:
                baseline = await self.forecast_ingredient_demand(material_id, horizon_days)

                if enhance_with_ai:
                    forecast = await self.enhance_with_context(baseline)
                else:
                    forecast = {**baseline, "final_forecast": baseline["predicted_consumption"]}

                # Cache result
                await self.cache_forecast(forecast)

                forecasts.append(forecast)

            except Exception as e:
                logger.error(f"Forecasting failed for {material_id}: {e}")

        logger.info(f"Generated {len(forecasts)} forecasts")
        return forecasts


# Singleton instance
_demand_forecaster = None


def get_demand_forecaster() -> DemandForecaster:
    """Get singleton demand forecaster instance"""
    global _demand_forecaster
    if _demand_forecaster is None:
        _demand_forecaster = DemandForecaster()
    return _demand_forecaster
