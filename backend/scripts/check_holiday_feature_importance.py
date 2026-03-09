"""
Check why holiday features aren't helping with MAPE
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.ml.feature_library import build_cloud_kitchen_features
from app.services.ml.holiday_calendar import IndianHolidayCalendar
from xgboost import XGBRegressor

# Load data
lexis_file = "/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx"

def load_and_prepare():
    # Load Excel - try different header rows
    for header_row in [4, 5, 6]:
        try:
            df = pd.read_excel(lexis_file, header=header_row)
            date_cols = [col for col in df.columns if 'date' in str(col).lower()]
            if not date_cols:
                continue

            date_col = date_cols[0]
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df[df[date_col].notna()]

            if len(df) > 0 and 'Total' in str(df.iloc[0].values):
                df = df.iloc[1:]

            if len(df) > 1000:
                break
        except Exception:
            continue

    qty_col = 'Qty.' if 'Qty.' in df.columns else [col for col in df.columns if 'qty' in str(col).lower()][0]
    df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)

    # Aggregate daily
    daily = df.groupby(date_col).agg({qty_col: 'sum'}).reset_index()
    daily.columns = ['ds', 'y']
    daily = daily.sort_values('ds')

    # Baseline features
    daily['day_of_week'] = daily['ds'].dt.dayofweek
    daily['day_of_month'] = daily['ds'].dt.day
    daily['month'] = daily['ds'].dt.month
    daily['is_weekend'] = (daily['day_of_week'] >= 5).astype(int)

    for lag in [1, 7, 14]:
        daily[f'lag_{lag}'] = daily['y'].shift(lag)

    daily['rolling_mean_7'] = daily['y'].rolling(window=7, min_periods=1).mean()
    daily['rolling_mean_14'] = daily['y'].rolling(window=14, min_periods=1).mean()
    daily['rolling_std_7'] = daily['y'].rolling(window=7, min_periods=1).std().fillna(0)

    # Cloud kitchen features
    daily = build_cloud_kitchen_features(daily, "Cloud Kitchen", "Residential", True)

    # Holiday features
    daily = IndianHolidayCalendar.add_holiday_features(daily)

    return daily

# Prepare data
daily = load_and_prepare()

# Train-test split
split_date = datetime(2025, 12, 15)
train_df = daily[daily['ds'] < split_date].copy()
test_df = daily[daily['ds'] >= split_date].copy()

# Get feature columns
feature_cols = [col for col in daily.columns if col not in ['ds', 'y', 'holiday_name']]

print(f"\n{'='*70}")
print("FEATURE ANALYSIS")
print(f"{'='*70}\n")

print(f"Total features: {len(feature_cols)}")
print(f"Training samples: {len(train_df)}")
print(f"Test samples: {len(test_df)}\n")

# Check holiday features in training data
holiday_features = ['is_holiday', 'is_major_festival', 'holiday_impact_score', 'is_pre_festival']

print("Holiday Feature Statistics in Training Data:")
print("-" * 70)
for feat in holiday_features:
    if feat in train_df.columns:
        non_zero = (train_df[feat] != 0).sum()
        print(f"{feat:30s} Non-zero: {non_zero:2d} / {len(train_df):2d} ({non_zero/len(train_df)*100:.1f}%)")

print("\nHoliday Feature Statistics in Test Data:")
print("-" * 70)
for feat in holiday_features:
    if feat in test_df.columns:
        non_zero = (test_df[feat] != 0).sum()
        print(f"{feat:30s} Non-zero: {non_zero:2d} / {len(test_df):2d} ({non_zero/len(test_df)*100:.1f}%)")

# Train model
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

# Get ALL feature importances
importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print(f"\n{'='*70}")
print("ALL FEATURE IMPORTANCES")
print(f"{'='*70}\n")

# Show holiday features specifically
print("Holiday Feature Importances:")
print("-" * 70)
for feat in holiday_features:
    if feat in importance['feature'].values:
        imp = importance[importance['feature'] == feat]['importance'].values[0]
        rank = importance[importance['feature'] == feat].index[0] + 1
        print(f"{feat:30s} Importance: {imp:.6f}  (Rank: {rank:2d}/{len(feature_cols)})")

print("\n\nTop 20 Features:")
print("-" * 70)
for i, row in importance.head(20).iterrows():
    is_holiday = "🎄" if row['feature'] in holiday_features else "  "
    print(f"{is_holiday} {row['feature']:30s} {row['importance']:.6f}")

# Check predictions on holiday days
print(f"\n{'='*70}")
print("PREDICTIONS ON HOLIDAY DAYS (Test Set)")
print(f"{'='*70}\n")

y_pred = model.predict(X_test)
test_results = test_df[['ds', 'y']].copy()
test_results['pred'] = y_pred
test_results['error_pct'] = np.abs((test_results['y'] - test_results['pred']) / (test_results['y'] + 1)) * 100

# Add holiday info
test_results['is_holiday'] = test_df['is_holiday'].values
test_results['holiday_name'] = test_df['holiday_name'].values

holiday_days = test_results[test_results['is_holiday'] == 1]

if len(holiday_days) > 0:
    print(f"Found {len(holiday_days)} holiday days in test set:\n")
    for _, row in holiday_days.iterrows():
        print(f"  {row['ds'].strftime('%Y-%m-%d')} ({row['holiday_name']})")
        print(f"    Actual: {row['y']:.0f},  Predicted: {row['pred']:.0f},  Error: {row['error_pct']:.1f}%\n")
else:
    print("No holiday days in test set")

print(f"{'='*70}\n")
