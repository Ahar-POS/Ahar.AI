"""
Train Model with Post-Prediction Holiday Adjustments

Strategy: Train XGBoost without holiday features, then apply rule-based
holiday corrections to predictions based on IndianHolidayCalendar.

This works better than training with holiday features because:
1. Only 4 holidays in 74 training days (5.4% signal too weak)
2. XGBoost overfits and ignores sparse holiday features
3. Rule-based corrections are more reliable for known holidays
"""

import pandas as pd
import numpy as np
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.ml.feature_library import build_cloud_kitchen_features
from app.services.ml.holiday_calendar import IndianHolidayCalendar

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_lexis_excel(file_path: str) -> pd.DataFrame:
    """Load Lexis order data from Excel"""
    logger.info(f"Loading data from: {file_path}")

    for header_row in [4, 5, 6]:
        try:
            df = pd.read_excel(file_path, header=header_row)
            date_cols = [col for col in df.columns if 'date' in str(col).lower()]
            if not date_cols:
                continue

            date_col = date_cols[0]
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df[df[date_col].notna()]

            if len(df) > 0 and 'Total' in str(df.iloc[0].values):
                df = df.iloc[1:]

            if len(df) > 1000:
                logger.info(f"✓ Loaded {len(df):,} order line items")
                return df

        except Exception:
            continue

    raise ValueError("Could not load Excel file")


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create features WITHOUT holidays (will apply post-prediction)"""
    logger.info("Creating features...")

    date_col = [col for col in df.columns if 'date' in str(col).lower()][0]
    qty_col = 'Qty.' if 'Qty.' in df.columns else [col for col in df.columns if 'qty' in str(col).lower()][0]

    df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)

    # Aggregate daily
    daily = df.groupby(date_col).agg({qty_col: 'sum'}).reset_index()
    daily.columns = ['ds', 'y']
    daily = daily.sort_values('ds')

    # Temporal features
    daily['day_of_week'] = daily['ds'].dt.dayofweek
    daily['day_of_month'] = daily['ds'].dt.day
    daily['month'] = daily['ds'].dt.month
    daily['is_weekend'] = (daily['day_of_week'] >= 5).astype(int)

    # Lag features
    for lag in [1, 7, 14]:
        daily[f'lag_{lag}'] = daily['y'].shift(lag)

    # Rolling features
    daily['rolling_mean_7'] = daily['y'].rolling(window=7, min_periods=1).mean()
    daily['rolling_mean_14'] = daily['y'].rolling(window=14, min_periods=1).mean()
    daily['rolling_std_7'] = daily['y'].rolling(window=7, min_periods=1).std().fillna(0)

    # Cloud kitchen features
    daily = build_cloud_kitchen_features(daily, "Cloud Kitchen", "Residential", True)

    logger.info(f"✓ Created {len(daily)} daily records with {len(daily.columns)-2} features")

    return daily


def apply_holiday_adjustment(date_obj: datetime, base_prediction: float) -> tuple[float, str]:
    """
    Apply rule-based holiday adjustment to base prediction

    Returns: (adjusted_prediction, explanation)
    """
    holiday = IndianHolidayCalendar.get_holiday(date_obj)

    if not holiday:
        return base_prediction, ""

    impact = holiday['impact']
    adjusted = base_prediction * (1 + impact)
    adjusted = max(adjusted, 0)  # No negative predictions

    explanation = f"{holiday['name']} ({impact:+.0%} impact): {base_prediction:.0f} → {adjusted:.0f}"

    return adjusted, explanation


def train_xgboost_model(train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: list) -> Dict[str, Any]:
    """Train XGBoost model and return metrics"""
    from xgboost import XGBRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['y']
    X_test = test_df[feature_cols].fillna(0)
    y_test = test_df['y']

    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
        verbosity=0
    )

    model.fit(X_train, y_train)

    # Base predictions (without holiday adjustments)
    y_pred_train = model.predict(X_train)
    y_pred_test_base = model.predict(X_test)
    y_pred_test_base = np.maximum(y_pred_test_base, 0)

    # Apply holiday adjustments to test predictions
    y_pred_test_adjusted = []
    adjustments = []

    for idx, row in test_df.iterrows():
        base_pred = y_pred_test_base[test_df.index.get_loc(idx)]
        adjusted_pred, explanation = apply_holiday_adjustment(row['ds'], base_pred)
        y_pred_test_adjusted.append(adjusted_pred)

        if explanation:
            adjustments.append({
                'date': row['ds'],
                'actual': row['y'],
                'base_pred': base_pred,
                'adjusted_pred': adjusted_pred,
                'explanation': explanation
            })

    y_pred_test_adjusted = np.array(y_pred_test_adjusted)

    # Metrics - BASE model (without adjustments)
    train_mape = np.mean(np.abs((y_train - y_pred_train) / (y_train + 1e-10))) * 100
    test_mape_base = np.mean(np.abs((y_test - y_pred_test_base) / (y_test + 1e-10))) * 100

    # Metrics - ADJUSTED model (with holiday corrections)
    test_mape_adj = np.mean(np.abs((y_test - y_pred_test_adjusted) / (y_test + 1e-10))) * 100
    test_mae_adj = mean_absolute_error(y_test, y_pred_test_adjusted)
    test_rmse_adj = np.sqrt(mean_squared_error(y_test, y_pred_test_adjusted))
    test_r2_adj = r2_score(y_test, y_pred_test_adjusted)

    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    return {
        'model': model,
        'predictions_base': y_pred_test_base,
        'predictions_adjusted': y_pred_test_adjusted,
        'train_mape': round(train_mape, 2),
        'test_mape_base': round(test_mape_base, 2),
        'test_mape_adjusted': round(test_mape_adj, 2),
        'test_mae': round(test_mae_adj, 2),
        'test_rmse': round(test_rmse_adj, 2),
        'test_r2': round(test_r2_adj, 4),
        'feature_importance': importance,
        'holiday_adjustments': adjustments
    }


def main():
    logger.info("="*70)
    logger.info("ML TRAINING WITH POST-PREDICTION HOLIDAY ADJUSTMENTS")
    logger.info("="*70)

    try:
        # Load data
        lexis_file = "/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx"
        df = load_lexis_excel(lexis_file)

        # Prepare features (WITHOUT holidays)
        daily = prepare_features(df)

        # Train-test split
        split_date = datetime(2025, 12, 15)
        train_df = daily[daily['ds'] < split_date].copy()
        test_df = daily[daily['ds'] >= split_date].copy()

        logger.info(f"\n{'='*70}")
        logger.info("DATA SPLIT:")
        logger.info(f"  Training: {train_df['ds'].min().date()} to {train_df['ds'].max().date()} ({len(train_df)} days)")
        logger.info(f"  Testing:  {test_df['ds'].min().date()} to {test_df['ds'].max().date()} ({len(test_df)} days)")

        # Train model
        logger.info(f"\n{'='*70}")
        logger.info("TRAINING MODEL")
        logger.info(f"{'='*70}")

        feature_cols = [col for col in daily.columns if col not in ['ds', 'y']]
        results = train_xgboost_model(train_df, test_df, feature_cols)

        logger.info(f"\n📊 Results:")
        logger.info(f"  Features:              {len(feature_cols)}")
        logger.info(f"  Train MAPE:            {results['train_mape']}%")
        logger.info(f"  Test MAPE (base):      {results['test_mape_base']}%")
        logger.info(f"  Test MAPE (adjusted):  {results['test_mape_adjusted']}% ← With holiday corrections")
        logger.info(f"  Test MAE:              {results['test_mae']}")
        logger.info(f"  Test R²:               {results['test_r2']}")

        # Show improvement
        improvement = results['test_mape_base'] - results['test_mape_adjusted']
        logger.info(f"\n✨ Holiday Adjustment Impact:")
        logger.info(f"  MAPE Improvement: {improvement:.2f} percentage points")
        logger.info(f"  Relative Improvement: {improvement/results['test_mape_base']*100:.1f}%")

        # Show holiday adjustments
        if results['holiday_adjustments']:
            logger.info(f"\n🎄 Holiday Adjustments Applied ({len(results['holiday_adjustments'])} days):")
            logger.info("-" * 70)
            for adj in results['holiday_adjustments']:
                error_base = abs(adj['actual'] - adj['base_pred']) / (adj['actual'] + 1) * 100
                error_adj = abs(adj['actual'] - adj['adjusted_pred']) / (adj['actual'] + 1) * 100
                logger.info(f"  {adj['date'].strftime('%Y-%m-%d')} - {adj['explanation']}")
                logger.info(f"    Actual: {adj['actual']:.0f}")
                logger.info(f"    Base error: {error_base:.1f}% → Adjusted error: {error_adj:.1f}%")
                logger.info("")

        logger.info(f"\n🔝 Top 10 Important Features:")
        for _, row in results['feature_importance'].head(10).iterrows():
            logger.info(f"  {row['feature']:30s} {row['importance']:.4f}")

        logger.info(f"\n{'='*70}")
        logger.info("SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Strategy: Train XGBoost on temporal patterns, apply rule-based holiday corrections")
        logger.info(f"Result: {results['test_mape_base']}% → {results['test_mape_adjusted']}% MAPE")

        if results['test_mape_adjusted'] <= 15:
            logger.info(f"🎯 Status: ✅ TARGET MET! (10-15% MAPE)")
        elif results['test_mape_adjusted'] <= 25:
            logger.info(f"🎯 Status: ⚠️  GOOD (close to target)")
        else:
            logger.info(f"🎯 Status: 🔄 NEEDS MORE WORK (target: 10-15%)")

        logger.info(f"{'='*70}\n")

        sys.exit(0)

    except Exception as e:
        logger.error(f"\n✗ Training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
