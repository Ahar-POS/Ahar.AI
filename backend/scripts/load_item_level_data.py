"""
Item-Level Data Loader for Demand Forecasting

Loads line-item sales data from Lexis export and reshapes it to
[date, item_name, qty] format for item-level forecasting.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_item_level_data(
    lexis_file: str,
    fill_missing: bool = True
) -> pd.DataFrame:
    """
    Load line-item data from Lexis export

    Args:
        lexis_file: Path to Lexis Excel export file
        fill_missing: If True, fill missing day-item combinations with qty=0

    Returns:
        DataFrame with columns: [ds, item_name, qty]
        - One row per day-item combination
        - ds: date
        - item_name: string (menu item name)
        - qty: quantity sold (target variable)
    """
    logger.info(f"Loading item-level data from: {lexis_file}")

    # Try different header rows (Lexis exports vary)
    for header_row in [4, 5, 6]:
        try:
            df = pd.read_excel(lexis_file, header=header_row)

            # Find date column
            date_cols = [col for col in df.columns if 'date' in str(col).lower()]
            if not date_cols:
                continue

            date_col = date_cols[0]

            # Parse dates
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df[df[date_col].notna()].copy()

            # Skip header rows if they contain "Total"
            if len(df) > 0 and 'Total' in str(df.iloc[0].values):
                df = df.iloc[1:]

            # Find item and quantity columns
            if 'Item Name' not in df.columns:
                continue

            item_col = 'Item Name'
            qty_col = 'Qty.' if 'Qty.' in df.columns else [
                col for col in df.columns if 'qty' in str(col).lower()
            ][0]

            # Convert qty to numeric
            df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)

            # Filter to only rows with valid data
            df = df[df[item_col].notna()].copy()

            # Aggregate to daily by item
            logger.info(f"✓ Found {len(df):,} line items")
            logger.info(f"  Aggregating to daily by item...")

            daily_item = df.groupby([date_col, item_col])[qty_col].sum().reset_index()
            daily_item.columns = ['ds', 'item_name', 'qty']

            # Remove items with blank names or very low volume
            daily_item = daily_item[daily_item['item_name'].str.strip() != ''].copy()

            logger.info(f"✓ Aggregated to {len(daily_item):,} day-item records")
            logger.info(f"  Date range: {daily_item['ds'].min().date()} to {daily_item['ds'].max().date()}")
            logger.info(f"  Unique items: {daily_item['item_name'].nunique()}")

            # Fill missing day-item combinations with 0
            # (Important: if item not sold on a day, qty = 0, not missing)
            if fill_missing:
                logger.info("\n  Filling missing day-item combinations with qty=0...")

                all_dates = pd.date_range(
                    daily_item['ds'].min(),
                    daily_item['ds'].max(),
                    freq='D'
                )
                all_items = daily_item['item_name'].unique()

                full_grid = pd.MultiIndex.from_product(
                    [all_dates, all_items],
                    names=['ds', 'item_name']
                ).to_frame(index=False)

                daily_item_full = full_grid.merge(
                    daily_item,
                    on=['ds', 'item_name'],
                    how='left'
                )
                daily_item_full['qty'] = daily_item_full['qty'].fillna(0)

                n_days = len(all_dates)
                n_items = len(all_items)
                logger.info(f"  ✓ Created full grid: {n_days} days × {n_items} items = {len(daily_item_full):,} records")

                return daily_item_full

            return daily_item

        except Exception as e:
            logger.debug(f"Failed with header_row={header_row}: {e}")
            continue

    raise ValueError(f"Could not load item-level data from Excel file: {lexis_file}")


def get_item_stats(daily_item_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate per-item statistics

    Args:
        daily_item_df: DataFrame with [ds, item_name, qty]

    Returns:
        DataFrame with item statistics sorted by total volume
    """
    item_stats = daily_item_df.groupby('item_name').agg({
        'qty': ['sum', 'mean', 'std', 'count']
    }).reset_index()

    item_stats.columns = ['item_name', 'total_qty', 'avg_daily_qty', 'std_qty', 'n_days_sold']

    # Calculate days with non-zero sales
    non_zero_days = daily_item_df[daily_item_df['qty'] > 0].groupby('item_name').size()
    item_stats = item_stats.merge(
        non_zero_days.rename('n_days_nonzero'),
        left_on='item_name',
        right_index=True,
        how='left'
    )
    item_stats['n_days_nonzero'] = item_stats['n_days_nonzero'].fillna(0).astype(int)

    # Calculate sparsity (% of days with zero sales)
    total_days = daily_item_df.groupby('item_name').size().iloc[0]
    item_stats['sparsity_pct'] = (1 - item_stats['n_days_nonzero'] / total_days) * 100

    # Sort by total volume
    item_stats = item_stats.sort_values('total_qty', ascending=False)

    return item_stats


def main():
    """Example usage"""
    # Load data
    lexis_file = "/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx"

    daily_item = load_item_level_data(lexis_file)

    # Show summary statistics
    logger.info(f"\n{'='*80}")
    logger.info("ITEM-LEVEL DATA SUMMARY")
    logger.info(f"{'='*80}\n")

    logger.info(f"Total records: {len(daily_item):,}")
    logger.info(f"Date range: {daily_item['ds'].min().date()} to {daily_item['ds'].max().date()}")
    logger.info(f"Unique items: {daily_item['item_name'].nunique()}")
    logger.info(f"Unique dates: {daily_item['ds'].nunique()}")

    # Item statistics
    item_stats = get_item_stats(daily_item)

    logger.info(f"\n{'='*80}")
    logger.info("TOP 20 ITEMS BY VOLUME")
    logger.info(f"{'='*80}\n")

    logger.info(f"{'Item Name':<45s} {'Total':>8s} {'Avg/Day':>8s} {'Sold Days':>10s} {'Sparsity':>9s}")
    logger.info("-" * 90)

    for idx, row in item_stats.head(20).iterrows():
        logger.info(
            f"{row['item_name'][:45]:<45s} "
            f"{row['total_qty']:>8.0f} "
            f"{row['avg_daily_qty']:>8.1f} "
            f"{row['n_days_nonzero']:>10.0f} "
            f"{row['sparsity_pct']:>8.1f}%"
        )

    # Sample data
    logger.info(f"\n{'='*80}")
    logger.info("SAMPLE RECORDS (first 10)")
    logger.info(f"{'='*80}\n")
    print(daily_item.head(10).to_string(index=False))

    logger.info(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
