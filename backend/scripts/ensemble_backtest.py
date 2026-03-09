"""
Comprehensive Ensemble Backtest with Holiday Post-Adjustment

Compares 6 model variants on Lexis data (Dec 15-31 holdout):
1. XGBoost baseline
2. XGBoost + holiday post-adjustment
3. Prophet
4. SARIMA
5. Ensemble (weighted by validation accuracy)
6. Ensemble + holiday post-adjustment

Key features:
- Validation-based ensemble weights (not in-sample fit)
- Holiday correction as final post-processing layer
- Per-day residual analysis
- Full 17-day holdout evaluation
"""

import pandas as pd
import numpy as np
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import warnings

warnings.filterwarnings('ignore')

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


def load_lexis_data(file_path: str) -> pd.DataFrame:
    """Load and prepare Lexis data"""
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
                qty_col = 'Qty.' if 'Qty.' in df.columns else [col for col in df.columns if 'qty' in str(col).lower()][0]
                df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)

                # Aggregate daily
                daily = df.groupby(date_col).agg({qty_col: 'sum'}).reset_index()
                daily.columns = ['ds', 'y']
                daily = daily.sort_values('ds')

                logger.info(f"✓ Loaded {len(df):,} line items → {len(daily)} daily records")
                return daily

        except Exception:
            continue

    raise ValueError("Could not load Excel file")


def prepare_features(daily: pd.DataFrame, clip_outliers: bool = True) -> pd.DataFrame:
    """Add temporal and cloud kitchen features"""
    # Temporal features
    daily['day_of_week'] = daily['ds'].dt.dayofweek
    daily['day_of_month'] = daily['ds'].dt.day
    daily['month'] = daily['ds'].dt.month
    daily['is_weekend'] = (daily['day_of_week'] >= 5).astype(int)

    # CRITICAL: Clip extreme outliers to prevent overfitting
    # Nov 29 had 1124 (outlier), cap at 99th percentile
    if clip_outliers:
        q99 = daily['y'].quantile(0.99)
        q01 = daily['y'].quantile(0.01)
        logger.info(f"Clipping outliers: capping demand at 99th percentile ({q99:.0f}), flooring at 1st percentile ({q01:.0f})")

        outliers_clipped = ((daily['y'] > q99) | (daily['y'] < q01)).sum()
        if outliers_clipped > 0:
            logger.info(f"  Clipped {outliers_clipped} outlier days")
            for idx, row in daily[daily['y'] > q99].iterrows():
                logger.info(f"    {row['ds'].strftime('%Y-%m-%d')}: {row['y']:.0f} → {q99:.0f}")

        daily['y'] = daily['y'].clip(lower=q01, upper=q99)

    # Load weather data if available
    weather_file = Path(__file__).parent.parent.parent / "data" / "gurgaon_weather_oct_dec_2025.xlsx"
    if weather_file.exists():
        logger.info(f"Loading weather data from: {weather_file}")
        try:
            weather = pd.read_excel(weather_file, sheet_name='weather_data')

            # Remove any rows with NaN dates (notes/metadata)
            weather = weather[weather['date'].notna()].copy()

            # Convert date column
            weather['ds'] = pd.to_datetime(weather['date'], errors='coerce')
            weather = weather[weather['ds'].notna()].copy()

            # Convert boolean flags to int (avoid type errors with bitwise operations)
            for col in ['is_rainy', 'is_heavy_rain', 'is_extreme_temp']:
                if col in weather.columns:
                    weather[col] = weather[col].fillna(0).astype(int)

            daily = daily.merge(
                weather[['ds', 'temp_avg', 'precipitation_mm', 'is_rainy', 'is_heavy_rain', 'is_extreme_temp']],
                on='ds',
                how='left'
            )

            # Fill missing weather values with 0
            for col in ['is_rainy', 'is_heavy_rain', 'is_extreme_temp']:
                if col in daily.columns:
                    daily[col] = daily[col].fillna(0).astype(int)

            logger.info(f"✓ Loaded weather data: {daily['is_rainy'].notna().sum()} days with weather")
        except Exception as e:
            logger.warning(f"Could not load weather data: {e}")

    # Load discount data if available
    discount_file = Path(__file__).parent.parent.parent / "data" / "daily_discount_features.csv"
    if discount_file.exists():
        logger.info(f"Loading discount data from: {discount_file}")
        try:
            discounts = pd.read_csv(discount_file)
            discounts['ds'] = pd.to_datetime(discounts['ds'])
            daily = daily.merge(
                discounts[[
                    'ds', 'discount_penetration', 'discount_avg_pct',
                    'is_high_discount_day', 'is_medium_discount_day', 'has_any_discount'
                ]],
                on='ds',
                how='left'
            )
            # Fill missing discount values with 0 (no discount)
            discount_cols = ['discount_penetration', 'discount_avg_pct', 'is_high_discount_day',
                           'is_medium_discount_day', 'has_any_discount']
            for col in discount_cols:
                if col in daily.columns:
                    daily[col] = daily[col].fillna(0)

            logger.info(f"✓ Loaded discount data: {daily['has_any_discount'].sum():.0f} days with discounts")
        except Exception as e:
            logger.warning(f"Could not load discount data: {e}")

    # Lag features
    for lag in [1, 7, 14]:
        daily[f'lag_{lag}'] = daily['y'].shift(lag)

    # Rolling features
    daily['rolling_mean_7'] = daily['y'].rolling(window=7, min_periods=1).mean()
    daily['rolling_mean_14'] = daily['y'].rolling(window=14, min_periods=1).mean()
    daily['rolling_std_7'] = daily['y'].rolling(window=7, min_periods=1).std().fillna(0)

    # Cloud kitchen features (includes weather features if available)
    daily = build_cloud_kitchen_features(daily, "Cloud Kitchen", "Residential", True)

    logger.info(f"✓ Added {len(daily.columns)-2} features")
    return daily


def apply_holiday_adjustment(predictions: np.ndarray, dates: pd.Series) -> Tuple[np.ndarray, List[Dict]]:
    """
    Apply rule-based holiday corrections to predictions

    Returns: (adjusted_predictions, adjustment_log)
    """
    # Ensure predictions is numpy array
    if isinstance(predictions, pd.Series):
        predictions = predictions.values

    adjusted = predictions.copy()
    adjustments = []

    # Reset dates index to match predictions array indexing
    dates_reset = dates.reset_index(drop=True)

    for i, date_val in enumerate(dates_reset):
        holiday = IndianHolidayCalendar.get_holiday(date_val)
        if holiday:
            impact = holiday['impact']
            original = predictions[i]
            adjusted[i] = max(original * (1 + impact), 0)

            adjustments.append({
                'date': date_val,
                'holiday': holiday['name'],
                'impact': impact,
                'original': original,
                'adjusted': adjusted[i]
            })

    return adjusted, adjustments


def train_xgboost(train_df: pd.DataFrame, val_df: pd.DataFrame, feature_cols: List[str]) -> Dict[str, Any]:
    """Train XGBoost model"""
    from xgboost import XGBRegressor

    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['y']
    X_val = val_df[feature_cols].fillna(0)
    y_val = val_df['y']

    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
        verbosity=0
    )

    model.fit(X_train, y_train)

    return {
        'model': model,
        'name': 'XGBoost',
        'feature_cols': feature_cols
    }


def train_prophet(train_df: pd.DataFrame, val_df: pd.DataFrame) -> Dict[str, Any]:
    """Train Prophet model"""
    try:
        from prophet import Prophet

        # Prepare data
        prophet_df = train_df[['ds', 'y']].copy()

        model = Prophet(
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10,
            seasonality_mode='multiplicative',
            weekly_seasonality=True,
            yearly_seasonality=False,
            daily_seasonality=False
        )

        model.fit(prophet_df)

        return {
            'model': model,
            'name': 'Prophet',
            'feature_cols': None
        }

    except Exception as e:
        logger.warning(f"Prophet training failed: {e}")
        return None


def train_sarima(train_df: pd.DataFrame, val_df: pd.DataFrame) -> Dict[str, Any]:
    """Train SARIMA model with auto order selection"""
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        from statsmodels.tsa.stattools import adfuller

        # Check stationarity
        adf_result = adfuller(train_df['y'].dropna())
        is_stationary = adf_result[1] < 0.05

        if not is_stationary:
            logger.warning("Time series not stationary, SARIMA may not be optimal")

        # Try simple SARIMA configuration
        model = SARIMAX(
            train_df['y'],
            order=(1, 1, 1),
            seasonal_order=(1, 1, 1, 7),
            enforce_stationarity=False,
            enforce_invertibility=False
        )

        fitted = model.fit(disp=False, maxiter=100)

        return {
            'model': fitted,
            'name': 'SARIMA',
            'feature_cols': None
        }

    except Exception as e:
        logger.warning(f"SARIMA training failed: {e}")
        return None


def predict_model(model_dict: Dict[str, Any], test_df: pd.DataFrame) -> np.ndarray:
    """Make predictions with any model type"""
    if model_dict is None:
        return None

    model = model_dict['model']
    name = model_dict['name']

    try:
        if name == 'XGBoost':
            X_test = test_df[model_dict['feature_cols']].fillna(0)
            predictions = model.predict(X_test)
            return np.maximum(predictions, 0)

        elif name == 'Prophet':
            future = test_df[['ds']].copy()
            forecast = model.predict(future)
            return np.maximum(forecast['yhat'].values, 0)

        elif name == 'SARIMA':
            # SARIMA forecast
            steps = len(test_df)
            predictions = model.forecast(steps=steps)
            return np.maximum(predictions, 0)

    except Exception as e:
        logger.error(f"{name} prediction failed: {e}")
        return None

    return None


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate forecast metrics"""
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-10))) * 100
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)

    return {
        'mape': round(mape, 2),
        'mae': round(mae, 2),
        'rmse': round(rmse, 2),
        'r2': round(r2, 4)
    }


def compute_ensemble_weights(models: List[Dict], val_df: pd.DataFrame) -> Dict[str, float]:
    """
    Compute ensemble weights based on validation accuracy

    Uses inverse MAPE as weights (better models get higher weight)
    """
    weights = {}
    inverse_mapes = {}

    y_val = val_df['y'].values

    for model_dict in models:
        if model_dict is None:
            continue

        name = model_dict['name']
        predictions = predict_model(model_dict, val_df)

        if predictions is None:
            continue

        metrics = calculate_metrics(y_val, predictions)
        mape = metrics['mape']

        # Use inverse MAPE for weighting (lower MAPE = higher weight)
        inverse_mape = 1.0 / (mape + 1e-10)
        inverse_mapes[name] = inverse_mape

        logger.info(f"  {name:15s} Val MAPE: {mape:6.2f}% → Weight: pending")

    # Normalize weights to sum to 1.0
    total = sum(inverse_mapes.values())
    if total > 0:
        weights = {name: inv_mape / total for name, inv_mape in inverse_mapes.items()}

    return weights


def create_ensemble_predictions(models: List[Dict], weights: Dict[str, float], test_df: pd.DataFrame) -> np.ndarray:
    """Create weighted ensemble predictions"""
    ensemble_pred = np.zeros(len(test_df))
    total_weight = 0

    for model_dict in models:
        if model_dict is None:
            continue

        name = model_dict['name']
        if name not in weights:
            continue

        predictions = predict_model(model_dict, test_df)
        if predictions is None:
            continue

        weight = weights[name]
        ensemble_pred += weight * predictions
        total_weight += weight

    # Normalize if weights don't sum to 1.0
    if total_weight > 0 and abs(total_weight - 1.0) > 0.01:
        ensemble_pred /= total_weight

    return ensemble_pred


def rolling_origin_backtest(
    daily_df: pd.DataFrame,
    model_type: str = 'xgb_only',
    feature_cols: List[str] = None,
    xgb_params: Dict[str, Any] = None,
    report_residuals: bool = False
) -> Dict[str, Any]:
    """
    Rolling-origin backtest with multiple December cutoffs

    Args:
        daily_df: Full daily data (Oct 1 - Dec 31)
        model_type: 'xgb_only', 'ensemble' (for comparison)
        feature_cols: List of feature column names
        xgb_params: XGBoost hyperparameters (if None, use defaults)
        report_residuals: If True, print detailed residual analysis

    Returns:
        {
            'fold_results': List of per-fold metrics,
            'mean_mape': Mean MAPE across folds,
            'median_mape': Median MAPE across folds,
            'worst_fold_mape': Max MAPE across folds,
            'reference_mape': Dec 15-21 MAPE (for comparison)
        }
    """
    from xgboost import XGBRegressor

    # Default XGBoost params (baseline)
    if xgb_params is None:
        xgb_params = {
            'n_estimators': 100,
            'max_depth': 4,
            'learning_rate': 0.1,
            'random_state': 42,
            'verbosity': 0
        }

    fold_results = []

    # Define fold cutoffs
    folds = [
        {
            'train_end': datetime(2025, 11, 30),
            'test_start': datetime(2025, 12, 1),
            'test_end': datetime(2025, 12, 7),
            'name': 'Dec 1-7'
        },
        {
            'train_end': datetime(2025, 12, 7),
            'test_start': datetime(2025, 12, 8),
            'test_end': datetime(2025, 12, 14),
            'name': 'Dec 8-14'
        },
        {
            'train_end': datetime(2025, 12, 14),
            'test_start': datetime(2025, 12, 15),
            'test_end': datetime(2025, 12, 21),
            'name': 'Dec 15-21'
        },
        {
            'train_end': datetime(2025, 12, 21),
            'test_start': datetime(2025, 12, 22),
            'test_end': datetime(2025, 12, 31),
            'name': 'Dec 22-31'
        }
    ]

    logger.info(f"\n{'='*80}")
    logger.info(f"ROLLING-ORIGIN BACKTEST: {model_type.upper()}")
    logger.info(f"{'='*80}\n")

    for fold_idx, fold in enumerate(folds):
        train_df = daily_df[daily_df['ds'] <= fold['train_end']].copy()
        test_df = daily_df[
            (daily_df['ds'] >= fold['test_start']) &
            (daily_df['ds'] <= fold['test_end'])
        ].copy()

        logger.info(f"Fold {fold_idx + 1} ({fold['name']}): "
                   f"Train to {fold['train_end'].date()}, Test {len(test_df)} days")

        # Train XGBoost
        model = XGBRegressor(**xgb_params)
        X_train = train_df[feature_cols].fillna(0)
        y_train = train_df['y']
        model.fit(X_train, y_train)

        # Predict
        X_test = test_df[feature_cols].fillna(0)
        predictions = model.predict(X_test)

        # Apply holiday adjustment
        adjusted_predictions, adjustments = apply_holiday_adjustment(
            predictions, test_df['ds']
        )

        # Calculate metrics
        y_test = test_df['y'].values
        mape = np.mean(np.abs((y_test - adjusted_predictions) / (y_test + 1e-10))) * 100

        # Residual analysis
        residuals = []
        for i, (idx, row) in enumerate(test_df.iterrows()):
            holiday = IndianHolidayCalendar.get_holiday(row['ds'])
            residuals.append({
                'date': row['ds'],
                'day_name': ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][row['day_of_week']],
                'actual': row['y'],
                'pred': adjusted_predictions[i],
                'ape': abs(row['y'] - adjusted_predictions[i]) / (row['y'] + 1e-10) * 100,
                'holiday': holiday['name'] if holiday else '',
                'lag_7': row.get('lag_7', 0),
                'rolling_mean_7': row.get('rolling_mean_7', 0),
                'rolling_std_7': row.get('rolling_std_7', 0),
                'days_since_major_festival': row.get('days_since_major_festival', 0)
            })

        worst_days = sorted(residuals, key=lambda x: x['ape'], reverse=True)[:3]

        fold_results.append({
            'fold_idx': fold_idx,
            'name': fold['name'],
            'train_end': fold['train_end'],
            'test_period': fold['name'],
            'mape': mape,
            'residuals': residuals,
            'worst_days': worst_days,
            'n_adjustments': len(adjustments)
        })

        logger.info(f"  MAPE: {mape:6.2f}%  ({len(adjustments)} holiday adjustments)")

    # Aggregate metrics
    mean_mape = np.mean([f['mape'] for f in fold_results])
    median_mape = np.median([f['mape'] for f in fold_results])
    worst_fold_mape = np.max([f['mape'] for f in fold_results])
    reference_mape = fold_results[2]['mape']  # Fold 3 = Dec 15-21

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("ROLLING VALIDATION SUMMARY")
    logger.info(f"{'='*80}\n")
    logger.info(f"Mean MAPE:    {mean_mape:6.2f}%")
    logger.info(f"Median MAPE:  {median_mape:6.2f}%")
    logger.info(f"Worst Fold:   {worst_fold_mape:6.2f}% (Fold {np.argmax([f['mape'] for f in fold_results]) + 1})")
    logger.info(f"Reference:    {reference_mape:6.2f}% (Dec 15-21, closest to original holdout)")

    # Detailed residual report
    if report_residuals:
        logger.info(f"\n{'='*80}")
        logger.info("WORST RESIDUAL DAYS (across all folds)")
        logger.info(f"{'='*80}\n")

        # Collect all residuals and sort
        all_residuals = []
        for fold in fold_results:
            all_residuals.extend(fold['residuals'])

        all_residuals_sorted = sorted(all_residuals, key=lambda x: x['ape'], reverse=True)[:10]

        for res in all_residuals_sorted:
            holiday_marker = f"🎄 {res['holiday']}" if res['holiday'] else ""
            logger.info(
                f"{res['date'].strftime('%Y-%m-%d')} ({res['day_name']}): "
                f"Actual {res['actual']:.0f}, Pred {res['pred']:.0f}, APE {res['ape']:.1f}% {holiday_marker}"
            )
            if res['lag_7'] > 0:
                logger.info(
                    f"  Features: lag_7={res['lag_7']:.0f}, "
                    f"rolling_mean_7={res['rolling_mean_7']:.0f}, "
                    f"rolling_std_7={res['rolling_std_7']:.0f}, "
                    f"days_since_major_festival={res['days_since_major_festival']:.0f}"
                )

    return {
        'fold_results': fold_results,
        'mean_mape': mean_mape,
        'median_mape': median_mape,
        'worst_fold_mape': worst_fold_mape,
        'reference_mape': reference_mape,
        'all_residuals': all_residuals if report_residuals else []
    }


def tune_xgboost_rolling(
    daily_df: pd.DataFrame,
    feature_cols: List[str],
    n_iter: int = 50
) -> Dict[str, Any]:
    """
    Tune XGBoost using rolling validation

    Returns best params based on mean MAPE across folds
    """
    from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
    from sklearn.metrics import make_scorer
    from xgboost import XGBRegressor

    logger.info(f"\n{'='*80}")
    logger.info("HYPERPARAMETER TUNING WITH ROLLING VALIDATION")
    logger.info(f"{'='*80}\n")

    # Custom scorer: negative MAPE (for maximization)
    def mape_scorer(y_true, y_pred):
        """Negative MAPE for maximization"""
        mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-10))) * 100
        return -mape  # Negative for maximization

    mape_scorer_sklearn = make_scorer(mape_scorer, greater_is_better=True)

    # Prepare data for tuning (use data up to Dec 21 for tuning, hold out Dec 22-31)
    train_df = daily_df[daily_df['ds'] <= datetime(2025, 12, 21)].copy()

    # Regularization-focused param grid
    param_distributions = {
        # Tree structure (keep shallow to avoid overfitting)
        'max_depth': [2, 3, 4],

        # Learning rate (lower = more regularization)
        'learning_rate': [0.03, 0.05, 0.1],

        # Number of trees (balance between learning and overfitting)
        'n_estimators': [50, 100, 150],

        # Sample regularization (prevent memorization)
        'subsample': [0.7, 0.9],
        'colsample_bytree': [0.7, 0.9],

        # Weight regularization (L2 penalty)
        'reg_lambda': [1, 5, 10],

        # Leaf regularization (prevent tiny splits)
        'min_child_weight': [1, 3, 5],

        # Fixed
        'random_state': [42],
        'verbosity': [0]
    }

    logger.info(f"Search space: {3*3*3*2*2*3*3} = 972 combinations")
    logger.info(f"Random search iterations: {n_iter}")
    logger.info(f"Cross-validation: TimeSeriesSplit(n_splits=3)\n")

    # Custom cross-validation: time series split for temporal data
    tscv = TimeSeriesSplit(n_splits=3)

    search = RandomizedSearchCV(
        XGBRegressor(),
        param_distributions=param_distributions,
        n_iter=n_iter,
        cv=tscv,
        scoring=mape_scorer_sklearn,
        n_jobs=-1,
        random_state=42,
        verbose=1
    )

    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['y']

    logger.info("Starting hyperparameter search...")
    search.fit(X_train, y_train)

    # Log best params
    logger.info(f"\n{'='*80}")
    logger.info("TUNING RESULTS")
    logger.info(f"{'='*80}\n")
    logger.info(f"Best CV MAPE: {-search.best_score_:.2f}%")
    logger.info(f"\nBest Parameters:")
    for param, value in sorted(search.best_params_.items()):
        logger.info(f"  {param:20s} = {value}")

    return {
        'best_params': search.best_params_,
        'best_cv_mape': -search.best_score_,
        'search_results': search.cv_results_
    }


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Ensemble Backtest with Rolling Validation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Original single holdout mode
  python ensemble_backtest.py

  # Rolling backtest mode
  python ensemble_backtest.py --rolling-backtest

  # Rolling backtest with detailed residuals
  python ensemble_backtest.py --rolling-backtest --report-residuals

  # Tune hyperparameters with rolling validation
  python ensemble_backtest.py --rolling-backtest --tune --n-iter 50

  # XGBoost only (faster)
  python ensemble_backtest.py --model xgb_only --rolling-backtest
        """
    )
    parser.add_argument(
        '--rolling-backtest',
        action='store_true',
        help='Use rolling-origin validation (4 folds) instead of single holdout'
    )
    parser.add_argument(
        '--tune',
        action='store_true',
        help='Run hyperparameter tuning with rolling validation'
    )
    parser.add_argument(
        '--n-iter',
        type=int,
        default=50,
        help='Number of hyperparameter search iterations (default: 50)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='ensemble',
        choices=['xgb_only', 'ensemble'],
        help='Model type to use (default: ensemble)'
    )
    parser.add_argument(
        '--report-residuals',
        action='store_true',
        help='Print detailed residual analysis'
    )

    args = parser.parse_args()

    logger.info("="*80)
    if args.rolling_backtest:
        logger.info("ROLLING-ORIGIN BACKTEST MODE")
    else:
        logger.info("ENSEMBLE BACKTEST WITH HOLIDAY POST-ADJUSTMENT")
    logger.info("="*80)

    try:
        # ===================================================================
        # STEP 1: Load and prepare data
        # ===================================================================
        lexis_file = "/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx"
        daily = load_lexis_data(lexis_file)
        daily = prepare_features(daily)

        feature_cols = [col for col in daily.columns if col not in ['ds', 'y']]

        # ===================================================================
        # ROLLING BACKTEST MODE
        # ===================================================================
        if args.rolling_backtest:
            # Tune hyperparameters first (if requested)
            if args.tune:
                tuning_results = tune_xgboost_rolling(
                    daily,
                    feature_cols,
                    n_iter=args.n_iter
                )
                best_params = tuning_results['best_params']

                logger.info(f"\n{'='*80}")
                logger.info("VALIDATING TUNED MODEL ON ALL FOLDS")
                logger.info(f"{'='*80}\n")
            else:
                # Use default params
                best_params = None

            # Run rolling backtest
            results = rolling_origin_backtest(
                daily,
                model_type=args.model,
                feature_cols=feature_cols,
                xgb_params=best_params,
                report_residuals=args.report_residuals
            )

            # Final summary
            logger.info(f"\n{'='*80}")
            logger.info("FINAL SUMMARY")
            logger.info(f"{'='*80}\n")

            mean_mape = results['mean_mape']
            if mean_mape <= 15:
                logger.info(f"🎯 Status: ✅ TARGET MET! ({mean_mape:.2f}% mean MAPE)")
            elif mean_mape <= 20:
                logger.info(f"🎯 Status: ⚠️  CLOSE ({mean_mape:.2f}% mean MAPE, need {mean_mape-15:.2f}% more)")
            else:
                logger.info(f"🎯 Status: 🔄 NEEDS WORK ({mean_mape:.2f}% mean MAPE, need {mean_mape-15:.2f}% improvement)")

            logger.info(f"\nMean MAPE across folds:   {results['mean_mape']:.2f}%")
            logger.info(f"Median MAPE:              {results['median_mape']:.2f}%")
            logger.info(f"Worst fold MAPE:          {results['worst_fold_mape']:.2f}%")
            logger.info(f"Reference (Dec 15-21):    {results['reference_mape']:.2f}%")

            logger.info(f"\n{'='*80}\n")
            sys.exit(0)

        # ===================================================================
        # ORIGINAL SINGLE HOLDOUT MODE (unchanged below)
        # ===================================================================

        # ===================================================================
        # STEP 2: Train-Validation-Test Split
        # ===================================================================
        # Training: Oct 1 - Nov 30 (60 days)
        # Validation: Dec 1 - Dec 14 (14 days)
        # Test: Dec 15 - Dec 31 (17 days)

        train_end = datetime(2025, 11, 30)
        val_end = datetime(2025, 12, 14)
        test_start = datetime(2025, 12, 15)

        train_df = daily[daily['ds'] <= train_end].copy()
        val_df = daily[(daily['ds'] > train_end) & (daily['ds'] <= val_end)].copy()
        test_df = daily[daily['ds'] >= test_start].copy()

        logger.info(f"\n{'='*80}")
        logger.info("DATA SPLIT:")
        logger.info(f"  Training:   {train_df['ds'].min().date()} to {train_df['ds'].max().date()} ({len(train_df)} days)")
        logger.info(f"  Validation: {val_df['ds'].min().date()} to {val_df['ds'].max().date()} ({len(val_df)} days)")
        logger.info(f"  Test:       {test_df['ds'].min().date()} to {test_df['ds'].max().date()} ({len(test_df)} days)")

        # ===================================================================
        # STEP 3: Train all models
        # ===================================================================
        logger.info(f"\n{'='*80}")
        logger.info("TRAINING MODELS")
        logger.info(f"{'='*80}\n")

        logger.info("Training XGBoost...")
        xgboost_model = train_xgboost(train_df, val_df, feature_cols)

        logger.info("Training Prophet...")
        prophet_model = train_prophet(train_df, val_df)

        logger.info("Training SARIMA...")
        sarima_model = train_sarima(train_df, val_df)

        models = [xgboost_model, prophet_model, sarima_model]
        models = [m for m in models if m is not None]

        logger.info(f"\n✓ Successfully trained {len(models)} models")

        # ===================================================================
        # STEP 4: Compute ensemble weights from validation data
        # ===================================================================
        logger.info(f"\n{'='*80}")
        logger.info("COMPUTING ENSEMBLE WEIGHTS (from validation accuracy)")
        logger.info(f"{'='*80}\n")

        weights = compute_ensemble_weights(models, val_df)

        logger.info("\nEnsemble Weights:")
        for name, weight in weights.items():
            logger.info(f"  {name:15s} {weight:.3f} ({weight*100:.1f}%)")

        # ===================================================================
        # STEP 5: Generate predictions on test set
        # ===================================================================
        logger.info(f"\n{'='*80}")
        logger.info("GENERATING TEST PREDICTIONS")
        logger.info(f"{'='*80}\n")

        y_test = test_df['y'].values
        results = {}

        # Individual models
        for model_dict in models:
            name = model_dict['name']
            predictions = predict_model(model_dict, test_df)

            if predictions is not None and len(predictions) == len(y_test):
                results[name] = predictions
                logger.info(f"✓ {name:15s} predictions: {len(predictions)} days")
            else:
                logger.warning(f"✗ {name:15s} prediction failed or length mismatch")

        # Ensemble
        ensemble_pred = create_ensemble_predictions(models, weights, test_df)
        results['Ensemble'] = ensemble_pred
        logger.info(f"✓ {'Ensemble':15s} predictions: {len(ensemble_pred)} days")

        # XGBoost + Holiday
        if 'XGBoost' in results:
            xgb_holiday_pred, xgb_adjustments = apply_holiday_adjustment(results['XGBoost'], test_df['ds'])
            results['XGBoost+Holiday'] = xgb_holiday_pred
            logger.info(f"✓ {'XGBoost+Holiday':15s} predictions: {len(xgb_holiday_pred)} days ({len(xgb_adjustments)} holidays)")

        # Ensemble + Holiday
        ensemble_holiday_pred, ens_adjustments = apply_holiday_adjustment(ensemble_pred, test_df['ds'])
        results['Ensemble+Holiday'] = ensemble_holiday_pred
        logger.info(f"✓ {'Ensemble+Holiday':15s} predictions: {len(ensemble_holiday_pred)} days ({len(ens_adjustments)} holidays)")

        # ===================================================================
        # STEP 6: Calculate metrics for all variants
        # ===================================================================
        logger.info(f"\n{'='*80}")
        logger.info("TEST SET METRICS (17 days)")
        logger.info(f"{'='*80}\n")

        metrics_table = []
        for name, predictions in sorted(results.items()):
            if len(predictions) == len(y_test):
                metrics = calculate_metrics(y_test, predictions)
                metrics_table.append({
                    'Model': name,
                    'MAPE': metrics['mape'],
                    'MAE': metrics['mae'],
                    'RMSE': metrics['rmse'],
                    'R²': metrics['r2']
                })

        # Print results table
        logger.info(f"{'Model':<25s} {'MAPE':<10s} {'MAE':<10s} {'RMSE':<10s} {'R²':<10s}")
        logger.info("-" * 80)
        for row in metrics_table:
            logger.info(f"{row['Model']:<25s} {row['MAPE']:>6.2f}%    {row['MAE']:>6.2f}    {row['RMSE']:>6.2f}    {row['R²']:>6.4f}")

        # ===================================================================
        # STEP 7: Per-day residual analysis for Ensemble+Holiday
        # ===================================================================
        logger.info(f"\n{'='*80}")
        logger.info("PER-DAY RESIDUAL ANALYSIS (Ensemble+Holiday)")
        logger.info(f"{'='*80}\n")

        best_pred = results['Ensemble+Holiday']
        residuals = []

        for i, (idx, row) in enumerate(test_df.iterrows()):
            actual = row['y']
            pred = best_pred[i]
            error = actual - pred
            error_pct = abs(error) / (actual + 1e-10) * 100

            holiday = IndianHolidayCalendar.get_holiday(row['ds'])
            holiday_name = holiday['name'] if holiday else ''

            residuals.append({
                'date': row['ds'],
                'day_name': ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][row['day_of_week']],
                'actual': actual,
                'pred': pred,
                'error': error,
                'error_pct': error_pct,
                'holiday': holiday_name
            })

        residuals_df = pd.DataFrame(residuals)
        residuals_df = residuals_df.sort_values('error_pct', ascending=False)

        logger.info("Top 10 Worst Prediction Days:")
        logger.info("-" * 80)
        for i, row in residuals_df.head(10).iterrows():
            holiday_marker = f"🎄 {row['holiday']}" if row['holiday'] else ""
            logger.info(f"{row['date'].strftime('%Y-%m-%d')} ({row['day_name']}): "
                       f"Actual {row['actual']:.0f}, Pred {row['pred']:.0f}, "
                       f"Error {row['error_pct']:.1f}% {holiday_marker}")

        # ===================================================================
        # STEP 8: Holiday adjustment impact
        # ===================================================================
        if ens_adjustments:
            logger.info(f"\n{'='*80}")
            logger.info(f"HOLIDAY ADJUSTMENTS APPLIED ({len(ens_adjustments)} days)")
            logger.info(f"{'='*80}\n")

            for adj in ens_adjustments:
                logger.info(f"{adj['date'].strftime('%Y-%m-%d')} - {adj['holiday']} ({adj['impact']:+.0%})")
                logger.info(f"  {adj['original']:.0f} → {adj['adjusted']:.0f}")

        # ===================================================================
        # STEP 9: Final summary
        # ===================================================================
        logger.info(f"\n{'='*80}")
        logger.info("SUMMARY")
        logger.info(f"{'='*80}\n")

        best_model = min(metrics_table, key=lambda x: x['MAPE'])
        logger.info(f"Best Model: {best_model['Model']}")
        logger.info(f"  MAPE: {best_model['MAPE']:.2f}%")
        logger.info(f"  MAE:  {best_model['MAE']:.2f}")
        logger.info(f"  RMSE: {best_model['RMSE']:.2f}")
        logger.info(f"  R²:   {best_model['R²']:.4f}")

        if best_model['MAPE'] <= 15:
            logger.info(f"\n🎯 Status: ✅ TARGET MET! (10-15% MAPE)")
        elif best_model['MAPE'] <= 25:
            logger.info(f"\n🎯 Status: ⚠️  GOOD (close to target, need {best_model['MAPE']-15:.2f}% more improvement)")
        else:
            logger.info(f"\n🎯 Status: 🔄 NEEDS MORE WORK (need {best_model['MAPE']-15:.2f}% improvement)")

        logger.info(f"\n{'='*80}\n")

        sys.exit(0)

    except Exception as e:
        logger.error(f"\n✗ Backtest failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
