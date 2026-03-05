"""
Forecast Validation API Endpoints

Provides endpoints to test and validate forecasting accuracy using backtesting.
"""

from datetime import datetime
from fastapi import APIRouter, Query
from typing import Optional, List
import logging

from app.services.forecast_validator import get_forecast_validator
from app.utils.response import success_response, error_response

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_date(s: str) -> datetime:
    """Parse YYYY-MM-DD to datetime at start of day (UTC)."""
    return datetime.strptime(s.strip()[:10], "%Y-%m-%d")


@router.post("/backtest/menu-items")
async def backtest_menu_items(
    lookback_days: int = Query(60, ge=30, le=180, description="Days of historical data for training"),
    test_days: int = Query(7, ge=1, le=30, description="Days to forecast and validate"),
    menu_item_ids: Optional[List[str]] = Query(None, description="Specific items to test (None = all)"),
    test_start_date: Optional[str] = Query(None, description="Fixed test window start (YYYY-MM-DD). Use with test_end_date."),
    test_end_date: Optional[str] = Query(None, description="Fixed test window end (YYYY-MM-DD). Use with test_start_date.")
):
    """
    Run backtesting on menu item forecasts

    This tests how well Prophet can predict menu item sales by:
    1. Training on historical data (lookback_days, or all data before test_start_date when fixed window used)
    2. Predicting the test period
    3. Comparing predictions to actual sales

    Args:
        lookback_days: Days of historical data to use (30-180); ignored if test_start_date set
        test_days: Days to forecast and validate (1-30); ignored if test_start_date/test_end_date set
        menu_item_ids: Optional list of specific items to test
        test_start_date: Start of test window (e.g. 2026-01-24). Train on all data before this.
        test_end_date: End of test window (e.g. 2026-01-31). Must provide both start and end.

    Returns:
        Accuracy metrics (MAE, RMSE, MAPE, bias) per item and aggregate
    """
    try:
        validator = get_forecast_validator()

        start_dt = None
        end_dt = None
        if test_start_date is not None and test_end_date is not None:
            start_dt = _parse_date(test_start_date)
            end_dt = _parse_date(test_end_date)
            if start_dt > end_dt:
                return error_response(
                    code="INVALID_DATES",
                    message="test_start_date must be before or equal to test_end_date",
                    details={"test_start_date": test_start_date, "test_end_date": test_end_date}
                )

        results = await validator.backtest_menu_items(
            lookback_days=lookback_days,
            test_days=test_days,
            menu_item_ids=menu_item_ids,
            test_start_date=start_dt,
            test_end_date=end_dt
        )

        # Generate report
        report = validator.generate_accuracy_report(results)

        return success_response(
            data={
                "results": results,
                "report": report
            },
            message=f"Backtest completed: {results['aggregate'].get('items_tested', 0)} items tested"
        )

    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        return error_response(
            code="BACKTEST_FAILED",
            message="Failed to run backtest",
            details={"error": str(e)}
        )


@router.post("/validate/ingredients")
async def validate_ingredient_forecasts(
    test_days: int = Query(7, ge=1, le=30, description="Days to validate")
):
    """
    Validate ingredient-level forecasts against actual consumption

    Calculates actual ingredient consumption from orders + recipes
    and compares to forecasted consumption.

    Args:
        test_days: Days to validate (1-30)

    Returns:
        Comparison of actual vs predicted consumption per ingredient
    """
    try:
        validator = get_forecast_validator()

        results = await validator.validate_ingredient_forecasts(
            test_days=test_days
        )

        # Calculate summary stats
        valid_results = [
            r for r in results.values() if "error" not in r
        ]

        if valid_results:
            avg_error = sum(abs(r["percentage_error"]) for r in valid_results) / len(valid_results)
            summary = {
                "ingredients_tested": len(valid_results),
                "average_percentage_error": avg_error,
                "within_20_percent": sum(1 for r in valid_results if abs(r["percentage_error"]) <= 20),
                "within_30_percent": sum(1 for r in valid_results if abs(r["percentage_error"]) <= 30)
            }
        else:
            summary = {"error": "No valid results"}

        return success_response(
            data={
                "results": results,
                "summary": summary
            },
            message=f"Validated {len(valid_results)} ingredients"
        )

    except Exception as e:
        logger.error(f"Ingredient validation failed: {e}", exc_info=True)
        return error_response(
            code="VALIDATION_FAILED",
            message="Failed to validate ingredient forecasts",
            details={"error": str(e)}
        )


@router.get("/metrics/explain")
async def explain_metrics():
    """
    Explain forecasting accuracy metrics

    Returns:
        Detailed explanation of each metric and how to interpret them
    """
    explanation = {
        "metrics": {
            "MAE": {
                "name": "Mean Absolute Error",
                "formula": "mean(|actual - predicted|)",
                "interpretation": "Average prediction error in units",
                "example": "MAE = 5 means predictions are off by 5 units on average",
                "good_value": "< 10% of average demand",
                "use_case": "Easy to interpret, same units as your data"
            },
            "RMSE": {
                "name": "Root Mean Squared Error",
                "formula": "sqrt(mean((actual - predicted)²))",
                "interpretation": "Penalizes large errors more than small ones",
                "example": "RMSE = 8 with MAE = 5 indicates some large errors",
                "good_value": "Close to MAE (indicates consistent errors)",
                "use_case": "When large errors are particularly costly (stockouts)"
            },
            "MAPE": {
                "name": "Mean Absolute Percentage Error",
                "formula": "mean(|actual - predicted| / actual) × 100%",
                "interpretation": "Average error as percentage of actual value",
                "example": "MAPE = 15% means predictions are 15% off on average",
                "good_value": "< 15% excellent, < 25% good, < 40% acceptable",
                "use_case": "Comparing accuracy across different items/scales"
            },
            "Bias": {
                "name": "Forecast Bias",
                "formula": "mean(predicted - actual)",
                "interpretation": "Systematic over/under forecasting",
                "example": "Bias = +3 means over-forecasting by 3 units (waste)",
                "good_value": "Close to 0 (unbiased forecasts)",
                "use_case": "Detecting if model consistently over or under predicts"
            },
            "Hit_Rate": {
                "name": "Hit Rate (within threshold)",
                "formula": "% of predictions within 20% of actual",
                "interpretation": "Reliability of predictions",
                "example": "Hit rate = 75% means 3/4 predictions are within 20%",
                "good_value": "> 70% for reliable planning",
                "use_case": "Understanding prediction consistency"
            },
            "R_Squared": {
                "name": "Coefficient of Determination",
                "formula": "1 - (sum_squared_residuals / total_sum_squares)",
                "interpretation": "How much variance the model explains",
                "example": "R² = 0.8 means model explains 80% of variance",
                "good_value": "> 0.7 strong, > 0.5 moderate, < 0.3 weak",
                "use_case": "Overall model quality assessment"
            }
        },
        "interpretation_guide": {
            "excellent": "MAPE < 15%, R² > 0.8, Hit Rate > 80%",
            "good": "MAPE 15-25%, R² 0.6-0.8, Hit Rate 70-80%",
            "acceptable": "MAPE 25-40%, R² 0.4-0.6, Hit Rate 60-70%",
            "poor": "MAPE > 40%, R² < 0.4, Hit Rate < 60%"
        },
        "business_impact": {
            "over_forecasting": {
                "indicator": "Positive bias",
                "consequence": "Food waste, tied-up capital, spoilage",
                "action": "Review safety buffers, check for systematic issues"
            },
            "under_forecasting": {
                "indicator": "Negative bias",
                "consequence": "Stockouts, lost sales, customer dissatisfaction",
                "action": "Increase safety stock, reduce lead times"
            },
            "high_variability": {
                "indicator": "RMSE >> MAE, low hit rate",
                "consequence": "Unpredictable inventory needs",
                "action": "Analyze outliers, consider external factors (weather, events)"
            }
        }
    }

    return success_response(
        data=explanation,
        message="Forecasting metrics explained"
    )


@router.get("/benchmark")
async def get_industry_benchmarks():
    """
    Get industry benchmarks for forecasting accuracy

    Returns:
        Typical MAPE ranges for different industries and forecasting horizons
    """
    benchmarks = {
        "restaurant_forecasting": {
            "menu_items_daily": {
                "excellent": "< 15%",
                "good": "15-25%",
                "acceptable": "25-40%",
                "poor": "> 40%",
                "note": "Daily restaurant sales are highly variable"
            },
            "ingredient_weekly": {
                "excellent": "< 10%",
                "good": "10-20%",
                "acceptable": "20-30%",
                "poor": "> 30%",
                "note": "Weekly aggregation smooths daily volatility"
            }
        },
        "by_horizon": {
            "1_day_ahead": {
                "typical_mape": "15-25%",
                "challenge": "High daily variability, weather, events"
            },
            "7_days_ahead": {
                "typical_mape": "20-30%",
                "challenge": "Longer horizon increases uncertainty"
            },
            "30_days_ahead": {
                "typical_mape": "30-50%",
                "challenge": "Many unknown factors, seasonal changes"
            }
        },
        "other_industries": {
            "retail_fashion": "30-50% MAPE (high seasonality)",
            "grocery_staples": "10-20% MAPE (stable demand)",
            "fast_food": "20-35% MAPE (similar to restaurant)",
            "manufacturing": "5-15% MAPE (controllable production)"
        },
        "prophet_typical_accuracy": {
            "with_good_data": "10-20% MAPE (90+ days history, clear patterns)",
            "with_sparse_data": "25-40% MAPE (<30 days history, irregular patterns)",
            "note": "Prophet works best with weekly/yearly seasonality"
        }
    }

    return success_response(
        data=benchmarks,
        message="Industry benchmarks for forecasting accuracy"
    )
