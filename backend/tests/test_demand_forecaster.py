"""
Tests for Demand Forecaster Service

Tests the 3-layer forecasting architecture:
- Layer 1: Prophet statistical forecasting
- Layer 2: Menu-to-ingredient mapping
- Layer 3: AI context enhancement
"""

import pytest
from datetime import datetime, timedelta
import pandas as pd

from app.services.demand_forecaster import get_demand_forecaster
from app.repositories.recipe_repository import get_recipe_repository


@pytest.mark.asyncio
class TestDemandForecaster:
    """Test demand forecasting system"""

    @pytest.fixture
    async def forecaster(self):
        """Get demand forecaster instance"""
        return get_demand_forecaster()

    @pytest.fixture
    async def recipe_repo(self):
        """Get recipe repository instance"""
        return get_recipe_repository()

    # ========== Layer 1: Statistical Baseline Tests ==========

    async def test_forecast_menu_item_with_data(self, forecaster):
        """Test menu item forecasting with actual historical data"""
        # Use MENU001 (Smoky Chicken Burger) - should have historical orders
        forecast = await forecaster.forecast_menu_item("MENU001", horizon_days=7)

        # Verify structure
        assert forecast["menu_item_id"] == "MENU001"
        assert forecast["horizon_days"] == 7
        assert "predictions" in forecast
        assert len(forecast["predictions"]) == 7

        # Verify predictions have required fields
        for pred in forecast["predictions"]:
            assert "date" in pred
            assert "predicted_quantity" in pred
            assert "lower_bound" in pred
            assert "upper_bound" in pred
            assert pred["predicted_quantity"] >= 0  # Non-negative

        # Verify confidence score
        assert 0.0 <= forecast["confidence_score"] <= 1.0

        print(f"\n✓ Menu item forecast:")
        print(f"  Total predicted: {forecast['total_predicted']:.1f}")
        print(f"  Confidence: {forecast['confidence_score']:.2f}")
        print(f"  Model: {forecast['model_type']}")

    async def test_forecast_menu_item_no_data(self, forecaster):
        """Test fallback forecast for menu item with no historical data"""
        # Use a non-existent menu item
        forecast = await forecaster.forecast_menu_item("MENU999", horizon_days=7)

        # Should return fallback forecast
        assert forecast["menu_item_id"] == "MENU999"
        assert forecast["model_type"] == "fallback"
        assert forecast["confidence_score"] < 0.5  # Low confidence

        print(f"\n✓ Fallback forecast:")
        print(f"  Total predicted: {forecast['total_predicted']:.1f}")
        print(f"  Confidence: {forecast['confidence_score']:.2f}")

    async def test_forecast_confidence_calculation(self, forecaster):
        """Test confidence score calculation logic"""
        import numpy as np

        # Narrow interval = high confidence
        lower = np.array([8.0, 9.0, 10.0])
        pred = np.array([10.0, 10.0, 10.0])
        upper = np.array([12.0, 11.0, 10.0])

        confidence = forecaster._calculate_forecast_confidence(lower, pred, upper)
        assert confidence > 0.7  # Should be high confidence

        # Wide interval = low confidence
        lower = np.array([1.0, 2.0, 3.0])
        pred = np.array([10.0, 10.0, 10.0])
        upper = np.array([20.0, 18.0, 17.0])

        confidence = forecaster._calculate_forecast_confidence(lower, pred, upper)
        assert confidence < 0.6  # Should be lower confidence

        print(f"\n✓ Confidence calculation working correctly")

    # ========== Layer 2: Ingredient Mapping Tests ==========

    async def test_forecast_ingredient_demand(self, forecaster):
        """Test ingredient demand forecasting with aggregation"""
        # Use RM001 (Chicken Breast) - used in multiple menu items
        forecast = await forecaster.forecast_ingredient_demand("RM001", horizon_days=7)

        # Verify structure
        assert forecast["material_id"] == "RM001"
        assert forecast["horizon_days"] == 7
        assert forecast["predicted_consumption"] >= 0

        # Verify menu item breakdown
        assert "menu_item_breakdown" in forecast
        assert len(forecast["menu_item_breakdown"]) > 0

        # Check breakdown details
        total_from_breakdown = sum(
            item["total_ingredient_needed"]
            for item in forecast["menu_item_breakdown"]
        )

        # Should match predicted consumption (within rounding)
        assert abs(total_from_breakdown - forecast["predicted_consumption"]) < 1.0

        print(f"\n✓ Ingredient forecast:")
        print(f"  Material: {forecast['material_id']}")
        print(f"  Total consumption: {forecast['predicted_consumption']:.1f}")
        print(f"  Used in {len(forecast['menu_item_breakdown'])} menu items")
        print(f"  Confidence: {forecast['confidence_score']:.2f}")

    async def test_ingredient_no_recipes(self, forecaster):
        """Test ingredient with no recipes"""
        # Use a non-existent material ID
        forecast = await forecaster.forecast_ingredient_demand("RM999", horizon_days=7)

        # Should return zero consumption
        assert forecast["material_id"] == "RM999"
        assert forecast["predicted_consumption"] == 0
        assert forecast["model_type"] == "no_recipes"

        print(f"\n✓ No recipes forecast: consumption = 0")

    async def test_daily_breakdown(self, forecaster):
        """Test daily breakdown in ingredient forecast"""
        forecast = await forecaster.forecast_ingredient_demand("RM003", horizon_days=7)

        # Verify daily breakdown
        assert "daily_breakdown" in forecast
        assert len(forecast["daily_breakdown"]) == 7

        # Check each day
        for day in forecast["daily_breakdown"]:
            assert "date" in day
            assert "predicted" in day
            assert "lower" in day
            assert "upper" in day
            assert day["predicted"] >= 0
            assert day["lower"] <= day["predicted"] <= day["upper"]

        print(f"\n✓ Daily breakdown:")
        for i, day in enumerate(forecast["daily_breakdown"][:3], 1):
            print(f"  Day {i}: {day['predicted']:.1f} units")

    # ========== Recipe Repository Tests ==========

    async def test_get_recipe_by_menu_item(self, recipe_repo):
        """Test fetching recipe by menu item ID"""
        recipe = await recipe_repo.get_by_menu_item("MENU001")

        assert recipe is not None
        assert recipe["menu_item_id"] == "MENU001"
        assert "ingredients" in recipe
        assert len(recipe["ingredients"]) > 0

        # Check ingredient structure
        ingredient = recipe["ingredients"][0]
        assert "material_id" in ingredient
        assert "quantity_per_serving" in ingredient
        assert "unit" in ingredient

        print(f"\n✓ Recipe for {recipe['menu_item_name']}:")
        print(f"  {len(recipe['ingredients'])} ingredients")

    async def test_get_recipes_by_ingredient(self, recipe_repo):
        """Test fetching all recipes using an ingredient"""
        recipes = await recipe_repo.get_by_ingredient("RM001")

        assert len(recipes) > 0

        # All recipes should contain RM001
        for recipe in recipes:
            ingredient_ids = [ing["material_id"] for ing in recipe["ingredients"]]
            assert "RM001" in ingredient_ids

        print(f"\n✓ RM001 (Chicken Breast) used in {len(recipes)} recipes")

    async def test_ingredient_usage_map(self, recipe_repo):
        """Test building complete ingredient usage map"""
        usage_map = await recipe_repo.get_ingredient_usage_map()

        assert len(usage_map) > 0

        # Check structure
        for material_id, usages in usage_map.items():
            assert material_id.startswith("RM")
            assert len(usages) > 0

            # Check usage structure
            for usage in usages:
                assert "menu_item_id" in usage
                assert "quantity_per_serving" in usage
                assert "unit" in usage

        print(f"\n✓ Usage map: {len(usage_map)} ingredients tracked")

    # ========== Caching Tests ==========

    async def test_forecast_caching(self, forecaster):
        """Test forecast caching and retrieval"""
        material_id = "RM005"

        # Clear any existing cache
        from app.core.database import get_database
        db = await get_database()
        await db.demand_forecasts.delete_many({"material_id": material_id})

        # Generate forecast
        forecast1 = await forecaster.forecast_ingredient_demand(material_id, horizon_days=7)

        # Cache it
        await forecaster.cache_forecast(forecast1, ttl_hours=1)

        # Retrieve from cache
        cached = await forecaster.get_cached_forecast(material_id)

        assert cached is not None
        assert cached["material_id"] == material_id
        assert cached["predicted_consumption"] == forecast1["predicted_consumption"]

        print(f"\n✓ Caching working: forecast cached and retrieved")

    async def test_cache_expiration(self, forecaster):
        """Test that expired forecasts are not returned"""
        material_id = "RM006"

        # Clear any existing cache
        from app.core.database import get_database
        db = await get_database()
        await db.demand_forecasts.delete_many({"material_id": material_id})

        # Generate forecast
        forecast = await forecaster.forecast_ingredient_demand(material_id, horizon_days=7)

        # Cache with very short TTL (simulate expiration)
        forecast_doc = {
            **forecast,
            "cached_at": datetime.utcnow() - timedelta(hours=25),  # 25 hours ago
            "expires_at": datetime.utcnow() - timedelta(hours=1)   # Expired 1 hour ago
        }
        await db.demand_forecasts.insert_one(forecast_doc)

        # Try to retrieve - should return None
        cached = await forecaster.get_cached_forecast(material_id)
        assert cached is None

        print(f"\n✓ Cache expiration working: expired forecast not returned")

    # ========== Integration Tests ==========

    @pytest.mark.slow
    async def test_forecast_all_ingredients(self, forecaster):
        """Test forecasting all ingredients (integration test)"""
        # This is a slower test as it forecasts all ingredients
        forecasts = await forecaster.forecast_all_ingredients(
            horizon_days=7,
            use_cache=False,
            enhance_with_ai=False  # Skip AI for faster testing
        )

        assert len(forecasts) > 0

        # Verify all forecasts have required structure
        for forecast in forecasts:
            assert "material_id" in forecast
            assert "predicted_consumption" in forecast
            assert "confidence_score" in forecast
            assert forecast["predicted_consumption"] >= 0

        print(f"\n✓ Forecasted {len(forecasts)} ingredients")

        # Show top 5 by consumption
        sorted_forecasts = sorted(
            forecasts,
            key=lambda f: f["predicted_consumption"],
            reverse=True
        )
        print(f"  Top 5 by consumption:")
        for forecast in sorted_forecasts[:5]:
            print(f"    {forecast['material_id']}: {forecast['predicted_consumption']:.1f}")

    # ========== Error Handling Tests ==========

    async def test_prophet_failure_fallback(self, forecaster):
        """Test that fallback works when Prophet fails"""
        # Create a scenario that might cause Prophet to fail
        # (e.g., insufficient data - already tested above)

        forecast = await forecaster.forecast_menu_item("MENU_NEW", horizon_days=7)

        # Should use fallback instead of crashing
        assert forecast["model_type"] == "fallback"
        assert "predictions" in forecast
        assert len(forecast["predictions"]) == 7

        print(f"\n✓ Fallback mechanism working on Prophet failure")


# Run tests with: pytest tests/test_demand_forecaster.py -v
# Run with output: pytest tests/test_demand_forecaster.py -v -s
# Run specific test: pytest tests/test_demand_forecaster.py::TestDemandForecaster::test_forecast_menu_item_with_data -v -s
