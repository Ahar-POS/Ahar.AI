"""Quick test of direct item-level model"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from load_item_level_data import load_item_level_data
from train_item_level_model import load_item_level_model
from ensemble_backtest import prepare_features_item_level

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Load model
logger.info("Loading model v2.0...")
model_dict = load_item_level_model('v2.0')
model = model_dict['model']
encoder = model_dict['encoder']
feature_cols = model_dict['feature_cols']

# Load data
logger.info("Loading data...")
lexis_file = "/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx"
daily_item = load_item_level_data(lexis_file)

# Split
test_start = pd.to_datetime('2025-12-01')
test_df = daily_item[daily_item['ds'] >= test_start].copy()

logger.info(f"Test period: {test_df['ds'].min().date()} to {test_df['ds'].max().date()}")

# Get historical for lag features
historical = daily_item[daily_item['ds'] < test_start].copy()
combined = pd.concat([historical, test_df], ignore_index=True)

# Prepare features
logger.info("Preparing features...")
combined_featured, _ = prepare_features_item_level(
    combined, encoder=encoder, fit_encoder=False, clip_outliers=False
)

test_featured = combined_featured[combined_featured['ds'] >= test_start].copy()

# Predict
logger.info("Predicting...")
X_test = test_featured[feature_cols].fillna(0)
predictions = model.predict(X_test)
predictions = np.maximum(predictions, 0)

test_featured['pred'] = predictions

# Calculate metrics
y_true = test_featured['y'].values
y_pred = test_featured['pred'].values

# Per-item MAPE (only on days sold)
logger.info("\n" + "="*80)
logger.info("PER-ITEM ACCURACY")
logger.info("="*80)

item_metrics = []
for item in test_featured['item_name'].unique():
    item_data = test_featured[test_featured['item_name'] == item]
    y_true_item = item_data['y'].values
    y_pred_item = item_data['pred'].values

    mask = y_true_item > 0
    if mask.sum() > 0:
        mape = np.mean(np.abs((y_true_item[mask] - y_pred_item[mask]) / y_true_item[mask])) * 100
        item_metrics.append({
            'item': item,
            'mape': mape,
            'total_qty': y_true_item.sum(),
            'pred_qty': y_pred_item.sum()
        })

item_metrics_df = pd.DataFrame(item_metrics).sort_values('total_qty', ascending=False)

# Weighted MAPE
weighted_mape = (item_metrics_df['mape'] * item_metrics_df['total_qty']).sum() / item_metrics_df['total_qty'].sum()

logger.info(f"\nTop 15 items:")
for idx, row in item_metrics_df.head(15).iterrows():
    logger.info(f"  {row['item'][:50]:50s} MAPE: {row['mape']:>6.1f}%  Qty: {row['total_qty']:>5.0f}")

logger.info(f"\nWeighted MAPE: {weighted_mape:.2f}%")
logger.info(f"Mean MAPE: {item_metrics_df['mape'].mean():.2f}%")
logger.info(f"Median MAPE: {item_metrics_df['mape'].median():.2f}%")

# Restaurant-level total
daily_totals = test_featured.groupby('ds').agg({'y': 'sum', 'pred': 'sum'})
total_mape = np.mean(np.abs((daily_totals['y'] - daily_totals['pred']) / daily_totals['y'])) * 100

logger.info(f"\n" + "="*80)
logger.info("RESTAURANT-LEVEL TOTAL")
logger.info("="*80)
logger.info(f"MAPE: {total_mape:.2f}%")

logger.info(f"\n" + "="*80)
logger.info("SUCCESS CRITERIA")
logger.info("="*80)
logger.info(f"✓ Weighted MAPE < 60%:  {'PASS' if weighted_mape < 60 else 'FAIL'} ({weighted_mape:.2f}%)")
logger.info(f"✓ Top 10 MAPE < 40%:    {'PASS' if item_metrics_df.head(10)['mape'].mean() < 40 else 'FAIL'} ({item_metrics_df.head(10)['mape'].mean():.2f}%)")
logger.info(f"✓ Restaurant MAPE < 20%: {'PASS' if total_mape < 20 else 'FAIL'} ({total_mape:.2f}%)")
logger.info("="*80)
