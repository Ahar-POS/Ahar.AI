"""
Forecast API Routes

Endpoints for demand forecasting and related operations.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

from app.services.demand_forecaster import get_demand_forecaster
from app.utils.response import success_response, error_response

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate-all")
async def generate_all_forecasts(
    horizon_days: int = Query(7, ge=1, le=30, description="Forecast horizon in days"),
    use_cache: bool = Query(True, description="Use cached forecasts if available"),
    enhance_with_ai: bool = Query(True, description="Apply AI context enhancement")
):
    """
    Generate forecasts for all ingredients

    This is typically run once per week (or on-demand) to update all forecasts.
    Cached forecasts are stored for 24 hours.

    Args:
        horizon_days: Number of days to forecast (1-30)
        use_cache: Use cached forecasts if available
        enhance_with_ai: Apply AI context enhancement (weather + events)

    Returns:
        List of ingredient forecasts with predictions
    """
    try:
        forecaster = get_demand_forecaster()
        forecasts = await forecaster.forecast_all_ingredients(
            horizon_days=horizon_days,
            use_cache=use_cache,
            enhance_with_ai=enhance_with_ai
        )

        return success_response(
            data={
                "forecasts": forecasts,
                "total_ingredients": len(forecasts),
                "horizon_days": horizon_days,
                "ai_enhanced": enhance_with_ai
            },
            message=f"Generated {len(forecasts)} ingredient forecasts"
        )

    except Exception as e:
        logger.error(f"Forecast generation failed: {e}", exc_info=True)
        return error_response(
            code="FORECAST_GENERATION_FAILED",
            message="Failed to generate forecasts",
            details={"error": str(e)}
        )


@router.get("/ingredient/{material_id}")
async def get_ingredient_forecast(
    material_id: str,
    horizon_days: int = Query(7, ge=1, le=30, description="Forecast horizon in days"),
    use_cache: bool = Query(True, description="Use cached forecast if available"),
    enhance_with_ai: bool = Query(False, description="Apply AI context enhancement")
):
    """
    Get forecast for a specific ingredient

    Args:
        material_id: Raw material identifier (e.g., "RM001")
        horizon_days: Number of days to forecast
        use_cache: Use cached forecast if available
        enhance_with_ai: Apply AI context enhancement (slower, costs API tokens)

    Returns:
        Ingredient demand forecast with breakdown by menu item
    """
    try:
        forecaster = get_demand_forecaster()

        # Check cache first
        if use_cache:
            cached = await forecaster.get_cached_forecast(material_id)
            if cached:
                return success_response(
                    data=cached,
                    message="Retrieved cached forecast"
                )

        # Generate new forecast
        baseline = await forecaster.forecast_ingredient_demand(
            material_id,
            horizon_days
        )

        if enhance_with_ai:
            forecast = await forecaster.enhance_with_context(baseline)
        else:
            forecast = {
                **baseline,
                "final_forecast": baseline["predicted_consumption"]
            }

        # Cache result
        await forecaster.cache_forecast(forecast)

        return success_response(
            data=forecast,
            message="Generated ingredient forecast"
        )

    except Exception as e:
        logger.error(f"Ingredient forecast failed for {material_id}: {e}", exc_info=True)
        return error_response(
            code="INGREDIENT_FORECAST_FAILED",
            message=f"Failed to forecast ingredient {material_id}",
            details={"error": str(e)}
        )


@router.get("/menu-item/{menu_item_id}")
async def get_menu_item_forecast(
    menu_item_id: str,
    horizon_days: int = Query(7, ge=1, le=30, description="Forecast horizon in days")
):
    """
    Get forecast for a specific menu item

    Args:
        menu_item_id: Menu item identifier (e.g., "MENU001")
        horizon_days: Number of days to forecast

    Returns:
        Menu item demand forecast with daily predictions
    """
    try:
        forecaster = get_demand_forecaster()
        forecast = await forecaster.forecast_menu_item(menu_item_id, horizon_days)

        return success_response(
            data=forecast,
            message="Generated menu item forecast"
        )

    except Exception as e:
        logger.error(f"Menu item forecast failed for {menu_item_id}: {e}", exc_info=True)
        return error_response(
            code="MENU_ITEM_FORECAST_FAILED",
            message=f"Failed to forecast menu item {menu_item_id}",
            details={"error": str(e)}
        )


@router.get("/cache/status")
async def get_cache_status():
    """
    Get status of cached forecasts

    Returns:
        Statistics about cached forecasts
    """
    try:
        from app.core.database import get_database
        from datetime import datetime

        db = await get_database()
        collection = db["demand_forecasts"]

        # Count cached forecasts
        total = await collection.count_documents({})
        valid = await collection.count_documents({
            "expires_at": {"$gt": datetime.utcnow()}
        })
        expired = total - valid

        return success_response(
            data={
                "total_cached": total,
                "valid": valid,
                "expired": expired
            },
            message="Retrieved cache status"
        )

    except Exception as e:
        logger.error(f"Cache status check failed: {e}", exc_info=True)
        return error_response(
            code="CACHE_STATUS_FAILED",
            message="Failed to get cache status",
            details={"error": str(e)}
        )


@router.delete("/cache/clear")
async def clear_forecast_cache():
    """
    Clear all cached forecasts

    Useful for testing or forcing regeneration of all forecasts.

    Returns:
        Number of deleted cache entries
    """
    try:
        from app.core.database import get_database

        db = await get_database()
        collection = db["demand_forecasts"]

        result = await collection.delete_many({})

        return success_response(
            data={"deleted_count": result.deleted_count},
            message=f"Cleared {result.deleted_count} cached forecasts"
        )

    except Exception as e:
        logger.error(f"Cache clear failed: {e}", exc_info=True)
        return error_response(
            code="CACHE_CLEAR_FAILED",
            message="Failed to clear cache",
            details={"error": str(e)}
        )
