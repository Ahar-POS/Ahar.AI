"""
Backtest ML Models Directly from Lexis Excel File

This script loads the real Lexis data from Excel and trains/tests ML models
without needing to import into MongoDB first.

Usage:
    python scripts/backtest_from_excel.py
    python scripts/backtest_from_excel.py --tune  # with hyperparameter tuning
"""

import pandas as pd
import numpy as np
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_lexis_excel(file_path: str) -> pd.DataFrame:
    """
    Load Lexis order data from Excel file

    Args:
        file_path: Path to Lexis Excel file

    Returns:
        DataFrame with order line items
    """
    logger.info(f"Loading Lexis data from: {file_path}")

    # Try different header rows
    for header_row in [4, 5, 6]:
        try:
            df = pd.read_excel(file_path, header=header_row)

            # Check if we have expected columns
            if 'Date' in df.columns or any('date' in str(col).lower() for col in df.columns):
                # Find the date column
                date_col = 'Date' if 'Date' in df.columns else [col for col in df.columns if 'date' in str(col).lower()][0]

                # Convert to datetime
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

                # Remove rows without valid dates
                df = df[df[date_col].notna()]

                # Remove 'Total' summary rows
                if len(df) > 0 and 'Total' in str(df.iloc[0].values):
                    df = df.iloc[1:]

                if len(df) > 1000:  # Should have ~11k rows
                    logger.info(f"✓ Loaded {len(df):,} order line items")
                    logger.info(f"  Date range: {df[date_col].min()} to {df[date_col].max()}")
                    logger.info(f"  Unique dates: {df[date_col].nunique()}")
                    return df

        except Exception as e:
            continue

    raise ValueError(f"Could not load Excel file properly. Tried headers 4-6.")


def prepare_daily_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate to daily level and create simple features

    Args:
        df: Order line items dataframe

    Returns:
        Daily aggregated dataframe with features
    """
    logger.info("Creating daily features...")

    # Find date and quantity columns
    date_col = 'Date' if 'Date' in df.columns else [col for col in df.columns if 'date' in str(col).lower()][0]
    qty_col = 'Qty.' if 'Qty.' in df.columns else [col for col in df.columns if 'qty' in str(col).lower() or 'quantity' in str(col).lower()][0]

    # Ensure numeric
    df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)

    # Aggregate by date
    daily = df.groupby(date_col).agg({
        qty_col: 'sum',  # Total quantity sold per day
    }).reset_index()

    daily.columns = ['ds', 'y']
    daily = daily.sort_values('ds')

    # Add temporal features
    daily['day_of_week'] = daily['ds'].dt.dayofweek
    daily['day_of_month'] = daily['ds'].dt.day
    daily['month'] = daily['ds'].dt.month
    daily['is_weekend'] = (daily['day_of_week'] >= 5).astype(int)

    # Add lag features
    for lag in [1, 7, 14]:
        daily[f'lag_{lag}'] = daily['y'].shift(lag)

    # Add rolling features
    daily['rolling_mean_7'] = daily['y'].rolling(window=7, min_periods=1).mean()
    daily['rolling_mean_14'] = daily['y'].rolling(window=14, min_periods=1).mean()
    daily['rolling_std_7'] = daily['y'].rolling(window=7, min_periods=1).std().fillna(0)

    logger.info(f"✓ Created {len(daily)} daily records with {len(daily.columns)} features")

    return daily


def train_simple_xgboost(train_df: pd.DataFrame, test_df: pd.DataFrame) -> Dict[str, Any]:
    """Train XGBoost model with simple features"""
    from xgboost import XGBRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    logger.info("Training XGBoost...")

    # Prepare features (drop NaN rows from lag features)
    feature_cols = [col for col in train_df.columns if col not in ['ds', 'y']]

    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['y']

    X_test = test_df[feature_cols].fillna(0)
    y_test = test_df['y']

    logger.info(f"  Training samples: {len(X_train)}, Features: {len(feature_cols)}")
    logger.info(f"  Test samples: {len(X_test)}")

    # Train model
    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42
    )

    model.fit(X_train, y_train)

    # Predict
    y_pred = model.predict(X_test)
    y_pred = np.maximum(y_pred, 0)  # No negative predictions

    # Calculate metrics
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mape = np.mean(np.abs((y_test - y_pred) / (y_test + 1e-10))) * 100
    r2 = r2_score(y_test, y_pred)

    train_pred = model.predict(X_train)
    train_mape = np.mean(np.abs((y_train - train_pred) / (y_train + 1e-10))) * 100

    logger.info(f"  Training MAPE: {train_mape:.2f}%")
    logger.info(f"  Test MAPE: {mape:.2f}%")
    logger.info(f"  Test MAE: {mae:.2f}")
    logger.info(f"  Test RMSE: {rmse:.2f}")
    logger.info(f"  Test R²: {r2:.4f}")

    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    logger.info(f"\n  Top 5 important features:")
    for _, row in importance.head(5).iterrows():
        logger.info(f"    {row['feature']}: {row['importance']:.4f}")

    return {
        'train_mape': round(train_mape, 2),
        'test_mape': round(mape, 2),
        'mae': round(mae, 2),
        'rmse': round(rmse, 2),
        'r2': round(r2, 4),
        'feature_importance': importance
    }


def main():
    parser = argparse.ArgumentParser(description="Backtest ML models from Excel")
    parser.add_argument('--tune', action='store_true', help="Run hyperparameter tuning")
    args = parser.parse_args()

    logger.info("="*70)
    logger.info("LEXIS EXCEL BACKTEST - Direct from Excel")
    logger.info("="*70)

    try:
        # Load data
        lexis_file = "/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx"
        df = load_lexis_excel(lexis_file)

        # Prepare daily features
        daily = prepare_daily_features(df)

        # Train-test split
        # Oct 1 - Dec 14 = training (75 days)
        # Dec 15 - Dec 31 = testing (17 days)
        split_date = datetime(2025, 12, 15)

        train_df = daily[daily['ds'] < split_date].copy()
        test_df = daily[daily['ds'] >= split_date].copy()

        logger.info(f"\n📊 Data Split:")
        logger.info(f"  Training: {train_df['ds'].min().date()} to {train_df['ds'].max().date()} ({len(train_df)} days)")
        logger.info(f"  Testing:  {test_df['ds'].min().date()} to {test_df['ds'].max().date()} ({len(test_df)} days)")
        logger.info(f"  Total daily average: {daily['y'].mean():.1f} units/day")

        # Train model
        logger.info(f"\n{'='*70}")
        results = train_simple_xgboost(train_df, test_df)

        # Summary
        logger.info(f"\n{'='*70}")
        logger.info("RESULTS SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Training MAPE: {results['train_mape']}%")
        logger.info(f"Test MAPE:     {results['test_mape']}%")
        logger.info(f"Test MAE:      {results['mae']}")
        logger.info(f"Test RMSE:     {results['rmse']}")
        logger.info(f"Test R²:       {results['r2']}")

        logger.info(f"\n🎯 Target: 10-15% MAPE")
        if results['test_mape'] <= 15:
            logger.info("   Status: ✅ TARGET MET!")
        elif results['test_mape'] <= 25:
            logger.info("   Status: ⚠️  GOOD (close to target)")
        else:
            logger.info("   Status: ❌ NEEDS IMPROVEMENT")

        logger.info(f"{'='*70}\n")

        sys.exit(0 if results['test_mape'] <= 25 else 1)

    except Exception as e:
        logger.error(f"\n✗ Backtest failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
