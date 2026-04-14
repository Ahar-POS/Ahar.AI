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

# Lazy import — avoid startup failure if joblib/lightgbm not installed
try:
    from app.services.ml.hybrid_abc_forecaster import HybridABCForecaster as _HybridABCForecaster
except Exception as _e:  # noqa: BLE001
    logger.warning(f"HybridABCForecaster import failed: {_e}. v7 model unavailable.")
    _HybridABCForecaster = None


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

        # v7 Hybrid ABC forecaster — primary predictor, Prophet is fallback
        self._v7_forecaster: Optional[Any] = None
        self._v7_load_attempted: bool = False

    async def _get_database(self):
        """Get database connection"""
        if self.db is None:
            self.db = get_database()
        return self.db

    # ============================================================================
    # V7 HYBRID ABC FORECASTER (PRIMARY PATH)
    # ============================================================================

    def _get_v7_forecaster(self) -> Optional[Any]:
        """
        Lazy-load HybridABCForecaster once.
        Returns None (silently) if artifacts are missing or joblib/lightgbm unavailable.
        Prophet takes over automatically when this returns None.
        """
        if self._v7_load_attempted:
            return self._v7_forecaster
        self._v7_load_attempted = True

        if _HybridABCForecaster is None:
            logger.info("v7 forecaster unavailable — using Prophet")
            return None

        try:
            forecaster = _HybridABCForecaster()
            forecaster.load_artifacts()
            self._v7_forecaster = forecaster
            logger.info("HybridABCForecaster v7 ready")
        except Exception as e:
            logger.warning(f"v7 artifact load failed: {e}. Prophet will be used for all items.")

        return self._v7_forecaster

    # ============================================================================
    # LAYER 1: STATISTICAL BASELINE (PROPHET)
    # ============================================================================

    async def _get_historical_orders(
        self,
        menu_item_id: str,
        lookback_days: int = 90,
        as_of_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch historical order data for a menu item

        Args:
            menu_item_id: Menu item identifier
            lookback_days: Number of days to look back
            as_of_date: If set, use as end of history (for backtesting); else use utcnow()

        Returns:
            DataFrame with columns: ds (date), y (quantity)
        """
        db = await self._get_database()
        orders_collection = db["orders"]

        # Calculate date range
        end_date = as_of_date if as_of_date is not None else datetime.utcnow()
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
        horizon_days: int = 7,
        as_of_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Forecast demand for a menu item using Prophet

        Args:
            menu_item_id: Menu item identifier
            horizon_days: Number of days to forecast
            as_of_date: If set, train only on data up to this date (for backtesting)

        Returns:
            Dict with forecast data including yhat, yhat_lower, yhat_upper
        """
        logger.info(f"Forecasting menu item {menu_item_id} for {horizon_days} days")

        # Use large lookback when as_of_date set (train on all data before test period).
        # For live forecasting use 180 days so items with older order history (e.g. seeded
        # data from several months ago) still meet the MIN_HISTORY_DAYS threshold for v7.
        lookback = 730 if as_of_date is not None else 180
        historical = await self._get_historical_orders(
            menu_item_id, lookback_days=lookback, as_of_date=as_of_date
        )

        # ── v7 Hybrid ABC primary path ──────────────────────────────────────
        # Only bypass for backtesting (as_of_date set) to keep Prophet as the
        # backtesting path (v7 models were trained on data up to 2026-02-28).
        if as_of_date is None:
            v7 = self._get_v7_forecaster()
            if v7 is not None:
                db = await self._get_database()
                await v7.load_name_map(db)

                eligible, reason = v7.can_use_v7(menu_item_id, historical)
                if eligible:
                    try:
                        result = v7.predict_item(menu_item_id, historical, horizon_days)
                        logger.info(
                            f"v7 [{result['model_type']}] used for {menu_item_id}"
                        )
                        return result
                    except Exception as exc:
                        logger.warning(
                            f"v7 prediction failed for {menu_item_id}: {exc}. "
                            "Falling back to Prophet."
                        )
                else:
                    # Surface eligibility misses at INFO so operators can understand
                    # why v7 didn't run during manual/on-demand triggers.
                    logger.info(f"v7 ineligible for {menu_item_id}: {reason}")
        # ── end v7 path ──────────────────────────────────────────────────────

        if len(historical) < 14:
            logger.warning(
                f"Insufficient data for {menu_item_id} ({len(historical)} days)"
            )
            return self._create_fallback_forecast(
                menu_item_id, horizon_days, as_of_date=as_of_date
            )

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
            return self._create_fallback_forecast(
                menu_item_id, horizon_days, as_of_date=as_of_date
            )

    def _create_fallback_forecast(
        self,
        menu_item_id: str,
        horizon_days: int,
        as_of_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create simple fallback forecast using historical average

        Used when Prophet fails or insufficient data
        """
        logger.info(f"Using fallback forecast for {menu_item_id}")

        # Use a conservative default (e.g., 5 units/day)
        daily_avg = 5.0
        base_date = as_of_date if as_of_date is not None else datetime.utcnow()

        predictions = []
        for i in range(horizon_days):
            date = (base_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
            predictions.append({
                "date": date,
                "predicted_quantity": daily_avg,
                "lower_bound": daily_avg * 0.7,
                "upper_bound": daily_avg * 1.3
            })

        return {
            "menu_item_id": menu_item_id,
            "forecast_date": (as_of_date or datetime.utcnow()).isoformat(),
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

    # ============================================================================
    # NEW: ENSEMBLE ML FORECASTING
    # ============================================================================

    async def forecast_with_ensemble(
        self,
        ingredient_id: str,
        ingredient_name: str,
        horizon_days: int = 7,
        use_cached_models: bool = True
    ) -> Dict[str, Any]:
        """
        Forecast using ML ensemble (Prophet + SARIMA + XGBoost)

        This is the NEW forecasting method that uses the complete ML system.
        Automatically adapts to data availability (Tier 1-4).

        Args:
            ingredient_id: Ingredient ID
            ingredient_name: Ingredient name
            horizon_days: Days to forecast
            use_cached_models: Use previously trained models if available

        Returns:
            Ensemble forecast with predictions and metadata
        """
        logger.info(f"Ensemble forecasting for {ingredient_name} ({horizon_days} days)")

        try:
            from app.services.ml import TierBasedForecaster
            from app.services.ml.model_registry import get_model_registry
            from app.services.feature_engineering import FeatureEngineeringService

            # Get historical data for training
            lookback_days = 90
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_days)

            db = await self._get_database()
            feature_service = FeatureEngineeringService(db)

            # Load and prepare training data
            train_data = await feature_service.build_ml_features(
                start_date=start_date,
                end_date=end_date,
                include_lags=True
            )

            if train_data.empty:
                logger.warning(f"No training data for {ingredient_name}, falling back to Prophet")
                return await self.forecast_ingredient_demand(ingredient_id, horizon_days)

            # TODO: Filter train_data for this specific ingredient
            # For now, using quantity as proxy

            # Prepare future features for prediction
            future_dates = pd.date_range(
                start=end_date + timedelta(days=1),
                periods=horizon_days,
                freq="D"
            )

            future_df = pd.DataFrame({"order_date": future_dates})

            # Engineer features for future dates (prediction mode)
            future_features = await feature_service.extract_external_features(
                df=future_df,
                mode="prediction"
            )

            # Get exogenous feature names
            exogenous_features = [
                col for col in train_data.columns
                if col not in ["ds", "y", "_id", "order_date"]
            ]

            # Use tier-based forecaster
            forecaster = TierBasedForecaster()

            result = forecaster.forecast(
                train_data=train_data,
                horizon=horizon_days,
                exogenous_future=future_features,
                target_column="y",
                date_column="ds",
                exogenous_features=exogenous_features
            )

            predictions = result["predictions"]

            # Format output
            return {
                "ingredient_id": ingredient_id,
                "ingredient_name": ingredient_name,
                "forecast_method": "ensemble_ml",
                "tier": result["tier"],
                "models_used": result.get("models_used", []),
                "model_weights": result.get("weights", {}),
                "expected_mape": result.get("expected_mape"),
                "confidence": result.get("confidence", "medium"),
                "horizon_days": horizon_days,
                "predictions": predictions.to_dict(orient="records"),
                "predicted_consumption": predictions["yhat"].sum(),
                "confidence_lower": predictions["yhat_lower"].sum(),
                "confidence_upper": predictions["yhat_upper"].sum(),
                "forecasted_at": datetime.utcnow().isoformat(),
                "recommendations": result.get("recommendations", [])
            }

        except Exception as e:
            logger.error(f"Ensemble forecasting failed: {e}", exc_info=True)
            # Fallback to Prophet-based forecast
            logger.info("Falling back to Prophet-based forecast")
            return await self.forecast_ingredient_demand(ingredient_id, horizon_days)

    async def forecast_with_llm_enhancement(
        self,
        baseline_forecast: Dict[str, Any],
        ingredient_name: str
    ) -> Dict[str, Any]:
        """
        Enhance ensemble forecast with LLM reasoning

        Adds:
        - Contextual explanation (why this prediction?)
        - Factor breakdown (weather, events, trends impact)
        - Confidence assessment
        - Actionable recommendations

        Args:
            baseline_forecast: Ensemble forecast result
            ingredient_name: Ingredient name

        Returns:
            Enhanced forecast with LLM reasoning
        """
        logger.info(f"Enhancing forecast with LLM reasoning for {ingredient_name}")

        try:
            # Extract key information
            predictions = baseline_forecast.get("predictions", [])
            predicted_consumption = baseline_forecast.get("predicted_consumption", 0)
            tier = baseline_forecast.get("tier", "unknown")
            models_used = baseline_forecast.get("models_used", [])
            confidence = baseline_forecast.get("confidence", "medium")

            # Build context for LLM
            prompt = f"""
You are analyzing a demand forecast for {ingredient_name}.

Forecast Summary:
- Total predicted consumption (next {len(predictions)} days): {predicted_consumption:.1f} units
- Forecasting method: Ensemble ML ({', '.join(models_used)})
- Data tier: {tier}
- Confidence level: {confidence}
- Expected accuracy (MAPE): {baseline_forecast.get('expected_mape', 'N/A')}%

Daily predictions:
{self._format_predictions_for_llm(predictions)}

Context available:
- Weather forecasts for next {len(predictions)} days
- Upcoming events (festivals, holidays, IPL matches)
- Recent market trends (PyTrends, news sentiment)

Your task:
1. Explain WHY this prediction makes sense (consider weather, events, trends, day-of-week patterns)
2. Break down the key factors influencing the forecast (weather impact, event impact, trend impact)
3. Provide confidence assessment (high/medium/low) with reasoning
4. Give actionable recommendations for the restaurant manager

Respond in JSON format:
{{
    "explanation": "Brief explanation of the forecast",
    "key_factors": [
        {{"factor": "Weather", "impact": "+5%", "explanation": "Rainy weekend increases dine-in"}},
        {{"factor": "Events", "impact": "+10%", "explanation": "Cricket match tomorrow"}}
    ],
    "confidence_assessment": {{
        "level": "high/medium/low",
        "reasoning": "Why this confidence level"
    }},
    "recommendations": [
        "Order 20% extra for Saturday due to expected surge",
        "Monitor weather forecast for adjustments"
    ]
}}
"""

            # Call Claude
            response = self.client.messages.create(
                model=self.settings.CHATBOT_MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON response
            content = response.content[0].text
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)

            if json_match:
                llm_analysis = json.loads(json_match.group(0))
            else:
                llm_analysis = {
                    "explanation": "Forecast based on ensemble ML models",
                    "key_factors": [],
                    "confidence_assessment": {"level": confidence, "reasoning": "Default"},
                    "recommendations": []
                }

            # Merge with baseline forecast
            return {
                **baseline_forecast,
                "llm_reasoning": llm_analysis,
                "explanation": llm_analysis.get("explanation", ""),
                "key_factors": llm_analysis.get("key_factors", []),
                "confidence_assessment": llm_analysis.get("confidence_assessment", {}),
                "llm_recommendations": llm_analysis.get("recommendations", [])
            }

        except Exception as e:
            logger.error(f"LLM enhancement failed: {e}")
            # Return baseline without enhancement
            return {
                **baseline_forecast,
                "llm_reasoning": None,
                "explanation": "Ensemble ML forecast (LLM enhancement unavailable)"
            }

    def _format_predictions_for_llm(self, predictions: List[Dict]) -> str:
        """Format predictions for LLM prompt"""
        if not predictions:
            return "No predictions available"

        lines = []
        for pred in predictions[:7]:  # First 7 days
            date = pred.get("ds", "Unknown")
            yhat = pred.get("yhat", 0)
            lines.append(f"- {date}: {yhat:.1f} units")

        return "\n".join(lines)

    async def forecast_ingredient_with_ml(
        self,
        ingredient_id: str,
        ingredient_name: str,
        horizon_days: int = 7,
        enhance_with_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Complete ML forecasting workflow (Ensemble + LLM)

        This is the main entry point for the new ML forecasting system.

        Args:
            ingredient_id: Ingredient ID
            ingredient_name: Ingredient name
            horizon_days: Days to forecast
            enhance_with_llm: Add LLM reasoning

        Returns:
            Complete forecast with ML predictions and LLM reasoning
        """
        # Step 1: Get ensemble forecast
        ensemble_forecast = await self.forecast_with_ensemble(
            ingredient_id=ingredient_id,
            ingredient_name=ingredient_name,
            horizon_days=horizon_days
        )

        # Step 2: Enhance with LLM if requested
        if enhance_with_llm and self.settings.CLAUDE_API_KEY:
            final_forecast = await self.forecast_with_llm_enhancement(
                baseline_forecast=ensemble_forecast,
                ingredient_name=ingredient_name
            )
        else:
            final_forecast = ensemble_forecast

        return final_forecast

    # ============================================================================
    # END: ENSEMBLE ML FORECASTING
    # ============================================================================

    async def forecast_all_ingredients(
        self,
        horizon_days: int = 7,
        use_cache: bool = True,
        enhance_with_ai: bool = True,
        use_ml_ensemble: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generate forecasts for all ingredients

        Args:
            horizon_days: Number of days to forecast
            use_cache: Use cached forecasts if available
            enhance_with_ai: Apply AI context enhancement (Prophet-based)
            use_ml_ensemble: Use ML ensemble forecasting (NEW!)

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
                # Use ML ensemble if requested
                if use_ml_ensemble:
                    forecast = await self.forecast_ingredient_with_ml(
                        ingredient_id=material_id,
                        ingredient_name=material.get("material_name", material_id),
                        horizon_days=horizon_days,
                        enhance_with_llm=enhance_with_ai
                    )
                else:
                    # Use legacy Prophet-based forecast
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
