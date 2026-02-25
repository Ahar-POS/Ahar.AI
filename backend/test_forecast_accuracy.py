"""
Test Script: Forecast Accuracy Validation

This script demonstrates how to test the forecasting accuracy of your
demand prediction model using backtesting.

Usage:
    python test_forecast_accuracy.py
"""

import asyncio
import sys
from app.services.forecast_validator import get_forecast_validator
from app.core.database import connect_to_database, close_database_connection


async def main():
    """Run forecast accuracy tests"""
    print("=" * 70)
    print("DEMAND FORECASTING ACCURACY TEST")
    print("=" * 70)
    print()

    # Connect to database
    print("📊 Connecting to database...")
    await connect_to_database()
    print("✓ Connected\n")

    validator = get_forecast_validator()

    # Test 1: Backtest menu items
    print("=" * 70)
    print("TEST 1: Menu Item Forecasting Accuracy")
    print("=" * 70)
    print()
    print("Running backtest with:")
    print("  - Training period: 60 days of historical data")
    print("  - Test period: 7 days forecast")
    print("  - Method: Walk-forward validation")
    print()

    try:
        results = await validator.backtest_menu_items(
            lookback_days=60,
            test_days=7,
            menu_item_ids=None  # Test all items
        )

        # Generate and print report
        report = validator.generate_accuracy_report(results)
        print(report)

        # Show top 3 best predictions
        print("\n" + "=" * 70)
        print("TOP 3 BEST PREDICTIONS (by MAPE):")
        print("=" * 70)
        print()

        items_with_metrics = [
            (item_id, data)
            for item_id, data in results["items"].items()
            if "error" not in data
        ]

        sorted_items = sorted(
            items_with_metrics,
            key=lambda x: x[1]["metrics"]["mape"]
        )[:3]

        for rank, (item_id, data) in enumerate(sorted_items, 1):
            metrics = data["metrics"]
            print(f"{rank}. {item_id}")
            print(f"   MAE: {metrics['mae']:.2f} units")
            print(f"   MAPE: {metrics['mape']:.1f}%")
            print(f"   Hit Rate: {metrics['hit_rate']:.1f}%")
            print()

    except Exception as e:
        print(f"❌ Menu item backtest failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Validate ingredient forecasts
    print("\n" + "=" * 70)
    print("TEST 2: Ingredient Forecasting Accuracy")
    print("=" * 70)
    print()
    print("Validating ingredient-level forecasts...")
    print("(Comparing predicted consumption vs actual from orders)")
    print()

    try:
        ingredient_results = await validator.validate_ingredient_forecasts(
            test_days=7
        )

        # Show results
        valid_results = [
            (material_id, data)
            for material_id, data in ingredient_results.items()
            if "error" not in data
        ]

        if valid_results:
            avg_error = sum(abs(r["percentage_error"]) for _, r in valid_results) / len(valid_results)
            within_20 = sum(1 for _, r in valid_results if abs(r["percentage_error"]) <= 20)
            within_30 = sum(1 for _, r in valid_results if abs(r["percentage_error"]) <= 30)

            print(f"Ingredients tested: {len(valid_results)}")
            print(f"Average error: {avg_error:.1f}%")
            print(f"Within 20% accuracy: {within_20}/{len(valid_results)} ({within_20/len(valid_results)*100:.1f}%)")
            print(f"Within 30% accuracy: {within_30}/{len(valid_results)} ({within_30/len(valid_results)*100:.1f}%)")
            print()

            # Show worst 5 predictions
            print("WORST 5 INGREDIENT PREDICTIONS:")
            print()

            sorted_ingredients = sorted(
                valid_results,
                key=lambda x: abs(x[1]["percentage_error"]),
                reverse=True
            )[:5]

            for material_id, data in sorted_ingredients:
                print(f"  {data['material_name']} ({material_id}):")
                print(f"    Actual: {data['actual_consumption']:.1f}")
                print(f"    Predicted: {data['predicted_consumption']:.1f}")
                print(f"    Error: {data['percentage_error']:+.1f}%")
                print()

        else:
            print("❌ No valid ingredient results")

    except Exception as e:
        print(f"❌ Ingredient validation failed: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    print("\n" + "=" * 70)
    print("Closing database connection...")
    await close_database_connection()
    print("✓ Tests complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
