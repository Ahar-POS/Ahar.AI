"""
v3.0 — Item-Level Daily Sales Prediction Model

Self-contained training script for predicting next-day quantity sold per item
for top 15 menu items at Lexi's Gourmet Sandwiches (Gurgaon cloud kitchen).

Model: LightGBM with Optuna hyperparameter tuning.
Data: Oct 1 – Dec 31, 2025 (91 days of Lexis POS data + weather + discount data)

Key design decisions:
- Log1p target transform (count data is better predicted in log space)
- Per-item outlier clipping at 95th percentile
- Retrain on train+val after tuning, evaluate on held-out test
- SMAPE instead of MAPE (handles low counts better)
"""

import pandas as pd
import numpy as np
import json
import joblib
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any

import lightgbm as lgb
import optuna
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Suppress optuna logging during tuning
optuna.logging.set_verbosity(optuna.logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# PATHS
# ============================================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent
LEXIS_FILE = PROJECT_ROOT / "lexis_real_data" / "Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx"
WEATHER_FILE = PROJECT_ROOT / "data" / "gurgaon_weather_oct_dec_2025.xlsx"
DISCOUNT_FILE = PROJECT_ROOT / "data" / "daily_discount_features.csv"
ITEMS_CATALOG = PROJECT_ROOT / "lexis_real_data" / "items_331832_2026_03_07_11_54_37.xlsx"

TOP_N_ITEMS = 15
VERSION = "v3.0"

# ============================================================================
# HOLIDAYS (Oct-Dec 2025 Gurgaon)
# ============================================================================
HOLIDAYS = {
    '2025-10-02': 'Gandhi Jayanti',
    '2025-10-12': 'Dussehra',
    '2025-10-20': 'Karwa Chauth',
    '2025-11-01': 'Diwali',
    '2025-11-02': 'Govardhan Puja',
    '2025-11-03': 'Bhai Dooj',
    '2025-11-05': 'Chhath Puja',
    '2025-11-15': 'Guru Nanak Jayanti',
    '2025-12-25': 'Christmas',
    '2025-12-31': 'New Years Eve',
}


# ============================================================================
# 1. DATA LOADING
# ============================================================================
def load_sales_data(lexis_file: Path) -> pd.DataFrame:
    """
    Load and parse Lexis POS export into clean order-line DataFrame.
    Returns: DataFrame with [date, item_name, qty] per order-line.
    """
    logger.info(f"Loading sales data from: {lexis_file}")

    df = pd.read_excel(lexis_file, header=None)

    # Data starts at row 5 (0-indexed); the first 5 rows are metadata/header
    data = df.iloc[5:].copy()
    cols = [
        'Date', 'Timestamp', 'InvoiceNo', 'PaymentType', 'OrderType',
        'Platform', 'ItemName', 'Price', 'Qty', 'SubTotal', 'Discount',
        'Tax', 'FinalTotal', 'Status', 'TableNo', 'ServerName', 'Covers',
        'Variation', 'Category', 'GroupName', 'HSN', 'Phone', 'CustomerName',
        'Address', 'GST', 'AssignTo', 'NonTaxable', 'SGSTRate', 'SGSTAmount',
        'CGSTRate', 'CGSTAmount'
    ]
    data.columns = cols

    # Remove summary/header rows
    data = data[~data['Date'].isin(['Total', 'Date', None])].copy()
    data = data.dropna(subset=['Date']).copy()
    data = data[data['ItemName'].notna()].copy()

    # Parse types
    data['Date'] = pd.to_datetime(data['Date'])
    data['Qty'] = pd.to_numeric(data['Qty'], errors='coerce').fillna(0).astype(int)
    data['Price'] = pd.to_numeric(data['Price'], errors='coerce').fillna(0)

    logger.info(f"  Loaded {len(data):,} order-lines")
    logger.info(f"  Date range: {data['Date'].min().date()} to {data['Date'].max().date()}")
    logger.info(f"  Unique items: {data['ItemName'].nunique()}")
    logger.info(f"  Unique invoices (orders): {data['InvoiceNo'].nunique()}")

    return data


def aggregate_daily_item(data: pd.DataFrame, top_n: int = TOP_N_ITEMS) -> Tuple[pd.DataFrame, List[str]]:
    """
    Aggregate order-lines to daily quantity per item.
    Filter to top N items by total volume.
    Fill missing days with qty=0.

    Returns: (daily_item_df, top_items_list)
    """
    # Daily aggregation
    daily = data.groupby(['Date', 'ItemName'])['Qty'].sum().reset_index()
    daily.columns = ['ds', 'item_name', 'qty']

    # Find top N items by total quantity
    item_totals = daily.groupby('item_name')['qty'].sum().sort_values(ascending=False)
    top_items = item_totals.head(top_n).index.tolist()

    total_qty = item_totals.sum()
    top_qty = item_totals.head(top_n).sum()
    logger.info(f"\n  Top {top_n} items cover {top_qty/total_qty*100:.1f}% of total volume ({top_qty:.0f}/{total_qty:.0f})")

    # Filter to top items only
    daily = daily[daily['item_name'].isin(top_items)].copy()

    # Create full date × item grid (fill missing days with qty=0)
    all_dates = pd.date_range(daily['ds'].min(), daily['ds'].max(), freq='D')
    full_grid = pd.MultiIndex.from_product(
        [all_dates, top_items], names=['ds', 'item_name']
    ).to_frame(index=False)

    daily = full_grid.merge(daily, on=['ds', 'item_name'], how='left')
    daily['qty'] = daily['qty'].fillna(0).astype(int)

    # Clip per-item outliers at 95th percentile (Nov 29 spike etc.)
    for item in top_items:
        mask = daily['item_name'] == item
        q95 = daily.loc[mask, 'qty'].quantile(0.95)
        n_clipped = (daily.loc[mask, 'qty'] > q95).sum()
        if n_clipped > 0:
            daily.loc[mask, 'qty'] = daily.loc[mask, 'qty'].clip(upper=q95)
            logger.info(f"  Clipped {n_clipped} outlier days for {item[:40]} (cap={q95:.0f})")

    logger.info(f"  Full grid: {len(all_dates)} days × {len(top_items)} items = {len(daily):,} records")

    # Print top items
    logger.info(f"\n  Top {top_n} items:")
    for i, item in enumerate(top_items, 1):
        total = item_totals[item]
        avg = total / len(all_dates)
        logger.info(f"    {i:2d}. {item[:50]:50s} total={total:>5.0f}  avg={avg:>4.1f}/day")

    return daily, top_items


def load_weather(weather_file: Path) -> pd.DataFrame:
    """Load daily weather data for Gurgaon."""
    logger.info(f"\n  Loading weather: {weather_file}")
    weather = pd.read_excel(weather_file)

    # Clean: drop metadata/note rows
    weather = weather[weather['date'].notna()].copy()
    weather['ds'] = pd.to_datetime(weather['date'], errors='coerce')
    weather = weather[weather['ds'].notna()].copy()

    # Select useful columns
    keep_cols = ['ds', 'temp_max', 'temp_min', 'temp_avg', 'precipitation_mm',
                 'humidity_avg', 'wind_speed_kmh', 'is_rainy']
    weather = weather[[c for c in keep_cols if c in weather.columns]].copy()

    # Ensure numeric types
    for col in weather.columns:
        if col != 'ds':
            weather[col] = pd.to_numeric(weather[col], errors='coerce').fillna(0)

    logger.info(f"  ✓ Weather: {len(weather)} days")
    return weather


def load_discounts(discount_file: Path) -> pd.DataFrame:
    """Load daily discount features."""
    logger.info(f"  Loading discounts: {discount_file}")
    discounts = pd.read_csv(discount_file)
    discounts['ds'] = pd.to_datetime(discounts['ds'])

    keep_cols = ['ds', 'discount_penetration', 'discount_avg_pct',
                 'is_high_discount_day', 'is_medium_discount_day']
    discounts = discounts[[c for c in keep_cols if c in discounts.columns]].copy()

    logger.info(f"  ✓ Discounts: {len(discounts)} days")
    return discounts


def load_item_catalog(catalog_file: Path) -> pd.DataFrame:
    """Load item catalog for static item features."""
    logger.info(f"  Loading catalog: {catalog_file}")
    catalog = pd.read_excel(catalog_file)

    # Keep useful columns
    catalog = catalog[['Name', 'Category', 'Price', 'Attributes']].copy()
    catalog.columns = ['item_name', 'category', 'price', 'attribute']

    # Clean
    catalog['is_veg'] = (catalog['attribute'] == 'veg').astype(int)
    catalog['price'] = pd.to_numeric(catalog['price'], errors='coerce').fillna(0)

    logger.info(f"  ✓ Catalog: {len(catalog)} items")
    return catalog


# ============================================================================
# 2. FEATURE ENGINEERING
# ============================================================================
def add_item_features(df: pd.DataFrame, top_items: List[str], catalog: pd.DataFrame) -> pd.DataFrame:
    """Add static item-level features."""
    # Item ID (integer label encoding)
    item_to_id = {item: i for i, item in enumerate(sorted(top_items))}
    df['item_id'] = df['item_name'].map(item_to_id)

    # Category encoding
    cat_map = catalog.set_index('item_name')['category'].to_dict()
    df['item_category_str'] = df['item_name'].map(cat_map).fillna('Unknown')
    categories = sorted(df['item_category_str'].unique())
    cat_to_id = {c: i for i, c in enumerate(categories)}
    df['item_category'] = df['item_category_str'].map(cat_to_id)

    # Price from catalog
    price_map = catalog.set_index('item_name')['price'].to_dict()
    df['item_price'] = df['item_name'].map(price_map).fillna(0)

    # Veg/non-veg
    veg_map = catalog.set_index('item_name')['is_veg'].to_dict()
    df['is_veg'] = df['item_name'].map(veg_map).fillna(0).astype(int)

    return df


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add per-item lag and rolling features.
    CRITICAL: shift by 1 to avoid leakage (we only know yesterday's data).
    NaN filled with 0 (not mean — that's leakage).
    """
    df = df.sort_values(['item_name', 'ds']).copy()

    lag_cols = {}
    for lag in [1, 2, 3, 7]:
        lag_cols[f'lag_{lag}'] = lag

    for item in df['item_name'].unique():
        mask = df['item_name'] == item
        item_series = df.loc[mask, 'qty']

        # Lag features
        for col_name, lag_val in lag_cols.items():
            df.loc[mask, col_name] = item_series.shift(lag_val).values

        # Rolling features (applied on shifted series to avoid leakage)
        shifted = item_series.shift(1)
        df.loc[mask, 'rolling_mean_3'] = shifted.rolling(3, min_periods=1).mean().values
        df.loc[mask, 'rolling_mean_7'] = shifted.rolling(7, min_periods=1).mean().values
        df.loc[mask, 'rolling_std_7'] = shifted.rolling(7, min_periods=1).std().fillna(0).values
        df.loc[mask, 'ewm_7'] = shifted.ewm(span=7, min_periods=1).mean().values

    # Fill NaN with 0 (first few days have no history — using 0 is honest)
    for col in ['lag_1', 'lag_2', 'lag_3', 'lag_7', 'rolling_mean_3', 'rolling_mean_7',
                'rolling_std_7', 'ewm_7']:
        df[col] = df[col].fillna(0)

    return df


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar / temporal features."""
    df['day_of_week'] = df['ds'].dt.dayofweek  # Mon=0
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['is_friday'] = (df['day_of_week'] == 4).astype(int)
    df['day_of_month'] = df['ds'].dt.day
    df['week_of_month'] = (df['ds'].dt.day - 1) // 7 + 1
    df['month'] = df['ds'].dt.month

    # Payday features (1st-5th and 25th-31st of month)
    df['is_payday_period'] = ((df['day_of_month'] <= 5) | (df['day_of_month'] >= 25)).astype(int)

    return df


def add_holiday_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add holiday flags and distance features."""
    holiday_dates = [pd.to_datetime(d) for d in HOLIDAYS.keys()]

    df['is_holiday'] = df['ds'].isin(holiday_dates).astype(int)

    # Days since last holiday
    def days_since_holiday(date):
        past_holidays = [h for h in holiday_dates if h <= date]
        if past_holidays:
            return (date - max(past_holidays)).days
        return 30  # Default: far from any holiday
    df['days_since_holiday'] = df['ds'].apply(days_since_holiday)

    return df


def add_weather_features(df: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Merge weather and add derived features."""
    df = df.merge(weather, on='ds', how='left')

    # Fill missing weather with medians
    for col in ['temp_avg', 'temp_max', 'temp_min', 'precipitation_mm',
                'humidity_avg', 'wind_speed_kmh', 'is_rainy']:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median() if df[col].median() else 0)

    # Derived: is it a cold day? (Gurgaon gets cold in Dec, drives delivery)
    if 'temp_avg' in df.columns:
        df['is_cold_day'] = (df['temp_avg'] < 15).astype(int)

    return df


def add_discount_features(df: pd.DataFrame, discounts: pd.DataFrame) -> pd.DataFrame:
    """Merge discount features."""
    df = df.merge(discounts, on='ds', how='left')

    for col in ['discount_penetration', 'discount_avg_pct',
                'is_high_discount_day', 'is_medium_discount_day']:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    return df


def add_store_level_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add cross-item store-level signals."""
    # Total store qty per day (across all top-15 items)
    daily_store = df.groupby('ds')['qty'].sum().reset_index()
    daily_store.columns = ['ds', 'store_total_qty']

    # Shift by 1 (yesterday's store total — to avoid leakage)
    daily_store = daily_store.sort_values('ds')
    daily_store['store_qty_yesterday'] = daily_store['store_total_qty'].shift(1).fillna(0)
    daily_store['store_rolling_mean_7'] = daily_store['store_total_qty'].shift(1).rolling(7, min_periods=1).mean().fillna(0)

    # Merge back (drop the current-day total to avoid leakage)
    df = df.merge(daily_store[['ds', 'store_qty_yesterday', 'store_rolling_mean_7']], on='ds', how='left')
    df['store_qty_yesterday'] = df['store_qty_yesterday'].fillna(0)
    df['store_rolling_mean_7'] = df['store_rolling_mean_7'].fillna(0)

    return df


def build_all_features(
    daily: pd.DataFrame,
    top_items: List[str],
    catalog: pd.DataFrame,
    weather: pd.DataFrame,
    discounts: pd.DataFrame
) -> pd.DataFrame:
    """
    Full feature engineering pipeline.
    Returns DataFrame with all features and target 'qty'.
    """
    logger.info("\nFeature Engineering:")

    df = daily.copy()

    df = add_item_features(df, top_items, catalog)
    logger.info("  ✓ Item features (id, category, price, veg)")

    df = add_lag_features(df)
    logger.info("  ✓ Lag features (lag_1/2/3/7, rolling_mean_3/7, rolling_std_7, ewm_7)")

    df = add_temporal_features(df)
    logger.info("  ✓ Temporal features (dow, weekend, friday, dom, wom, month, payday)")

    df = add_holiday_features(df)
    logger.info("  ✓ Holiday features (is_holiday, days_since_holiday)")

    df = add_weather_features(df, weather)
    logger.info("  ✓ Weather features (temp, rain, humidity, wind, cold_day)")

    df = add_discount_features(df, discounts)
    logger.info("  ✓ Discount features (penetration, avg_pct, high/medium)")

    df = add_store_level_features(df)
    logger.info("  ✓ Store-level features (store_qty_yesterday, store_rolling_mean_7)")

    return df


# ============================================================================
# 3. FEATURE COLUMNS
# ============================================================================
FEATURE_COLS = [
    # Item identity
    'item_id', 'item_category', 'item_price', 'is_veg',
    # Lags (per-item)
    'lag_1', 'lag_2', 'lag_3', 'lag_7',
    'rolling_mean_3', 'rolling_mean_7', 'rolling_std_7', 'ewm_7',
    # Temporal
    'day_of_week', 'is_weekend', 'day_of_month',
    # Domain
    'is_payday_period', 'days_since_holiday',
    # Weather (only features that showed importance)
    'temp_avg', 'humidity_avg', 'wind_speed_kmh',
    # Discounts
    'discount_penetration', 'discount_avg_pct',
    # Store-level
    'store_qty_yesterday', 'store_rolling_mean_7',
]

TARGET = 'qty'


# ============================================================================
# 4. TRAIN / VAL / TEST SPLIT
# ============================================================================
def split_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Time-based train/val/test split.
    Train: Oct 1 – Nov 23 (54 days)
    Val:   Nov 24 – Dec 14 (21 days)
    Test:  Dec 15 – Dec 31 (17 days)
    """
    train_end = pd.to_datetime('2025-11-23')
    val_end = pd.to_datetime('2025-12-14')

    train = df[df['ds'] <= train_end].copy()
    val = df[(df['ds'] > train_end) & (df['ds'] <= val_end)].copy()
    test = df[df['ds'] > val_end].copy()

    logger.info(f"\nData Split:")
    logger.info(f"  Train: {len(train):,} records ({train['ds'].min().date()} to {train['ds'].max().date()}) — {train['ds'].nunique()} days")
    logger.info(f"  Val:   {len(val):,} records ({val['ds'].min().date()} to {val['ds'].max().date()}) — {val['ds'].nunique()} days")
    logger.info(f"  Test:  {len(test):,} records ({test['ds'].min().date()} to {test['ds'].max().date()}) — {test['ds'].nunique()} days")

    return train, val, test


# ============================================================================
# 5. MODEL TRAINING + OPTUNA TUNING
# ============================================================================
def objective(trial, X_train, y_train, X_val, y_val):
    """Optuna objective: minimize validation MAE on log1p-transformed target."""
    params = {
        'objective': 'regression',
        'metric': 'mae',
        'boosting_type': 'gbdt',
        'verbosity': -1,
        'n_jobs': -1,

        'num_leaves': trial.suggest_int('num_leaves', 15, 63),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15),
        'n_estimators': trial.suggest_int('n_estimators', 100, 800),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 30),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.6, 1.0),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.6, 1.0),
        'bagging_freq': trial.suggest_int('bagging_freq', 1, 7),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-3, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-3, 10.0, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 8),
    }

    model = lgb.LGBMRegressor(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )

    # Predict in log space, then convert back for MAE
    preds_log = model.predict(X_val)
    preds = np.expm1(np.maximum(preds_log, 0))
    preds = np.maximum(preds, 0)
    y_val_orig = np.expm1(y_val)
    mae = mean_absolute_error(y_val_orig, preds)
    return mae


def train_model(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    feature_cols: List[str],
    n_trials: int = 100
) -> Tuple[lgb.LGBMRegressor, Dict]:
    """
    Train LightGBM with Optuna hyperparameter tuning.
    Strategy: tune on train→val, then retrain on train+val for final test eval.
    Returns: (best_model, best_params)
    """
    # Log1p transform target (count data is better predicted in log space)
    logger.info(f"\n  Applying log1p target transform...")
    logger.info(f"  Target range before: [{train[TARGET].min():.0f}, {train[TARGET].max():.0f}]")

    # We need to keep original qty for evaluation later
    train = train.copy()
    val = val.copy()
    train['qty_orig'] = train[TARGET].copy()
    val['qty_orig'] = val[TARGET].copy()
    train[TARGET] = np.log1p(train[TARGET])
    val[TARGET] = np.log1p(val[TARGET])

    logger.info(f"\nHyperparameter Tuning ({n_trials} Optuna trials)...")

    X_train = train[feature_cols].fillna(0)
    y_train = train[TARGET]
    X_val = val[feature_cols].fillna(0)
    y_val = val[TARGET]

    study = optuna.create_study(direction='minimize', study_name='lgbm_sales')
    study.optimize(
        lambda trial: objective(trial, X_train, y_train, X_val, y_val),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    best_params = study.best_params
    best_val_mae = study.best_value

    logger.info(f"  Best trial: MAE = {best_val_mae:.3f} (on original scale)")
    logger.info(f"  Best params: {json.dumps(best_params, indent=4)}")

    # Retrain on TRAIN + VAL combined with best params for final test eval
    logger.info(f"\n  Retraining on train+val combined ({len(train)+len(val)} records)...")

    final_params = {
        'objective': 'regression',
        'metric': 'mae',
        'boosting_type': 'gbdt',
        'verbosity': -1,
        'n_jobs': -1,
        **best_params,
    }

    # Combine train + val for final model
    train_val = pd.concat([train, val], ignore_index=True)
    X_train_val = train_val[feature_cols].fillna(0)
    y_train_val = train_val[TARGET]  # already log1p transformed

    # For early stopping, use val as monitoring set
    model = lgb.LGBMRegressor(**final_params)
    model.fit(
        X_train_val, y_train_val,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )

    # Validation metrics (in original space)
    val_pred_log = model.predict(X_val)
    val_pred = np.expm1(np.maximum(val_pred_log, 0))
    val_pred = np.maximum(val_pred, 0)
    val_mae = mean_absolute_error(val['qty_orig'], val_pred)
    val_rmse = np.sqrt(mean_squared_error(val['qty_orig'], val_pred))
    logger.info(f"  Final val MAE (original scale):  {val_mae:.3f}")
    logger.info(f"  Final val RMSE (original scale): {val_rmse:.3f}")

    return model, final_params


# ============================================================================
# 6. EVALUATION
# ============================================================================
def evaluate_model(
    model: lgb.LGBMRegressor,
    test: pd.DataFrame,
    feature_cols: List[str],
    top_items: List[str],
    split_name: str = "Test"
) -> Dict[str, Any]:
    """
    Evaluate model on a dataset. Returns detailed per-item metrics.
    """
    X = test[feature_cols].fillna(0)
    y = test[TARGET].values

    # Predict in log space, convert back
    preds_log = model.predict(X)
    preds = np.expm1(np.maximum(preds_log, 0))
    preds = np.maximum(preds, 0)
    preds_rounded = np.round(preds).astype(int)

    # Overall metrics
    overall_mae = mean_absolute_error(y, preds_rounded)
    overall_rmse = np.sqrt(mean_squared_error(y, preds_rounded))

    # SMAPE (symmetric, handles low counts better than MAPE)
    # SMAPE = 200 * |actual - pred| / (|actual| + |pred|), capped at 200%
    denominator = np.abs(y) + np.abs(preds) + 1e-10
    overall_smape = np.mean(200 * np.abs(y - preds) / denominator)

    # MAPE only on days with actual >= 2 (avoid extreme inflation from low counts)
    nonzero_mask = y >= 2
    if nonzero_mask.sum() > 0:
        overall_mape = np.mean(np.abs((y[nonzero_mask] - preds[nonzero_mask]) / y[nonzero_mask])) * 100
    else:
        overall_mape = float('nan')

    logger.info(f"\n{'='*80}")
    logger.info(f"{split_name} SET EVALUATION")
    logger.info(f"{'='*80}")
    logger.info(f"  Overall MAE:  {overall_mae:.3f}")
    logger.info(f"  Overall RMSE: {overall_rmse:.3f}")
    logger.info(f"  Overall SMAPE: {overall_smape:.2f}%")
    logger.info(f"  Overall MAPE: {overall_mape:.2f}% (on days with actual ≥ 2)")

    # Per-item metrics
    test_eval = test.copy()
    test_eval['pred'] = preds_rounded
    test_eval['pred_raw'] = preds

    item_metrics = []
    logger.info(f"\n  {'Item':<50s} {'MAE':>6s} {'RMSE':>6s} {'SMAPE':>7s} {'MAPE':>7s} {'Volume':>8s} {'Avg/Day':>8s}")
    logger.info(f"  {'-'*95}")

    for item in top_items:
        item_data = test_eval[test_eval['item_name'] == item]
        if len(item_data) == 0:
            continue

        y_i = item_data['qty'].values.astype(float)
        p_i = item_data['pred_raw'].values

        mae_i = mean_absolute_error(y_i, np.round(p_i))
        rmse_i = np.sqrt(mean_squared_error(y_i, np.round(p_i)))

        # SMAPE per item
        denom_i = np.abs(y_i) + np.abs(p_i) + 1e-10
        smape_i = np.mean(200 * np.abs(y_i - p_i) / denom_i)

        nonzero = y_i >= 2
        mape_i = np.mean(np.abs((y_i[nonzero] - p_i[nonzero]) / y_i[nonzero])) * 100 if nonzero.sum() > 0 else float('nan')

        total_vol = y_i.sum()
        avg_day = y_i.mean()

        item_metrics.append({
            'item': item,
            'mae': mae_i,
            'rmse': rmse_i,
            'smape': smape_i,
            'mape': mape_i,
            'total_volume': int(total_vol),
            'avg_per_day': avg_day,
            'n_days': len(item_data),
        })

        logger.info(f"  {item[:50]:<50s} {mae_i:>6.2f} {rmse_i:>6.2f} {smape_i:>6.1f}% {mape_i:>6.1f}% {int(total_vol):>8d} {avg_day:>8.1f}")

    # Weighted SMAPE by volume
    item_df = pd.DataFrame(item_metrics)
    if len(item_df) > 0:
        weighted_smape = (item_df['smape'] * item_df['total_volume']).sum() / item_df['total_volume'].sum()
        valid_mape = item_df[item_df['mape'].notna()]
        weighted_mape = (valid_mape['mape'] * valid_mape['total_volume']).sum() / valid_mape['total_volume'].sum() if len(valid_mape) > 0 else float('nan')
    else:
        weighted_smape = float('nan')
        weighted_mape = float('nan')

    logger.info(f"\n  Weighted SMAPE (by volume): {weighted_smape:.2f}%")
    logger.info(f"  Weighted MAPE (by volume, actual≥2): {weighted_mape:.2f}%")

    return {
        'overall_mae': overall_mae,
        'overall_rmse': overall_rmse,
        'overall_smape': overall_smape,
        'overall_mape': overall_mape,
        'weighted_smape': weighted_smape,
        'weighted_mape': weighted_mape,
        'per_item': item_metrics,
    }


# ============================================================================
# 7. FEATURE IMPORTANCE
# ============================================================================
def analyze_features(model: lgb.LGBMRegressor, feature_cols: List[str]) -> pd.DataFrame:
    """Print and return feature importance."""
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_,
    }).sort_values('importance', ascending=False)

    logger.info(f"\nFeature Importance (top 20):")
    for _, row in importance.head(20).iterrows():
        bar = '█' * int(row['importance'] / importance['importance'].max() * 30)
        logger.info(f"  {row['feature']:30s} {row['importance']:>5d}  {bar}")

    zero_importance = importance[importance['importance'] == 0]
    if len(zero_importance) > 0:
        logger.info(f"\n  ⚠️  {len(zero_importance)} features with zero importance: {', '.join(zero_importance['feature'].tolist())}")

    return importance


# ============================================================================
# 8. SAVE MODEL
# ============================================================================
def save_model(
    model: lgb.LGBMRegressor,
    params: Dict,
    feature_cols: List[str],
    top_items: List[str],
    test_metrics: Dict,
    val_metrics: Dict,
    feature_importance: pd.DataFrame,
    version: str = VERSION,
):
    """Save model and artifacts to models/v3.0/"""
    model_dir = PROJECT_ROOT / 'models' / version
    model_dir.mkdir(parents=True, exist_ok=True)

    # Model
    joblib.dump(model, model_dir / 'model.joblib', compress=3)
    logger.info(f"\n  Saved model: {model_dir / 'model.joblib'}")

    # Features
    with open(model_dir / 'features.json', 'w') as f:
        json.dump(feature_cols, f, indent=2)

    # Item mapping
    item_mapping = {item: i for i, item in enumerate(sorted(top_items))}
    with open(model_dir / 'item_mapping.json', 'w') as f:
        json.dump(item_mapping, f, indent=2)

    # Feature importance
    feature_importance.to_csv(model_dir / 'feature_importance.csv', index=False)

    # Metadata
    metadata = {
        'version': version,
        'description': 'LightGBM item-level daily sales prediction (top 15 items)',
        'model_type': 'LightGBM',
        'created_at': datetime.now().isoformat(),
        'n_items': len(top_items),
        'n_features': len(feature_cols),
        'top_items': top_items,
        'hyperparams': {k: v for k, v in params.items() if k not in ['objective', 'metric', 'boosting_type', 'verbosity', 'n_jobs']},
        'train_split': {'start': '2025-10-01', 'end': '2025-11-23', 'days': 54},
        'val_split': {'start': '2025-11-24', 'end': '2025-12-14', 'days': 21},
        'test_split': {'start': '2025-12-15', 'end': '2025-12-31', 'days': 17},
        'test_metrics': {
            'overall_mae': round(test_metrics['overall_mae'], 3),
            'overall_rmse': round(test_metrics['overall_rmse'], 3),
            'overall_smape': round(test_metrics['overall_smape'], 2),
            'overall_mape': round(test_metrics['overall_mape'], 2),
            'weighted_smape': round(test_metrics['weighted_smape'], 2),
            'weighted_mape': round(test_metrics['weighted_mape'], 2),
        },
        'val_metrics': {
            'overall_mae': round(val_metrics['overall_mae'], 3),
            'overall_rmse': round(val_metrics['overall_rmse'], 3),
            'overall_smape': round(val_metrics['overall_smape'], 2),
            'overall_mape': round(val_metrics['overall_mape'], 2),
            'weighted_smape': round(val_metrics['weighted_smape'], 2),
            'weighted_mape': round(val_metrics['weighted_mape'], 2),
        },
        'per_item_test_metrics': [
            {
                'item': m['item'],
                'mae': round(m['mae'], 2),
                'rmse': round(m['rmse'], 2),
                'smape': round(m['smape'], 2),
                'mape': round(m['mape'], 2) if not np.isnan(m['mape']) else None,
                'total_volume': m['total_volume'],
            }
            for m in test_metrics['per_item']
        ],
        'top_10_features': feature_importance.head(10)['feature'].tolist(),
    }

    with open(model_dir / 'metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"  Saved metadata: {model_dir / 'metadata.json'}")

    # Update latest symlink
    latest_path = PROJECT_ROOT / 'models' / 'latest'
    if latest_path.exists() or latest_path.is_symlink():
        latest_path.unlink()
    latest_path.symlink_to(version)
    logger.info(f"  Updated models/latest → {version}")

    logger.info(f"\n  ✓ All artifacts saved to: {model_dir}")


# ============================================================================
# MAIN
# ============================================================================
def main():
    logger.info("=" * 80)
    logger.info("v3.0 — ITEM-LEVEL DAILY SALES PREDICTION MODEL")
    logger.info("=" * 80)

    # ------------------------------------------------------------------
    # 1. LOAD DATA
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: DATA LOADING")
    logger.info("=" * 80)

    raw_data = load_sales_data(LEXIS_FILE)
    daily, top_items = aggregate_daily_item(raw_data, TOP_N_ITEMS)
    weather = load_weather(WEATHER_FILE)
    discounts = load_discounts(DISCOUNT_FILE)
    catalog = load_item_catalog(ITEMS_CATALOG)

    # ------------------------------------------------------------------
    # 2. FEATURE ENGINEERING
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: FEATURE ENGINEERING")
    logger.info("=" * 80)

    featured = build_all_features(daily, top_items, catalog, weather, discounts)

    # Verify no features are missing
    missing_features = [c for c in FEATURE_COLS if c not in featured.columns]
    if missing_features:
        logger.error(f"  Missing features: {missing_features}")
        # Remove missing features from FEATURE_COLS
        for f in missing_features:
            FEATURE_COLS.remove(f)
            logger.info(f"  Removed missing feature: {f}")

    # Check for any NaN in features
    feature_nulls = featured[FEATURE_COLS].isnull().sum()
    null_features = feature_nulls[feature_nulls > 0]
    if len(null_features) > 0:
        logger.warning(f"  Features with NaN: {dict(null_features)}")
        logger.info("  Filling NaN with 0...")
        featured[FEATURE_COLS] = featured[FEATURE_COLS].fillna(0)

    total_features = len(FEATURE_COLS)
    logger.info(f"\n  Total features: {total_features}")
    logger.info(f"  Total records: {len(featured):,}")

    # ------------------------------------------------------------------
    # 3. TRAIN / VAL / TEST SPLIT
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: TRAIN / VAL / TEST SPLIT")
    logger.info("=" * 80)

    train, val, test = split_data(featured)

    # ------------------------------------------------------------------
    # 4. TRAIN MODEL
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: MODEL TRAINING (LightGBM + Optuna)")
    logger.info("=" * 80)

    model, best_params = train_model(train, val, test, FEATURE_COLS, n_trials=100)

    # ------------------------------------------------------------------
    # 5. EVALUATE
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: EVALUATION")
    logger.info("=" * 80)

    # Note: for evaluation, the TARGET column must be in original scale (not log1p)
    # The evaluate_model function does the log prediction internally
    val_metrics = evaluate_model(model, val, FEATURE_COLS, top_items, "Validation")
    test_metrics = evaluate_model(model, test, FEATURE_COLS, top_items, "Test")

    # ------------------------------------------------------------------
    # 6. FEATURE IMPORTANCE
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 80)
    logger.info("STEP 6: FEATURE IMPORTANCE")
    logger.info("=" * 80)

    feature_importance = analyze_features(model, FEATURE_COLS)

    # ------------------------------------------------------------------
    # 7. SAVE
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 80)
    logger.info("STEP 7: SAVING MODEL")
    logger.info("=" * 80)

    save_model(model, best_params, FEATURE_COLS, top_items,
               test_metrics, val_metrics, feature_importance)

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 80)
    logger.info("TRAINING COMPLETE ✓")
    logger.info("=" * 80)
    logger.info(f"  Model:         LightGBM v3.0")
    logger.info(f"  Items:         {len(top_items)} (top by volume)")
    logger.info(f"  Features:      {total_features}")
    logger.info(f"  Val MAE:       {val_metrics['overall_mae']:.3f}")
    logger.info(f"  Val SMAPE:     {val_metrics['weighted_smape']:.2f}%")
    logger.info(f"  Test MAE:      {test_metrics['overall_mae']:.3f}")
    logger.info(f"  Test SMAPE:    {test_metrics['weighted_smape']:.2f}%")
    logger.info(f"  Test MAPE:     {test_metrics['weighted_mape']:.2f}% (actual≥2)")

    v2_wmape = 74.95
    improvement = v2_wmape - test_metrics['weighted_mape']
    logger.info(f"\n  vs v2.0:       {improvement:+.2f}% improvement in weighted MAPE")
    logger.info(f"                 (v2.0: {v2_wmape:.2f}%  →  v3.0: {test_metrics['weighted_mape']:.2f}%)")
    logger.info("=" * 80 + "\n")

    return model, test_metrics


if __name__ == "__main__":
    main()
