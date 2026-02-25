"""
Simple Forecast Accuracy Test (Without Prophet)

Tests forecasting accuracy using simple moving average as baseline.
This bypasses Prophet library issues and gives you immediate results.
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.core.database import connect_to_database, close_database_connection, get_database


async def simple_forecast_test():
    """Run simple moving average forecast and measure accuracy"""

    print("=" * 70)
    print("SIMPLE FORECAST ACCURACY TEST")
    print("(Using Moving Average - No Prophet Required)")
    print("=" * 70)
    print()

    # Connect to database
    print("📊 Connecting to database...")
    await connect_to_database()
    db = get_database()
    print("✓ Connected\n")

    # Test parameters
    training_days = 60  # Use 60 days for training
    test_days = 7       # Test on 7 days
    window_size = 7     # 7-day moving average

    # Use Jan 28, 2026 as the latest date (based on actual data)
    test_end_date = datetime(2026, 1, 28)
    test_start_date = test_end_date - timedelta(days=test_days)
    training_end_date = test_start_date
    training_start_date = training_end_date - timedelta(days=training_days)

    print(f"Training period: {training_start_date.date()} to {training_end_date.date()}")
    print(f"Test period: {test_start_date.date()} to {test_end_date.date()}")
    print(f"Method: {window_size}-day moving average")
    print()

    # Get all menu items
    menu_items = await db.menu_items.find({}).to_list(length=None)
    print(f"Testing {len(menu_items)} menu items...")
    print()

    all_results = []

    for item in menu_items[:10]:  # Test first 10 items for speed
        menu_item_id = item["menu_item_id"]

        try:
            # Get training data
            train_pipeline = [
                {
                    "$match": {
                        "order_date": {
                            "$gte": training_start_date,
                            "$lt": training_end_date
                        },
                        "status": {"$ne": "cancelled"}
                    }
                },
                {"$unwind": "$items"},
                {"$match": {"items.menu_item_id": menu_item_id}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$order_date"
                            }
                        },
                        "quantity": {"$sum": "$items.quantity"}
                    }
                },
                {"$sort": {"_id": 1}}
            ]

            cursor = db.orders.aggregate(train_pipeline)
            train_data = await cursor.to_list(length=None)

            if len(train_data) < window_size:
                continue  # Skip items with insufficient data

            # Calculate moving average
            quantities = [d["quantity"] for d in train_data]
            moving_avg = np.mean(quantities[-window_size:])  # Last 7 days average

            # Predict: Use moving average for each of next 7 days
            predictions = [moving_avg] * test_days

            # Get actual test data
            test_pipeline = [
                {
                    "$match": {
                        "order_date": {
                            "$gte": test_start_date,
                            "$lte": test_end_date
                        },
                        "status": {"$ne": "cancelled"}
                    }
                },
                {"$unwind": "$items"},
                {"$match": {"items.menu_item_id": menu_item_id}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$order_date"
                            }
                        },
                        "quantity": {"$sum": "$items.quantity"}
                    }
                },
                {"$sort": {"_id": 1}}
            ]

            cursor = db.orders.aggregate(test_pipeline)
            test_data = await cursor.to_list(length=None)

            # Create date-indexed actuals (fill missing with 0)
            # Use periods=test_days to ensure exact number of days
            date_range = pd.date_range(start=test_start_date, periods=test_days, freq="D")
            test_dict = {
                pd.to_datetime(d["_id"]): d["quantity"]
                for d in test_data
            }
            actuals = [test_dict.get(date, 0.0) for date in date_range]

            # Calculate metrics
            actuals_arr = np.array(actuals)
            predictions_arr = np.array(predictions)

            errors = predictions_arr - actuals_arr
            abs_errors = np.abs(errors)

            mae = float(np.mean(abs_errors))
            rmse = float(np.sqrt(np.mean(errors ** 2)))

            # MAPE (avoid division by zero)
            non_zero_mask = actuals_arr != 0
            if np.any(non_zero_mask):
                mape = float(
                    np.mean(np.abs(errors[non_zero_mask] / actuals_arr[non_zero_mask])) * 100
                )
            else:
                mape = float('inf')

            bias = float(np.mean(errors))

            # Hit rate (within 20%)
            threshold = 0.20
            within_threshold = np.sum(
                abs_errors <= threshold * (actuals_arr + 1)  # +1 to avoid zero division
            )
            hit_rate = float(within_threshold / len(actuals_arr) * 100)

            all_results.append({
                "menu_item_id": menu_item_id,
                "menu_item_name": item.get("name", menu_item_id),
                "training_avg": float(moving_avg),
                "actual_avg": float(np.mean(actuals_arr)),
                "mae": mae,
                "rmse": rmse,
                "mape": mape,
                "bias": bias,
                "hit_rate": hit_rate
            })

            print(f"✓ {menu_item_id}: MAPE={mape:.1f}%, MAE={mae:.2f}, Bias={bias:+.2f}")

        except Exception as e:
            print(f"✗ {menu_item_id}: {e}")

    # Calculate aggregate metrics
    print()
    print("=" * 70)
    print("AGGREGATE RESULTS")
    print("=" * 70)
    print()

    if all_results:
        avg_mae = np.mean([r["mae"] for r in all_results])
        avg_rmse = np.mean([r["rmse"] for r in all_results])
        avg_mape = np.mean([r["mape"] for r in all_results if r["mape"] != float('inf')])
        avg_bias = np.mean([r["bias"] for r in all_results])
        avg_hit_rate = np.mean([r["hit_rate"] for r in all_results])

        print(f"Items tested: {len(all_results)}")
        print()
        print(f"MAE (Mean Absolute Error):        {avg_mae:.2f} units")
        print(f"RMSE (Root Mean Squared Error):   {avg_rmse:.2f} units")
        print(f"MAPE (Mean Absolute % Error):     {avg_mape:.1f}%")
        print(f"Bias (Over/Under forecasting):    {avg_bias:+.2f} units")
        print(f"Hit Rate (within 20%):            {avg_hit_rate:.1f}%")
        print()

        # Interpretation
        print("INTERPRETATION:")
        print()

        if avg_mape < 15:
            print("  ✅ EXCELLENT: MAPE < 15% - Very accurate forecasts")
        elif avg_mape < 25:
            print("  ✓ GOOD: MAPE 15-25% - Acceptable for inventory planning")
        elif avg_mape < 40:
            print("  ⚠ FAIR: MAPE 25-40% - Needs improvement")
        else:
            print("  ❌ POOR: MAPE > 40% - Significant forecast error")

        if abs(avg_bias) < 2:
            print("  ✅ Minimal bias - Balanced forecasts")
        elif avg_bias > 2:
            print(f"  ⚠ Over-forecasting by {avg_bias:.1f} units - May lead to waste")
        else:
            print(f"  ⚠ Under-forecasting by {abs(avg_bias):.1f} units - Risk of stockouts")

        if avg_hit_rate > 70:
            print(f"  ✅ High hit rate ({avg_hit_rate:.0f}%) - Reliable predictions")
        else:
            print(f"  ⚠ Low hit rate ({avg_hit_rate:.0f}%) - High variability")

        print()
        print("=" * 70)
        print()
        print("NOTE: This is a simple moving average baseline.")
        print("Prophet (when fixed) typically achieves 5-10% better MAPE.")
        print()

        # Show best and worst
        sorted_results = sorted(all_results, key=lambda x: x["mape"] if x["mape"] != float('inf') else 999)

        print("TOP 3 BEST PREDICTIONS:")
        for i, r in enumerate(sorted_results[:3], 1):
            print(f"  {i}. {r['menu_item_name']}: MAPE={r['mape']:.1f}%, MAE={r['mae']:.2f}")

        print()
        print("TOP 3 WORST PREDICTIONS:")
        for i, r in enumerate(sorted_results[-3:][::-1], 1):
            mape_str = f"{r['mape']:.1f}%" if r['mape'] != float('inf') else "N/A (no sales)"
            print(f"  {i}. {r['menu_item_name']}: MAPE={mape_str}, MAE={r['mae']:.2f}")

    else:
        print("❌ No results - insufficient data for testing")

    print()
    print("=" * 70)

    # Cleanup
    await close_database_connection()
    print("✓ Test complete")


if __name__ == "__main__":
    asyncio.run(simple_forecast_test())
