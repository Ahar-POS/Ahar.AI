"""
Item-Level Direct Predictions

Generates item-level demand predictions using trained XGBoost model.
"""

import pandas as pd
import numpy as np
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import warnings

warnings.filterwarnings('ignore')

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from train_item_level_model import load_item_level_model
from ensemble_backtest import prepare_features_item_level

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def predict_item_level_direct(
    start_date: datetime,
    days: int = 7,
    version: str = 'latest',
    output: Optional[str] = None,
    lexis_file: Optional[str] = None
) -> pd.DataFrame:
    """
    Direct item-level predictions using trained XGBoost

    Args:
        start_date: Start date for predictions
        days: Number of days to forecast
        version: Model version to load
        output: Optional CSV output path
        lexis_file: Optional path to Lexis file (for loading recent data for lag features)

    Returns:
        DataFrame with columns: [date, item_name, predicted_qty]
    """
    logger.info("="*80)
    logger.info("ITEM-LEVEL PREDICTIONS (DIRECT)")
    logger.info("="*80)

    # ========================================================================
    # STEP 1: Load model
    # ========================================================================
    logger.info(f"\nStep 1: Loading model...")
    model_dict = load_item_level_model(version)

    model = model_dict['model']
    encoder = model_dict['encoder']
    feature_cols = model_dict['feature_cols']

    logger.info(f"  Model version: {model_dict['metadata']['version']}")
    logger.info(f"  Test MAPE: {model_dict['metadata']['test_mape']:.2f}%")
    logger.info(f"  Weighted MAPE: {model_dict['metadata']['weighted_mape']:.2f}%")

    # ========================================================================
    # STEP 2: Create future dates × items grid
    # ========================================================================
    logger.info(f"\nStep 2: Creating prediction grid...")

    future_dates = pd.date_range(start_date, periods=days, freq='D')
    items = list(encoder.item_means_.keys())  # All items from training

    future_grid = pd.MultiIndex.from_product(
        [future_dates, items],
        names=['ds', 'item_name']
    ).to_frame(index=False)

    # Add dummy quantity column (will be replaced with predictions)
    future_grid['qty'] = 0

    logger.info(f"  Prediction period: {future_dates[0].date()} to {future_dates[-1].date()}")
    logger.info(f"  Items: {len(items)}")
    logger.info(f"  Total predictions: {len(future_grid):,}")

    # ========================================================================
    # STEP 3: Load historical data for lag features (if available)
    # ========================================================================
    if lexis_file:
        logger.info(f"\nStep 3: Loading historical data for lag features...")
        try:
            from load_item_level_data import load_item_level_data

            # Load full history
            historical = load_item_level_data(lexis_file)

            # Filter to dates before prediction start
            historical = historical[historical['ds'] < start_date].copy()

            logger.info(f"  Loaded {len(historical):,} historical records")
            logger.info(f"  Date range: {historical['ds'].min().date()} to {historical['ds'].max().date()}")

            # Combine historical + future
            combined = pd.concat([historical, future_grid], ignore_index=True)
            combined = combined.sort_values(['item_name', 'ds']).reset_index(drop=True)

        except Exception as e:
            logger.warning(f"  Could not load historical data: {e}")
            logger.warning(f"  Lag features will be initialized with item means")
            combined = future_grid.copy()
    else:
        logger.info(f"\nStep 3: No historical data provided (lag features will use item means)")
        combined = future_grid.copy()

    # ========================================================================
    # STEP 4: Prepare features
    # ========================================================================
    logger.info(f"\nStep 4: Preparing features...")

    # Use encoder without fitting
    future_df, _ = prepare_features_item_level(
        combined,
        encoder=encoder,
        fit_encoder=False,
        clip_outliers=False
    )

    # Filter to only future dates
    future_df = future_df[future_df['ds'] >= start_date].copy()

    logger.info(f"  ✓ Prepared {len(future_df):,} records with {len(feature_cols)} features")

    # ========================================================================
    # STEP 5: Predict
    # ========================================================================
    logger.info(f"\nStep 5: Generating predictions...")

    X_future = future_df[feature_cols].fillna(0)
    predictions = model.predict(X_future)

    # Clip negative predictions to 0
    predictions = np.maximum(predictions, 0)

    # Add predictions to dataframe
    future_df['predicted_qty'] = predictions

    logger.info(f"  ✓ Generated {len(predictions):,} predictions")

    # ========================================================================
    # STEP 6: Format output
    # ========================================================================
    result = future_df[['ds', 'item_name', 'predicted_qty']].copy()
    result.columns = ['date', 'item_name', 'predicted_qty']
    result['predicted_qty'] = result['predicted_qty'].round(1)

    # ========================================================================
    # STEP 7: Display results
    # ========================================================================
    logger.info(f"\n{'='*80}")
    logger.info("PREDICTIONS BY DAY")
    logger.info(f"{'='*80}\n")

    for date in future_dates:
        day_pred = result[result['date'] == date]
        total = day_pred['predicted_qty'].sum()

        day_name = date.strftime('%a')
        logger.info(f"{date.strftime('%Y-%m-%d')} ({day_name}) - Total: {total:.0f} units")

        # Show top 5 items for this day
        top5 = day_pred.nlargest(5, 'predicted_qty')
        for _, row in top5.iterrows():
            logger.info(f"  {row['item_name'][:45]:45s} {row['predicted_qty']:5.1f} units")
        logger.info("")

    # ========================================================================
    # STEP 8: Summary by item (for whole period)
    # ========================================================================
    logger.info(f"{'='*80}")
    logger.info(f"SUMMARY BY ITEM ({days} days)")
    logger.info(f"{'='*80}\n")

    item_summary = result.groupby('item_name')['predicted_qty'].agg(['sum', 'mean']).sort_values('sum', ascending=False)

    logger.info(f"{'Rank':<5s} {'Item':<45s} {'Total':>8s} {'Avg/Day':>8s}")
    logger.info("-"*70)

    for idx, (item, row) in enumerate(item_summary.head(30).iterrows(), 1):
        logger.info(f"{idx:>3d}. {item[:45]:<45s} {row['sum']:>8.1f}  ({row['mean']:>5.1f}/day)")

    # Overall summary
    total_predicted = result['predicted_qty'].sum()
    avg_per_day = total_predicted / days

    logger.info(f"\n{'='*80}")
    logger.info("OVERALL SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"  Total predicted: {total_predicted:.0f} units")
    logger.info(f"  Average per day: {avg_per_day:.0f} units")
    logger.info(f"  Unique items: {len(items)}")
    logger.info(f"  Prediction days: {days}")

    # ========================================================================
    # STEP 9: Save to CSV
    # ========================================================================
    if output:
        result.to_csv(output, index=False)
        logger.info(f"\n✓ Saved predictions to: {output}")

    logger.info(f"\n{'='*80}\n")

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Generate item-level demand predictions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Predict next 7 days
  python predict_item_level_direct.py --start-date 2026-01-01 --days 7

  # Predict with specific model version
  python predict_item_level_direct.py --start-date 2026-01-01 --version v2.0

  # Save predictions to CSV
  python predict_item_level_direct.py --start-date 2026-01-01 --output forecast.csv

  # Use historical data for lag features
  python predict_item_level_direct.py --start-date 2026-01-01 --lexis-file data.xlsx
        """
    )

    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='Start date for predictions (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to forecast (default: 7)'
    )

    parser.add_argument(
        '--version',
        type=str,
        default='latest',
        help='Model version to load (default: latest)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output CSV file path'
    )

    parser.add_argument(
        '--lexis-file',
        type=str,
        default=None,
        help='Path to Lexis file for loading historical data (for lag features)'
    )

    args = parser.parse_args()

    try:
        # Parse start date
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')

        # Generate predictions
        result = predict_item_level_direct(
            start_date=start_date,
            days=args.days,
            version=args.version,
            output=args.output,
            lexis_file=args.lexis_file
        )

        logger.info("✓ Prediction completed successfully\n")
        sys.exit(0)

    except Exception as e:
        logger.error(f"\n✗ Prediction failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
