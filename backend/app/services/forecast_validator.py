"""
Forecast Validation and Accuracy Testing

Provides backtesting framework to measure forecasting accuracy using
historical data. Implements standard metrics (MAE, RMSE, MAPE) and
generates accuracy reports.

Usage:
    validator = ForecastValidator()
    results = await validator.backtest_menu_items(lookback_days=60, test_days=7)
    report = validator.generate_accuracy_report(results)
"""

import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import logging

from app.services.demand_forecaster import get_demand_forecaster
from app.core.database import get_database

logger = logging.getLogger(__name__)


def _json_safe_float(value: float) -> Optional[float]:
    """Return value if finite (no inf/nan), else None so JSON serialization succeeds."""
    if value is None:
        return None
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


class ForecastValidator:
    """
    Backtesting and accuracy validation for demand forecasting

    Key Metrics:
    - MAE (Mean Absolute Error): Average prediction error
    - RMSE (Root Mean Squared Error): Penalizes large errors
    - MAPE (Mean Absolute Percentage Error): Scale-independent accuracy
    - Forecast Bias: Systematic over/under prediction
    - Hit Rate: % of days within acceptable error threshold
    """

    def __init__(self):
        self.forecaster = get_demand_forecaster()
        self.db = None

    async def _get_database(self):
        """Get database connection"""
        if self.db is None:
            self.db = get_database()
        return self.db

    # ============================================================================
    # BACKTESTING: Train on Past, Test on Held-out Data
    # ============================================================================

    async def backtest_menu_items(
        self,
        lookback_days: int = 60,
        test_days: int = 7,
        menu_item_ids: List[str] = None,
        test_start_date: datetime = None,
        test_end_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Perform walk-forward backtesting on menu items

        Strategy:
        1. Use data from [today - lookback_days - test_days] to [today - test_days] for training
          (or when test_start_date/test_end_date given: train on all data before test_start_date)
        2. Predict next test_days
        3. Compare predictions to actual sales

        Args:
            lookback_days: Days of historical data to use for training (ignored if test_start_date set)
            test_days: Days to forecast and validate (ignored if test_end_date - test_start_date used)
            menu_item_ids: Specific items to test (None = all items)
            test_start_date: Start of test window (inclusive). When set, train on all data before this.
            test_end_date: End of test window (inclusive). Required if test_start_date is set.

        Returns:
            Dict with predictions, actuals, and metrics per item
        """
        if test_start_date is not None and test_end_date is not None:
            test_days = (test_end_date - test_start_date).days + 1
            lookback_days = 730  # train on up to 2 years before test start
            logger.info(f"Starting backtest: fixed window {test_start_date.date()} to {test_end_date.date()} ({test_days} days)")
        else:
            logger.info(f"Starting backtest: {lookback_days} training days, {test_days} test days")
            test_end_date = datetime.utcnow()
            test_start_date = test_end_date - timedelta(days=test_days)

        db = await self._get_database()

        # Get all menu items if not specified (include legacy/imported items without is_active)
        if not menu_item_ids:
            menu_items = await db.menu_items.find({
                "$or": [
                    {"is_active": True},
                    {"is_active": {"$exists": False}}
                ]
            }).to_list(length=None)
            menu_item_ids = [item["menu_item_id"] for item in menu_items]

        results = {}

        for menu_item_id in menu_item_ids:
            try:
                # Get actual sales for test period (dates already calculated above)
                actual_sales = await self._get_actual_sales(
                    menu_item_id,
                    test_start_date,
                    test_end_date
                )

                # Generate forecast (using data up to day before test_start_date)
                forecast = await self._forecast_with_cutoff(
                    menu_item_id,
                    cutoff_date=test_start_date - timedelta(days=1),
                    horizon_days=test_days
                )

                # Extract predictions
                predictions = [
                    pred["predicted_quantity"]
                    for pred in forecast["predictions"]
                ]

                # Calculate metrics
                metrics = self._calculate_metrics(actual_sales, predictions)

                results[menu_item_id] = {
                    "menu_item_id": menu_item_id,
                    "actual_sales": actual_sales,
                    "predictions": predictions,
                    "metrics": metrics,
                    "forecast_data": forecast
                }

                logger.info(
                    f"{menu_item_id}: MAE={metrics['mae']:.2f}, "
                    f"MAPE={metrics['mape']:.1f}%, Bias={metrics['bias']:.2f}"
                )

            except Exception as e:
                logger.error(f"Backtest failed for {menu_item_id}: {e}")
                results[menu_item_id] = {"error": str(e)}

        # Calculate aggregate metrics
        aggregate = self._calculate_aggregate_metrics(results)

        return {
            "test_config": {
                "lookback_days": lookback_days,
                "test_days": test_days,
                "test_start_date": test_start_date.isoformat(),
                "test_end_date": test_end_date.isoformat()
            },
            "items": results,
            "aggregate": aggregate
        }

    async def _get_actual_sales(
        self,
        menu_item_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[float]:
        """
        Get actual sales for a menu item in date range

        Returns:
            List of daily sales quantities (0 for days with no sales)
        """
        db = await self._get_database()

        # Aggregate orders by date
        pipeline = [
            {
                "$match": {
                    "order_date": {"$gte": start_date, "$lte": end_date},
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

        cursor = db.orders.aggregate(pipeline)
        results = await cursor.to_list(length=None)

        # Create date-indexed series
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        sales_dict = {
            pd.to_datetime(record["_id"]): record["total_quantity"]
            for record in results
        }

        # Fill missing dates with 0
        actual_sales = [
            sales_dict.get(date, 0.0)
            for date in date_range
        ]

        return actual_sales

    async def _forecast_with_cutoff(
        self,
        menu_item_id: str,
        cutoff_date: datetime,
        horizon_days: int
    ) -> Dict[str, Any]:
        """
        Generate forecast using data only up to cutoff_date.

        First forecast day will be cutoff_date + 1 day (for backtesting).
        """
        forecast = await self.forecaster.forecast_menu_item(
            menu_item_id,
            horizon_days,
            as_of_date=cutoff_date
        )
        return forecast

    # ============================================================================
    # ACCURACY METRICS
    # ============================================================================

    def _calculate_metrics(
        self,
        actual: List[float],
        predicted: List[float]
    ) -> Dict[str, float]:
        """
        Calculate all accuracy metrics

        Args:
            actual: List of actual sales values
            predicted: List of predicted sales values

        Returns:
            Dict with MAE, RMSE, MAPE, bias, hit_rate
        """
        actual_arr = np.array(actual)
        predicted_arr = np.array(predicted)

        # Ensure same length
        min_len = min(len(actual_arr), len(predicted_arr))
        actual_arr = actual_arr[:min_len]
        predicted_arr = predicted_arr[:min_len]

        # Calculate errors
        errors = predicted_arr - actual_arr
        abs_errors = np.abs(errors)

        # MAE: Mean Absolute Error
        mae = float(np.mean(abs_errors))

        # RMSE: Root Mean Squared Error
        rmse = float(np.sqrt(np.mean(errors ** 2)))

        # MAPE: Mean Absolute Percentage Error
        # Avoid division by zero - only calculate for non-zero actuals
        non_zero_mask = actual_arr != 0
        if np.any(non_zero_mask):
            mape = float(
                np.mean(np.abs(errors[non_zero_mask] / actual_arr[non_zero_mask])) * 100
            )
        else:
            mape = 999.0  # Can't calculate MAPE if all actuals are 0; use sentinel (JSON-safe)

        # Forecast Bias: Positive = over-forecasting, Negative = under-forecasting
        bias = float(np.mean(errors))

        # Hit Rate: % of predictions within 20% of actual
        threshold = 0.20  # 20% tolerance
        hits = np.sum(abs_errors <= threshold * actual_arr)
        hit_rate = float(hits / len(actual_arr) * 100) if len(actual_arr) > 0 else 0.0

        # R² (Coefficient of Determination)
        ss_res = np.sum(errors ** 2)
        ss_tot = np.sum((actual_arr - np.mean(actual_arr)) ** 2)
        r_squared = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

        mae = float(np.mean(abs_errors))
        rmse = float(np.sqrt(np.mean(errors ** 2)))

        # Ensure all values are JSON-serializable (no inf/nan)
        return {
            "mae": _json_safe_float(mae) or 0.0,
            "rmse": _json_safe_float(rmse) or 0.0,
            "mape": _json_safe_float(mape) or 999.0,
            "bias": _json_safe_float(bias) or 0.0,
            "hit_rate": _json_safe_float(hit_rate) or 0.0,
            "r_squared": _json_safe_float(r_squared) or 0.0,
            "num_predictions": len(actual_arr)
        }

    def _calculate_aggregate_metrics(
        self,
        results: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate aggregate metrics across all items

        Weighted by actual sales volume (high-volume items matter more)
        """
        all_actuals = []
        all_predictions = []

        for item_id, item_data in results.items():
            if "error" in item_data:
                continue

            all_actuals.extend(item_data["actual_sales"])
            all_predictions.extend(item_data["predictions"])

        if not all_actuals:
            return {"error": "No valid predictions to aggregate"}

        aggregate_metrics = self._calculate_metrics(all_actuals, all_predictions)
        aggregate_metrics["items_tested"] = len([
            r for r in results.values() if "error" not in r
        ])

        return aggregate_metrics

    # ============================================================================
    # INGREDIENT-LEVEL VALIDATION
    # ============================================================================

    async def validate_ingredient_forecasts(
        self,
        test_days: int = 7
    ) -> Dict[str, Any]:
        """
        Validate ingredient-level forecasts against actual consumption

        This is harder because we need to infer ingredient consumption
        from order data + recipes
        """
        logger.info(f"Validating ingredient forecasts for {test_days} days")

        db = await self._get_database()

        # Get all ingredients
        ingredients = await db.raw_material_inventory.find({}).to_list(length=None)

        results = {}

        for ingredient in ingredients:
            material_id = ingredient["material_id"]

            try:
                # Calculate actual consumption (from orders + recipes)
                actual_consumption = await self._calculate_actual_ingredient_consumption(
                    material_id,
                    test_days
                )

                # Get forecast
                forecast = await self.forecaster.forecast_ingredient_demand(
                    material_id,
                    horizon_days=test_days
                )

                predicted_consumption = forecast["predicted_consumption"]

                # Calculate metrics
                error = predicted_consumption - actual_consumption
                pct_error = (error / actual_consumption * 100) if actual_consumption > 0 else 0

                results[material_id] = {
                    "material_id": material_id,
                    "material_name": ingredient["material_name"],
                    "actual_consumption": actual_consumption,
                    "predicted_consumption": predicted_consumption,
                    "error": error,
                    "percentage_error": pct_error,
                    "forecast_confidence": forecast["confidence_score"]
                }

                logger.info(
                    f"{material_id}: Actual={actual_consumption:.1f}, "
                    f"Predicted={predicted_consumption:.1f}, Error={pct_error:.1f}%"
                )

            except Exception as e:
                logger.error(f"Validation failed for {material_id}: {e}")
                results[material_id] = {"error": str(e)}

        return results

    async def _calculate_actual_ingredient_consumption(
        self,
        material_id: str,
        days: int
    ) -> float:
        """
        Calculate actual ingredient consumption from orders + recipes

        Formula: Sum(menu_item_quantity × ingredient_per_serving) for all orders
        """
        db = await self._get_database()

        # Get recipes containing this ingredient
        recipes = await db.recipe_bom.find({
            "ingredients.material_id": material_id
        }).to_list(length=None)

        if not recipes:
            return 0.0

        # Get orders for test period
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        total_consumption = 0.0

        for recipe in recipes:
            menu_item_id = recipe["menu_item_id"]

            # Find ingredient quantity in recipe
            ingredient = next(
                (ing for ing in recipe["ingredients"] if ing["material_id"] == material_id),
                None
            )

            if not ingredient:
                continue

            qty_per_serving = ingredient["quantity_per_serving"]

            # Get order quantities for this menu item
            pipeline = [
                {
                    "$match": {
                        "order_date": {"$gte": start_date, "$lte": end_date},
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
                        "_id": None,
                        "total_quantity": {"$sum": "$items.quantity"}
                    }
                }
            ]

            cursor = db.orders.aggregate(pipeline)
            result = await cursor.to_list(length=1)

            if result:
                menu_item_qty = result[0]["total_quantity"]
                total_consumption += menu_item_qty * qty_per_serving

        return total_consumption

    # ============================================================================
    # REPORTING
    # ============================================================================

    def generate_accuracy_report(
        self,
        backtest_results: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable accuracy report

        Returns:
            Formatted string report
        """
        agg = backtest_results["aggregate"]
        config = backtest_results["test_config"]

        if agg.get("error"):
            return (
                f"Demand forecasting accuracy report\n"
                f"Test: {config['lookback_days']} training days, {config['test_days']} test days\n"
                f"Date range: {config['test_start_date'][:10]} to {config['test_end_date'][:10]}\n\n"
                f"No valid predictions to aggregate. {agg['error']}\n"
                f"Check that you have order data in the test period and that forecasts are generated."
            )

        report = f"""
╔═══════════════════════════════════════════════════════════════╗
║          DEMAND FORECASTING ACCURACY REPORT                   ║
╚═══════════════════════════════════════════════════════════════╝

Test Configuration:
  Training Period: {config['lookback_days']} days
  Test Period: {config['test_days']} days
  Date Range: {config['test_start_date'][:10]} to {config['test_end_date'][:10]}
  Items Tested: {agg.get('items_tested', 0)}

───────────────────────────────────────────────────────────────

AGGREGATE METRICS (across all menu items):

  MAE (Mean Absolute Error):          {agg['mae']:.2f} units
    → Predictions are off by {agg['mae']:.1f} units on average

  RMSE (Root Mean Squared Error):     {agg['rmse']:.2f} units
    → Penalizes large errors more heavily

  MAPE (Mean Absolute % Error):       {f"{agg['mape']:.1f}%" if agg.get('mape') is not None and agg['mape'] < 999 else "N/A"}
    → Predictions are off by {f"{agg['mape']:.1f}%" if agg.get('mape') is not None and agg['mape'] < 999 else "N/A"} on average

  Forecast Bias:                       {agg['bias']:+.2f} units
    → {'Over-forecasting' if agg['bias'] > 0 else 'Under-forecasting'} by {abs(agg['bias']):.1f} units

  Hit Rate (within 20%):               {agg['hit_rate']:.1f}%
    → {agg['hit_rate']:.1f}% of predictions are within 20% of actual

  R² (Coefficient of Determination):   {agg['r_squared']:.3f}
    → Model explains {agg['r_squared']*100:.1f}% of variance

───────────────────────────────────────────────────────────────

INTERPRETATION:

"""

        # Add interpretation based on metrics
        mape_val = agg.get('mape')
        if mape_val is not None and mape_val >= 999:
            report += "  (MAPE N/A for some items - no actual demand in test period)\n"
        elif mape_val is not None and mape_val < 15:
            report += "  ✅ EXCELLENT: MAPE < 15% - Very accurate forecasts\n"
        elif mape_val is not None and mape_val < 25:
            report += "  ✓ GOOD: MAPE 15-25% - Acceptable accuracy for inventory planning\n"
        elif mape_val is not None and mape_val < 40:
            report += "  ⚠ FAIR: MAPE 25-40% - Needs improvement\n"
        elif mape_val is not None:
            report += "  ❌ POOR: MAPE > 40% - Significant forecast error\n"

        if abs(agg['bias']) < 2:
            report += "  ✅ Minimal bias - Balanced forecasts\n"
        elif agg['bias'] > 2:
            report += f"  ⚠ Over-forecasting by {agg['bias']:.1f} units - May lead to waste\n"
        else:
            report += f"  ⚠ Under-forecasting by {abs(agg['bias']):.1f} units - Risk of stockouts\n"

        if agg['hit_rate'] > 70:
            report += f"  ✅ High hit rate ({agg['hit_rate']:.0f}%) - Reliable predictions\n"
        else:
            report += f"  ⚠ Low hit rate ({agg['hit_rate']:.0f}%) - High variability\n"

        report += "\n"

        # Add per-item breakdown for worst performers
        report += "TOP 5 WORST PREDICTIONS (by MAPE):\n\n"

        items_with_metrics = [
            (item_id, data)
            for item_id, data in backtest_results["items"].items()
            if "error" not in data
        ]

        sorted_items = sorted(
            items_with_metrics,
            key=lambda x: x[1]["metrics"]["mape"],
            reverse=True
        )[:5]

        for item_id, data in sorted_items:
            metrics = data["metrics"]
            report += f"  {item_id}: MAPE={metrics['mape']:.1f}%, MAE={metrics['mae']:.2f}\n"

        report += "\n╚═══════════════════════════════════════════════════════════════╝\n"

        return report


# Singleton
_validator = None


def get_forecast_validator() -> ForecastValidator:
    """Get singleton validator instance"""
    global _validator
    if _validator is None:
        _validator = ForecastValidator()
    return _validator
