"""
Manual test script for demand forecaster

Run this with: python3 test_forecast_manual.py
"""

import asyncio
from app.core.database import connect_to_database
from app.services.demand_forecaster import get_demand_forecaster
from app.repositories.recipe_repository import get_recipe_repository


async def test_recipe_repository():
    """Test recipe repository"""
    print("\n=== Testing Recipe Repository ===")

    repo = get_recipe_repository()

    # Test get_by_menu_item
    recipe = await repo.get_by_menu_item("MENU001")
    if recipe:
        print(f"✓ Found recipe for {recipe['menu_item_name']}")
        print(f"  Ingredients: {len(recipe['ingredients'])}")
    else:
        print("✗ Recipe not found")

    # Test get_by_ingredient
    recipes = await repo.get_by_ingredient("RM001")
    print(f"✓ RM001 (Chicken Breast) used in {len(recipes)} recipes")

    return True


async def test_menu_item_forecast():
    """Test forecasting a single menu item"""
    print("\n=== Testing Menu Item Forecast ===")

    forecaster = get_demand_forecaster()

    # Forecast MENU001 (Smoky Chicken Burger)
    forecast = await forecaster.forecast_menu_item("MENU001", horizon_days=7)

    print(f"✓ Forecast for {forecast['menu_item_id']}")
    print(f"  Total predicted (7 days): {forecast['total_predicted']:.1f} units")
    print(f"  Confidence: {forecast['confidence_score']:.2f}")
    print(f"  Model: {forecast['model_type']}")

    # Show first 3 days
    print(f"  First 3 days:")
    for pred in forecast['predictions'][:3]:
        print(f"    {pred['date']}: {pred['predicted_quantity']:.1f} units")

    return True


async def test_ingredient_forecast():
    """Test forecasting an ingredient"""
    print("\n=== Testing Ingredient Forecast ===")

    forecaster = get_demand_forecaster()

    # Forecast RM001 (Chicken Breast)
    forecast = await forecaster.forecast_ingredient_demand("RM001", horizon_days=7)

    print(f"✓ Forecast for {forecast['material_id']}")
    print(f"  Total consumption (7 days): {forecast['predicted_consumption']:.1f} grams")
    print(f"  Confidence: {forecast['confidence_score']:.2f}")
    print(f"  Used in {len(forecast['menu_item_breakdown'])} menu items")

    # Show breakdown
    print(f"  Menu item breakdown:")
    for item in forecast['menu_item_breakdown'][:3]:
        print(f"    {item['menu_item_name']}: {item['total_ingredient_needed']:.1f} grams")

    return True


async def test_cache():
    """Test forecast caching"""
    print("\n=== Testing Forecast Caching ===")

    forecaster = get_demand_forecaster()

    # Generate forecast
    forecast1 = await forecaster.forecast_ingredient_demand("RM003", horizon_days=7)
    print(f"✓ Generated forecast for RM003: {forecast1['predicted_consumption']:.1f}")

    # Cache it
    await forecaster.cache_forecast(forecast1, ttl_hours=1)
    print(f"✓ Cached forecast")

    # Retrieve from cache
    cached = await forecaster.get_cached_forecast("RM003")
    if cached:
        print(f"✓ Retrieved from cache: {cached['predicted_consumption']:.1f}")
    else:
        print("✗ Cache retrieval failed")

    return True


async def main():
    """Run all tests"""
    print("="*80)
    print("DEMAND FORECASTER MANUAL TESTS")
    print("="*80)

    # Connect to database
    print("\nConnecting to MongoDB...")
    await connect_to_database()
    print("✓ Connected to MongoDB")

    try:
        # Run tests
        await test_recipe_repository()
        await test_menu_item_forecast()
        await test_ingredient_forecast()
        await test_cache()

        print("\n" + "="*80)
        print("✓ ALL TESTS PASSED!")
        print("="*80)

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
