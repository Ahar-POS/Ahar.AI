"""
Train Model with LLM-Powered Feature Engineering

This script:
1. Loads Lexis data from Excel (separate from POS database)
2. Adds baseline features
3. Trains initial model (baseline)
4. Uses Claude AI to analyze errors and suggest new features
5. Implements suggested features
6. Retrains model and shows improvement

ISOLATED FROM POS CODE - Only reads Excel, never touches database
"""

import pandas as pd
import numpy as np
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import os

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.ml.feature_library import build_cloud_kitchen_features
from app.services.ml.llm_feature_engineer import LLMFeatureEngineer, implement_llm_feature
from app.services.ml.holiday_calendar import IndianHolidayCalendar

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_lexis_excel(file_path: str) -> pd.DataFrame:
    """Load Lexis order data from Excel"""
    logger.info(f"Loading data from: {file_path}")

    # Try different header rows
    for header_row in [4, 5, 6]:
        try:
            df = pd.read_excel(file_path, header=header_row)

            # Find date column
            date_cols = [col for col in df.columns if 'date' in str(col).lower()]
            if not date_cols:
                continue

            date_col = date_cols[0]
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df[df[date_col].notna()]

            # Remove Total row if exists
            if len(df) > 0 and 'Total' in str(df.iloc[0].values):
                df = df.iloc[1:]

            if len(df) > 1000:
                logger.info(f"✓ Loaded {len(df):,} order line items")
                return df

        except Exception as e:
            continue

    raise ValueError("Could not load Excel file")


def prepare_baseline_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create baseline temporal and lag features"""
    logger.info("Creating baseline features...")

    # Find columns
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

    logger.info(f"✓ Created {len(daily)} daily records with baseline features")

    return daily


def train_xgboost_model(train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: List[str]) -> Dict[str, Any]:
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

    # Predictions
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    y_pred_test = np.maximum(y_pred_test, 0)

    # Metrics
    train_mape = np.mean(np.abs((y_train - y_pred_train) / (y_train + 1e-10))) * 100
    test_mape = np.mean(np.abs((y_test - y_pred_test) / (y_test + 1e-10))) * 100
    test_mae = mean_absolute_error(y_test, y_pred_test)
    test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    test_r2 = r2_score(y_test, y_pred_test)

    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    return {
        'model': model,
        'predictions': y_pred_test,
        'train_mape': round(train_mape, 2),
        'test_mape': round(test_mape, 2),
        'test_mae': round(test_mae, 2),
        'test_rmse': round(test_rmse, 2),
        'test_r2': round(test_r2, 4),
        'feature_importance': importance
    }


def main():
    parser = argparse.ArgumentParser(description="Train with LLM feature engineering")
    parser.add_argument('--skip-llm', action='store_true', help="Skip LLM analysis (use rule-based)")
    parser.add_argument('--api-key', type=str, help="Anthropic API key")
    args = parser.parse_args()

    logger.info("="*70)
    logger.info("ML TRAINING WITH LLM FEATURE ENGINEERING")
    logger.info("="*70)

    try:
        # ===================================================================
        # STEP 1: Load Data
        # ===================================================================
        lexis_file = "/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx"
        df = load_lexis_excel(lexis_file)

        # ===================================================================
        # STEP 2: Prepare Baseline Features
        # ===================================================================
        daily = prepare_baseline_features(df)

        # ===================================================================
        # STEP 3: Add Cloud Kitchen Features
        # ===================================================================
        logger.info("\nAdding cloud kitchen features...")

        daily = build_cloud_kitchen_features(
            daily,
            restaurant_type="Cloud Kitchen",
            area_type="Residential",
            delivery_focused=True
        )

        baseline_feature_count = len([col for col in daily.columns if col not in ['ds', 'y']])
        logger.info(f"✓ Total features after cloud kitchen engineering: {baseline_feature_count}")

        # ===================================================================
        # STEP 3.5: Add Holiday Calendar Features
        # ===================================================================
        logger.info("\nAdding Indian holiday calendar...")

        daily = IndianHolidayCalendar.add_holiday_features(daily)

        # Count holidays in dataset
        holidays_found = daily[daily['is_holiday'] == 1]
        logger.info(f"✓ Found {len(holidays_found)} holiday days in dataset:")
        for _, row in holidays_found.iterrows():
            impact = row['holiday_impact_score']
            sign = '+' if impact > 0 else ''
            logger.info(f"  {row['ds'].strftime('%Y-%m-%d')}: {row['holiday_name']} (impact: {sign}{impact:.0%})")

        with_holidays_count = len([col for col in daily.columns if col not in ['ds', 'y']])
        new_holiday_features = with_holidays_count - baseline_feature_count
        logger.info(f"✓ Added {new_holiday_features} holiday features")

        # ===================================================================
        # STEP 4: Train-Test Split
        # ===================================================================
        split_date = datetime(2025, 12, 15)
        train_df = daily[daily['ds'] < split_date].copy()
        test_df = daily[daily['ds'] >= split_date].copy()

        logger.info(f"\n{'='*70}")
        logger.info("DATA SPLIT:")
        logger.info(f"  Training: {train_df['ds'].min().date()} to {train_df['ds'].max().date()} ({len(train_df)} days)")
        logger.info(f"  Testing:  {test_df['ds'].min().date()} to {test_df['ds'].max().date()} ({len(test_df)} days)")

        # ===================================================================
        # STEP 5: Train Baseline Model
        # ===================================================================
        logger.info(f"\n{'='*70}")
        logger.info("PHASE 1: BASELINE MODEL (Cloud Kitchen Features)")
        logger.info(f"{'='*70}")

        feature_cols = [col for col in daily.columns if col not in ['ds', 'y', 'holiday_name']]
        baseline_results = train_xgboost_model(train_df, test_df, feature_cols)

        logger.info(f"\n📊 Baseline Results:")
        logger.info(f"  Features:     {len(feature_cols)}")
        logger.info(f"  Train MAPE:   {baseline_results['train_mape']}%")
        logger.info(f"  Test MAPE:    {baseline_results['test_mape']}%")
        logger.info(f"  Test MAE:     {baseline_results['test_mae']}")
        logger.info(f"  Test R²:      {baseline_results['test_r2']}")

        logger.info(f"\n🔝 Top 10 Important Features:")
        for _, row in baseline_results['feature_importance'].head(10).iterrows():
            logger.info(f"  {row['feature']:30s} {row['importance']:.4f}")

        # ===================================================================
        # STEP 6: LLM Error Analysis
        # ===================================================================
        logger.info(f"\n{'='*70}")
        logger.info("PHASE 2: LLM FEATURE ENGINEERING")
        logger.info(f"{'='*70}")

        # Get API key
        api_key = args.api_key or os.getenv('ANTHROPIC_API_KEY')

        if args.skip_llm or not api_key:
            logger.warning("⚠️  Skipping LLM analysis (--skip-llm or no API key)")
            logger.info("Using rule-based feature suggestions instead")

        # Initialize LLM engineer
        llm_engineer = LLMFeatureEngineer(anthropic_api_key=api_key)

        # Restaurant context for LLM
        restaurant_context = {
            'type': 'Cloud Kitchen',
            'area_type': 'Residential',
            'location': 'DLF Phase IV, Sector 28, Gurugram',
            'primary_channel': 'Delivery (Swiggy/Zomato 80%)',
            'walk_in_pct': 20
        }

        # Analyze errors
        logger.info("\nAnalyzing prediction errors with LLM...")
        analysis = llm_engineer.analyze_errors(
            train_df,
            test_df,
            baseline_results['predictions'],
            feature_cols,
            restaurant_context
        )

        # Show error patterns
        error_patterns = analysis['error_patterns']
        logger.info(f"\n📉 Error Analysis:")
        logger.info(f"  Average test error: {error_patterns['avg_error_pct']:.1f}%")
        logger.info(f"  Over-predictions:   {error_patterns['over_predictions']}")
        logger.info(f"  Under-predictions:  {error_patterns['under_predictions']}")

        logger.info(f"\n❌ Worst Prediction Days:")
        for day in error_patterns['worst_days'][:3]:
            day_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day['day_of_week']]
            logger.info(f"  {day['ds'].strftime('%Y-%m-%d')} ({day_name}): "
                       f"Predicted {day['pred']:.0f}, Actual {day['y']:.0f}, "
                       f"Error {day['error_pct']:.1f}%")

        # Show LLM suggestions
        llm_suggestions = analysis['llm_suggestions']
        logger.info(f"\n💡 LLM Feature Suggestions:")
        for i, feature in enumerate(llm_suggestions.get('features', []), 1):
            logger.info(f"\n  {i}. {feature['name']}")
            logger.info(f"     {feature['description']}")
            logger.info(f"     Rationale: {feature['rationale']}")

        # ===================================================================
        # STEP 7: Implement LLM Features
        # ===================================================================
        logger.info(f"\n{'='*70}")
        logger.info("IMPLEMENTING LLM FEATURES")
        logger.info(f"{'='*70}")

        enhanced_daily = daily.copy()
        for feature_def in llm_suggestions.get('features', []):
            enhanced_daily = implement_llm_feature(enhanced_daily, feature_def)

        # Re-split with new features
        train_df_enhanced = enhanced_daily[enhanced_daily['ds'] < split_date].copy()
        test_df_enhanced = enhanced_daily[enhanced_daily['ds'] >= split_date].copy()

        enhanced_feature_cols = [col for col in enhanced_daily.columns if col not in ['ds', 'y', 'holiday_name']]
        new_feature_count = len(enhanced_feature_cols) - len(feature_cols)

        logger.info(f"\n✓ Added {new_feature_count} new features")
        logger.info(f"  Total features: {len(enhanced_feature_cols)}")

        # ===================================================================
        # STEP 8: Retrain with Enhanced Features
        # ===================================================================
        logger.info(f"\n{'='*70}")
        logger.info("PHASE 3: ENHANCED MODEL (Baseline + LLM Features)")
        logger.info(f"{'='*70}")

        enhanced_results = train_xgboost_model(train_df_enhanced, test_df_enhanced, enhanced_feature_cols)

        logger.info(f"\n📊 Enhanced Results:")
        logger.info(f"  Features:     {len(enhanced_feature_cols)}")
        logger.info(f"  Train MAPE:   {enhanced_results['train_mape']}%")
        logger.info(f"  Test MAPE:    {enhanced_results['test_mape']}%")
        logger.info(f"  Test MAE:     {enhanced_results['test_mae']}")
        logger.info(f"  Test R²:      {enhanced_results['test_r2']}")

        logger.info(f"\n🔝 Top 10 Important Features (Enhanced Model):")
        for _, row in enhanced_results['feature_importance'].head(10).iterrows():
            is_new = "🆕" if row['feature'] not in feature_cols else "  "
            logger.info(f"  {is_new} {row['feature']:30s} {row['importance']:.4f}")

        # ===================================================================
        # STEP 9: Compare Results
        # ===================================================================
        logger.info(f"\n{'='*70}")
        logger.info("FINAL COMPARISON")
        logger.info(f"{'='*70}")

        improvement = baseline_results['test_mape'] - enhanced_results['test_mape']
        improvement_pct = (improvement / baseline_results['test_mape']) * 100

        logger.info(f"\n📈 Model Progression:")
        logger.info(f"  Baseline (10 features):               39.68% MAPE")
        logger.info(f"  + Cloud Kitchen + Holidays ({baseline_feature_count} features): {baseline_results['test_mape']}% MAPE")
        logger.info(f"  + LLM Features ({len(enhanced_feature_cols)} features):         {enhanced_results['test_mape']}% MAPE")

        logger.info(f"\n✨ Improvement:")
        logger.info(f"  MAPE Reduction:     {improvement:.2f} percentage points")
        logger.info(f"  Relative Improvement: {improvement_pct:.1f}%")

        if enhanced_results['test_mape'] <= 15:
            logger.info(f"\n🎯 Status: ✅ TARGET MET! (10-15% MAPE)")
        elif enhanced_results['test_mape'] <= 20:
            logger.info(f"\n🎯 Status: ⚠️  CLOSE TO TARGET (target: 10-15%)")
        else:
            logger.info(f"\n🎯 Status: 🔄 NEEDS MORE WORK (target: 10-15%)")

        logger.info(f"\n{'='*70}\n")

        sys.exit(0)

    except Exception as e:
        logger.error(f"\n✗ Training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
