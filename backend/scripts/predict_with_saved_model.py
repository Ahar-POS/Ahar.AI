"""
Make Predictions with Saved Model

This script loads a saved model and makes predictions on new data.

Usage:
    # Predict next 7 days
    python scripts/predict_with_saved_model.py --days 7

    # Predict specific date range
    python scripts/predict_with_saved_model.py --start-date 2026-01-01 --end-date 2026-01-07

    # Use specific model version
    python scripts/predict_with_saved_model.py --version v1.0 --days 7
"""

import pandas as pd
import numpy as np
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from scripts.train_and_save_model import load_model
from scripts.ensemble_backtest import prepare_features, apply_holiday_adjustment

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_future_dates(start_date: datetime, n_days: int) -> pd.DataFrame:
    """
    Create DataFrame with future dates for prediction

    Args:
        start_date: Starting date
        n_days: Number of days to predict

    Returns:
        DataFrame with 'ds' column
    """
    dates = pd.date_range(start=start_date, periods=n_days, freq='D')
    return pd.DataFrame({'ds': dates})


def prepare_prediction_features(
    future_df: pd.DataFrame,
    historical_df: pd.DataFrame = None
) -> pd.DataFrame:
    """
    Prepare features for future dates

    Args:
        future_df: DataFrame with future dates
        historical_df: Historical data for lag features (optional)

    Returns:
        DataFrame with all features needed for prediction
    """
    # Add dummy y column (not used for prediction)
    future_df['y'] = 0

    # If we have historical data, combine it to calculate lags
    if historical_df is not None:
        combined = pd.concat([historical_df[['ds', 'y']], future_df], ignore_index=True)
        combined = prepare_features(combined)

        # Extract only future dates
        future_df = combined[combined['ds'].isin(future_df['ds'])].copy()
    else:
        # No historical data - features will have NaN for lags
        future_df = prepare_features(future_df)

    return future_df


def predict_demand(
    model_dict: dict,
    future_df: pd.DataFrame,
    apply_holiday_adj: bool = True
) -> pd.DataFrame:
    """
    Predict demand for future dates

    Args:
        model_dict: Loaded model dictionary
        future_df: DataFrame with features
        apply_holiday_adj: Whether to apply holiday adjustments

    Returns:
        DataFrame with predictions
    """
    model = model_dict['model']
    feature_cols = model_dict['feature_cols']

    # Prepare features
    X = future_df[feature_cols].fillna(0)

    # Make predictions
    predictions = model.predict(X)
    predictions = np.maximum(predictions, 0)  # No negative predictions

    # Apply holiday adjustments
    if apply_holiday_adj:
        adjusted_predictions, adjustments = apply_holiday_adjustment(
            predictions,
            future_df['ds']
        )
        predictions = adjusted_predictions

        logger.info(f"Applied {len(adjustments)} holiday adjustments")
        for adj in adjustments:
            logger.info(f"  {adj['date'].strftime('%Y-%m-%d')} - {adj['holiday']}: "
                       f"{adj['original']:.0f} → {adj['adjusted']:.0f}")
    else:
        adjustments = []

    # Create results DataFrame
    results = pd.DataFrame({
        'date': future_df['ds'],
        'day_of_week': future_df['ds'].dt.day_name(),
        'predicted_demand': predictions.round(0).astype(int),
        'is_weekend': future_df['is_weekend'].values,
        'discount_penetration': future_df.get('discount_penetration', 0).values,
        'is_rainy': future_df.get('is_rainy', 0).values
    })

    return results


def main():
    parser = argparse.ArgumentParser(description='Predict demand with saved model')
    parser.add_argument(
        '--version',
        type=str,
        default='latest',
        help='Model version to use (default: latest)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Number of days to predict from today'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output CSV file path'
    )
    parser.add_argument(
        '--no-holiday-adj',
        action='store_true',
        help='Disable holiday adjustments'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("DEMAND PREDICTION")
    logger.info("="*80)

    # Load model
    logger.info(f"\nLoading model version: {args.version}")
    model_dict = load_model(args.version)

    logger.info(f"\nModel Info:")
    logger.info(f"  Version: {model_dict['metadata']['version']}")
    logger.info(f"  Created: {model_dict['metadata']['created_at']}")
    logger.info(f"  Training MAPE: {model_dict['metadata']['train_mape']:.2f}%")
    logger.info(f"  Features: {model_dict['metadata']['n_features']}")

    # Determine date range
    if args.days:
        start_date = datetime.now().date()
        n_days = args.days
    elif args.start_date and args.end_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        n_days = (end_date - start_date).days + 1
    else:
        # Default: next 7 days
        start_date = datetime.now().date()
        n_days = 7

    logger.info(f"\nPredicting for:")
    logger.info(f"  Start date: {start_date}")
    logger.info(f"  Days: {n_days}")

    # Create future dates
    future_df = create_future_dates(start_date, n_days)

    # Prepare features
    future_df = prepare_prediction_features(future_df, historical_df=None)

    # Make predictions
    logger.info(f"\nGenerating predictions...")
    results = predict_demand(
        model_dict,
        future_df,
        apply_holiday_adj=not args.no_holiday_adj
    )

    # Display results
    logger.info(f"\n{'='*80}")
    logger.info("PREDICTIONS")
    logger.info(f"{'='*80}\n")

    for idx, row in results.iterrows():
        weekend_marker = "🔸" if row['is_weekend'] else "  "
        discount_marker = f"💰{row['discount_penetration']*100:.0f}%" if row['discount_penetration'] > 0 else "    "
        rain_marker = "🌧️ " if row['is_rainy'] else "   "

        logger.info(
            f"{weekend_marker} {row['date'].strftime('%Y-%m-%d')} ({row['day_of_week'][:3]}): "
            f"{row['predicted_demand']:4d} units  {discount_marker} {rain_marker}"
        )

    # Summary statistics
    logger.info(f"\n{'='*80}")
    logger.info("SUMMARY")
    logger.info(f"{'='*80}\n")
    logger.info(f"Total predicted demand: {results['predicted_demand'].sum():,} units")
    logger.info(f"Average daily demand:   {results['predicted_demand'].mean():.0f} units")
    logger.info(f"Peak demand:            {results['predicted_demand'].max()} units on {results.loc[results['predicted_demand'].idxmax(), 'date'].strftime('%Y-%m-%d')}")
    logger.info(f"Lowest demand:          {results['predicted_demand'].min()} units on {results.loc[results['predicted_demand'].idxmin(), 'date'].strftime('%Y-%m-%d')}")

    # Weekend vs weekday
    weekend_avg = results[results['is_weekend'] == 1]['predicted_demand'].mean()
    weekday_avg = results[results['is_weekend'] == 0]['predicted_demand'].mean()
    logger.info(f"\nWeekend avg:  {weekend_avg:.0f} units")
    logger.info(f"Weekday avg:  {weekday_avg:.0f} units")

    # Save to CSV if requested
    if args.output:
        results.to_csv(args.output, index=False)
        logger.info(f"\n✓ Saved predictions to: {args.output}")

    logger.info(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
