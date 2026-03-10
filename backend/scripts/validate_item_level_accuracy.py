"""
Validate Item-Level Forecast Accuracy

This script:
1. Trains restaurant-level model on training data
2. Calculates item mix from training period
3. Predicts item-level sales for validation/test periods
4. Compares with actual item sales
5. Reports MAPE by item

Usage:
    python scripts/validate_item_level_accuracy.py
    python scripts/validate_item_level_accuracy.py --top-n 20 --split test
"""

import pandas as pd
import numpy as np
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from xgboost import XGBRegressor
from scripts.ensemble_backtest import load_lexis_data, prepare_features, apply_holiday_adjustment

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_item_level_data(lexis_file: str) -> pd.DataFrame:
    """Load line-item level data (not aggregated)"""

    logger.info(f"Loading item-level data from: {lexis_file}")

    df = pd.read_excel(lexis_file, header=5)

    # Find columns
    date_col = [col for col in df.columns if 'date' in str(col).lower()][0]
    item_col = 'Item Name' if 'Item Name' in df.columns else \
               [col for col in df.columns if 'item' in str(col).lower()][0]
    qty_col = 'Qty.' if 'Qty.' in df.columns else \
              [col for col in df.columns if 'qty' in str(col).lower()][0]

    # Parse dates and quantities
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df[df[date_col].notna()].copy()
    df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)

    # Rename for consistency
    df = df.rename(columns={
        date_col: 'date',
        item_col: 'item_name',
        qty_col: 'qty'
    })

    logger.info(f"✓ Loaded {len(df):,} line items")
    logger.info(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    logger.info(f"  Unique items: {df['item_name'].nunique()}")

    return df[['date', 'item_name', 'qty']]


def calculate_item_mix_from_period(
    item_data: pd.DataFrame,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    """Calculate item mix percentages from a specific period"""

    period_data = item_data[
        (item_data['date'] >= start_date) &
        (item_data['date'] <= end_date)
    ].copy()

    item_totals = period_data.groupby('item_name')['qty'].sum().sort_values(ascending=False)
    total_qty = item_totals.sum()

    item_mix = pd.DataFrame({
        'item_name': item_totals.index,
        'total_qty': item_totals.values,
        'percentage': (item_totals.values / total_qty * 100)
    })

    logger.info(f"\nItem Mix ({start_date.date()} to {end_date.date()}):")
    logger.info(f"  Total items: {len(item_mix)}")
    logger.info(f"  Total qty: {total_qty:.0f}")
    logger.info(f"  Top 10 items: {item_mix.head(10)['percentage'].sum():.1f}% of sales")

    return item_mix


def get_actual_item_sales(
    item_data: pd.DataFrame,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    """Get actual daily sales by item for a period"""

    period_data = item_data[
        (item_data['date'] >= start_date) &
        (item_data['date'] <= end_date)
    ].copy()

    # Aggregate to daily by item
    daily_item = period_data.groupby(['date', 'item_name'])['qty'].sum().reset_index()

    return daily_item


def train_restaurant_model(daily_df: pd.DataFrame, train_end: datetime) -> Dict:
    """Train restaurant-level model on training period"""

    train_df = daily_df[daily_df['ds'] <= train_end].copy()

    feature_cols = [col for col in train_df.columns if col not in ['ds', 'y']]

    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
        verbosity=0
    )

    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['y']

    model.fit(X_train, y_train)

    logger.info(f"✓ Trained restaurant-level model on {len(train_df)} days")

    return {
        'model': model,
        'feature_cols': feature_cols
    }


def predict_item_level(
    model_dict: Dict,
    daily_df: pd.DataFrame,
    item_mix: pd.DataFrame,
    start_date: datetime,
    end_date: datetime,
    top_n: int = None
) -> pd.DataFrame:
    """Predict item-level sales using hierarchical allocation"""

    test_df = daily_df[
        (daily_df['ds'] >= start_date) &
        (daily_df['ds'] <= end_date)
    ].copy()

    model = model_dict['model']
    feature_cols = model_dict['feature_cols']

    # Predict restaurant-level totals
    X_test = test_df[feature_cols].fillna(0)
    predictions = model.predict(X_test)

    # Apply holiday adjustments
    adjusted_predictions, _ = apply_holiday_adjustment(predictions, test_df['ds'])

    # Allocate to items
    if top_n:
        top_items = item_mix.head(top_n)
        other_pct = 100 - top_items['percentage'].sum()
    else:
        top_items = item_mix
        other_pct = 0

    results = []

    for idx, (_, row) in enumerate(test_df.iterrows()):
        date = row['ds']
        total_pred = adjusted_predictions[idx]

        # Allocate to items
        for _, item in top_items.iterrows():
            item_pred = total_pred * item['percentage'] / 100
            results.append({
                'date': date,
                'item_name': item['item_name'],
                'predicted_qty': item_pred
            })

        # Add "Other" category if needed
        if other_pct > 0:
            other_pred = total_pred * other_pct / 100
            results.append({
                'date': date,
                'item_name': 'Other items',
                'predicted_qty': other_pred
            })

    return pd.DataFrame(results)


def calculate_item_mape(
    predicted: pd.DataFrame,
    actual: pd.DataFrame
) -> pd.DataFrame:
    """Calculate MAPE for each item"""

    # Merge predicted and actual
    merged = predicted.merge(
        actual,
        on=['date', 'item_name'],
        how='outer',
        suffixes=('_pred', '_actual')
    )

    merged['predicted_qty'] = merged['predicted_qty'].fillna(0)
    merged['qty'] = merged['qty'].fillna(0)

    # Calculate errors by item
    item_errors = []

    for item_name in merged['item_name'].unique():
        item_data = merged[merged['item_name'] == item_name].copy()

        y_true = item_data['qty'].values
        y_pred = item_data['predicted_qty'].values

        # Only calculate MAPE for days where item was sold
        mask = y_true > 0

        if mask.sum() == 0:
            continue

        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / (y_true[mask] + 1e-10))) * 100
        mae = np.mean(np.abs(y_true[mask] - y_pred[mask]))

        total_actual = y_true.sum()
        total_pred = y_pred.sum()

        item_errors.append({
            'item_name': item_name,
            'mape': mape,
            'mae': mae,
            'total_actual': total_actual,
            'total_pred': total_pred,
            'days_sold': mask.sum(),
            'total_days': len(item_data)
        })

    return pd.DataFrame(item_errors).sort_values('total_actual', ascending=False)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Validate item-level accuracy')
    parser.add_argument(
        '--split',
        type=str,
        default='test',
        choices=['val', 'test', 'both'],
        help='Which split to validate on'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=20,
        help='Number of top items to track individually'
    )
    parser.add_argument(
        '--lexis-file',
        type=str,
        default='/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx',
        help='Path to Lexis data file'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("ITEM-LEVEL ACCURACY VALIDATION")
    logger.info("="*80)

    # Define splits
    train_end = datetime(2025, 11, 30)
    val_start = datetime(2025, 12, 1)
    val_end = datetime(2025, 12, 14)
    test_start = datetime(2025, 12, 15)
    test_end = datetime(2025, 12, 31)

    # Load data
    logger.info("\n" + "="*80)
    logger.info("STEP 1: LOADING DATA")
    logger.info("="*80)

    # Load item-level data
    item_data = load_item_level_data(args.lexis_file)

    # Load aggregated daily data (for restaurant model)
    daily_data = load_lexis_data(args.lexis_file)
    daily_data = prepare_features(daily_data)

    # Calculate item mix from training period
    logger.info("\n" + "="*80)
    logger.info("STEP 2: CALCULATING ITEM MIX FROM TRAINING PERIOD")
    logger.info("="*80)

    item_mix = calculate_item_mix_from_period(
        item_data,
        datetime(2025, 10, 1),
        train_end
    )

    logger.info(f"\nTop {args.top_n} items:")
    for idx, row in item_mix.head(args.top_n).iterrows():
        logger.info(f"  {idx+1:2d}. {row['item_name']:50s} {row['percentage']:6.2f}%")

    # Train restaurant model
    logger.info("\n" + "="*80)
    logger.info("STEP 3: TRAINING RESTAURANT-LEVEL MODEL")
    logger.info("="*80)

    model_dict = train_restaurant_model(daily_data, train_end)

    # Validate on requested split(s)
    splits_to_validate = []

    if args.split in ['val', 'both']:
        splits_to_validate.append(('Validation', val_start, val_end))
    if args.split in ['test', 'both']:
        splits_to_validate.append(('Test', test_start, test_end))

    for split_name, start, end in splits_to_validate:
        logger.info("\n" + "="*80)
        logger.info(f"STEP 4: VALIDATING ON {split_name.upper()} SET ({start.date()} to {end.date()})")
        logger.info("="*80)

        # Get predictions
        logger.info(f"\nGenerating item-level predictions...")
        predicted = predict_item_level(
            model_dict,
            daily_data,
            item_mix,
            start,
            end,
            top_n=args.top_n
        )

        # Get actuals
        logger.info(f"Loading actual item sales...")
        actual = get_actual_item_sales(item_data, start, end)

        # Calculate MAPE
        logger.info(f"Calculating accuracy metrics...")
        item_metrics = calculate_item_mape(predicted, actual)

        # Display results
        logger.info(f"\n{'='*80}")
        logger.info(f"{split_name.upper()} SET RESULTS - ITEM-LEVEL ACCURACY")
        logger.info(f"{'='*80}\n")

        logger.info(f"{'Item':<50s} {'MAPE':<10s} {'MAE':<10s} {'Actual':<10s} {'Predicted':<10s} {'Days'}")
        logger.info("-" * 100)

        for idx, row in item_metrics.head(args.top_n).iterrows():
            logger.info(
                f"{row['item_name']:<50s} "
                f"{row['mape']:>6.1f}%    "
                f"{row['mae']:>6.1f}    "
                f"{row['total_actual']:>7.0f}    "
                f"{row['total_pred']:>7.0f}       "
                f"{row['days_sold']}/{row['total_days']}"
            )

        # Summary statistics
        logger.info(f"\n{'='*80}")
        logger.info(f"SUMMARY STATISTICS")
        logger.info(f"{'='*80}\n")

        # Weighted MAPE (by volume)
        total_actual = item_metrics['total_actual'].sum()
        weighted_mape = (item_metrics['mape'] * item_metrics['total_actual']).sum() / total_actual

        logger.info(f"Items tracked: {len(item_metrics)}")
        logger.info(f"Mean MAPE (unweighted): {item_metrics['mape'].mean():.2f}%")
        logger.info(f"Median MAPE: {item_metrics['mape'].median():.2f}%")
        logger.info(f"Weighted MAPE (by volume): {weighted_mape:.2f}%")
        logger.info(f"Best item MAPE: {item_metrics['mape'].min():.2f}% ({item_metrics.loc[item_metrics['mape'].idxmin(), 'item_name']})")
        logger.info(f"Worst item MAPE: {item_metrics['mape'].max():.2f}% ({item_metrics.loc[item_metrics['mape'].idxmax(), 'item_name']})")

        # Total accuracy
        total_pred = item_metrics['total_pred'].sum()
        total_mape = abs(total_actual - total_pred) / total_actual * 100

        logger.info(f"\nTotal volume accuracy:")
        logger.info(f"  Actual total: {total_actual:.0f} units")
        logger.info(f"  Predicted total: {total_pred:.0f} units")
        logger.info(f"  Total MAPE: {total_mape:.2f}%")

        logger.info(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
