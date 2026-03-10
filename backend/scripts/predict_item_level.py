"""
Item-Level Demand Forecasting with Hierarchical Approach

This script:
1. Uses the restaurant-level model to predict total demand
2. Calculates historical item mix percentages
3. Allocates total forecast to individual items

Usage:
    python scripts/predict_item_level.py --days 7
    python scripts/predict_item_level.py --start-date 2026-03-15 --days 7 --output item_forecast.csv
"""

import pandas as pd
import numpy as np
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from scripts.train_and_save_model import load_model
from scripts.predict_with_saved_model import create_future_dates, prepare_prediction_features, predict_demand
from scripts.ensemble_backtest import load_lexis_data

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_item_mix(lexis_file: str, lookback_days: int = 30) -> pd.DataFrame:
    """
    Calculate average item mix percentages from historical data

    Args:
        lexis_file: Path to Lexis data file
        lookback_days: Number of recent days to use for mix calculation

    Returns:
        DataFrame with item mix percentages
    """
    logger.info(f"Calculating item mix from last {lookback_days} days...")

    # Load raw line item data
    df = pd.read_excel(lexis_file, header=5)

    # Find relevant columns
    date_col = [col for col in df.columns if 'date' in str(col).lower()][0]
    item_col = 'Item Name' if 'Item Name' in df.columns else \
               [col for col in df.columns if 'item' in str(col).lower()][0]
    qty_col = 'Qty.' if 'Qty.' in df.columns else \
              [col for col in df.columns if 'qty' in str(col).lower()][0]

    # Parse dates
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df[df[date_col].notna()].copy()

    # Filter to recent data
    cutoff_date = df[date_col].max() - pd.Timedelta(days=lookback_days)
    recent_df = df[df[date_col] >= cutoff_date].copy()

    # Calculate total quantity per item
    df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)

    item_totals = recent_df.groupby(item_col)[qty_col].sum().sort_values(ascending=False)
    total_qty = item_totals.sum()

    # Calculate percentages
    item_mix = pd.DataFrame({
        'item_name': item_totals.index,
        'total_qty': item_totals.values,
        'percentage': (item_totals.values / total_qty * 100).round(2)
    })

    logger.info(f"\nItem Mix (Top 20 items, {lookback_days} days):")
    logger.info("-" * 70)
    for idx, row in item_mix.head(20).iterrows():
        logger.info(f"  {row['item_name']:40s} {row['percentage']:6.2f}%  ({row['total_qty']:.0f} units)")

    logger.info(f"\nTotal items: {len(item_mix)}")
    logger.info(f"Top 10 items: {item_mix.head(10)['percentage'].sum():.1f}% of sales")
    logger.info(f"Top 20 items: {item_mix.head(20)['percentage'].sum():.1f}% of sales")

    return item_mix


def allocate_forecast_to_items(
    total_forecast: pd.DataFrame,
    item_mix: pd.DataFrame,
    top_n: int = 20
) -> pd.DataFrame:
    """
    Allocate total forecast to individual items

    Args:
        total_forecast: DataFrame with daily total predictions
        item_mix: DataFrame with item percentages
        top_n: Number of top items to forecast individually

    Returns:
        DataFrame with item-level forecasts
    """
    logger.info(f"\nAllocating forecasts to top {top_n} items...")

    results = []

    for _, day in total_forecast.iterrows():
        date = day['date']
        total_demand = day['predicted_demand']

        # Allocate to top N items
        top_items = item_mix.head(top_n)
        other_percentage = 100 - top_items['percentage'].sum()

        for _, item in top_items.iterrows():
            allocated_qty = round(total_demand * item['percentage'] / 100)

            results.append({
                'date': date,
                'day_of_week': day['day_of_week'],
                'item_name': item['item_name'],
                'predicted_qty': allocated_qty,
                'item_percentage': item['percentage']
            })

        # Add "Other items" category
        if other_percentage > 0:
            other_qty = round(total_demand * other_percentage / 100)
            results.append({
                'date': date,
                'day_of_week': day['day_of_week'],
                'item_name': 'Other items',
                'predicted_qty': other_qty,
                'item_percentage': other_percentage
            })

    item_forecast_df = pd.DataFrame(results)

    return item_forecast_df


def main():
    parser = argparse.ArgumentParser(description='Item-level demand forecasting')
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to forecast'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--lexis-file',
        type=str,
        default='/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx',
        help='Path to Lexis data file'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=20,
        help='Number of top items to forecast'
    )
    parser.add_argument(
        '--lookback-days',
        type=int,
        default=30,
        help='Days to use for calculating item mix'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output CSV file'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("ITEM-LEVEL DEMAND FORECASTING")
    logger.info("="*80)

    # Step 1: Load restaurant-level model
    logger.info("\nStep 1: Loading restaurant-level model...")
    model_dict = load_model('latest')
    logger.info(f"  Model version: {model_dict['metadata']['version']}")
    logger.info(f"  Training MAPE: {model_dict['metadata']['train_mape']:.2f}%")

    # Step 2: Calculate item mix
    logger.info("\nStep 2: Calculating historical item mix...")
    item_mix = calculate_item_mix(args.lexis_file, args.lookback_days)

    # Step 3: Generate total forecast
    logger.info("\nStep 3: Generating total demand forecast...")
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    else:
        start_date = datetime.now().date()

    future_df = create_future_dates(start_date, args.days)
    future_df = prepare_prediction_features(future_df, historical_df=None)
    total_forecast = predict_demand(model_dict, future_df)

    logger.info(f"  Total forecast: {total_forecast['predicted_demand'].sum():,} units over {args.days} days")

    # Step 4: Allocate to items
    logger.info("\nStep 4: Allocating to individual items...")
    item_forecast = allocate_forecast_to_items(total_forecast, item_mix, args.top_n)

    # Display results
    logger.info(f"\n{'='*80}")
    logger.info("ITEM-LEVEL FORECASTS")
    logger.info(f"{'='*80}\n")

    # Show first day as example
    first_day = item_forecast[item_forecast['date'] == item_forecast['date'].min()]

    logger.info(f"Example: {first_day['date'].iloc[0].strftime('%Y-%m-%d')} ({first_day['day_of_week'].iloc[0]})")
    logger.info("-" * 70)
    for _, item in first_day.iterrows():
        logger.info(f"  {item['item_name']:40s} {item['predicted_qty']:4d} units  ({item['item_percentage']:5.2f}%)")

    # Summary by item across all days
    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY BY ITEM ({args.days} days)")
    logger.info(f"{'='*80}\n")

    item_summary = item_forecast.groupby('item_name').agg({
        'predicted_qty': 'sum',
        'item_percentage': 'first'
    }).sort_values('predicted_qty', ascending=False)

    for item_name, row in item_summary.iterrows():
        avg_daily = row['predicted_qty'] / args.days
        logger.info(f"  {item_name:40s} {int(row['predicted_qty']):5d} units total  ({avg_daily:.1f}/day)")

    # Save to CSV
    if args.output:
        item_forecast.to_csv(args.output, index=False)
        logger.info(f"\n✓ Saved item-level forecasts to: {args.output}")

    logger.info(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
