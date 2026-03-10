"""
Item-Level Demand Forecasting Model Training

Trains a single XGBoost model that predicts demand for all menu items.
Uses target encoding for item_name to avoid 50-60 separate models.
"""

import pandas as pd
import numpy as np
import sys
import logging
import argparse
import joblib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple
import warnings

warnings.filterwarnings('ignore')

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from load_item_level_data import load_item_level_data, get_item_stats
from ensemble_backtest import prepare_features_item_level
from app.services.ml.encoders import ItemTargetEncoder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def train_item_level_model(
    lexis_file: str,
    version: str = 'v2.0',
    description: str = None,
    train_end_date: str = '2025-11-30',
    clip_outliers: bool = True
) -> Dict[str, Any]:
    """
    Train item-level XGBoost model

    Args:
        lexis_file: Path to Lexis Excel export
        version: Model version string (e.g., 'v2.0')
        description: Optional description for metadata
        train_end_date: End date for training split (YYYY-MM-DD)
        clip_outliers: Whether to clip extreme outliers

    Returns:
        {
            'model': XGBRegressor,
            'encoder': ItemTargetEncoder,
            'feature_cols': List[str],
            'metadata': Dict
        }
    """
    from xgboost import XGBRegressor

    logger.info("="*80)
    logger.info("ITEM-LEVEL MODEL TRAINING")
    logger.info("="*80)

    # ========================================================================
    # STEP 1: Load item-level data
    # ========================================================================
    logger.info("\nStep 1: Loading item-level data...")
    daily_item = load_item_level_data(lexis_file)

    logger.info(f"  Loaded {len(daily_item):,} day-item records")
    logger.info(f"  Date range: {daily_item['ds'].min().date()} to {daily_item['ds'].max().date()}")
    logger.info(f"  Unique items: {daily_item['item_name'].nunique()}")

    # Show item statistics
    item_stats = get_item_stats(daily_item)
    logger.info(f"\n  Top 10 items by volume:")
    for idx, row in item_stats.head(10).iterrows():
        logger.info(f"    {row['item_name'][:40]:40s} {row['total_qty']:>6.0f} units ({row['avg_daily_qty']:>4.1f}/day)")

    # ========================================================================
    # STEP 2: Train/Test Split
    # ========================================================================
    train_end = pd.to_datetime(train_end_date)
    train_df = daily_item[daily_item['ds'] <= train_end].copy()
    test_df = daily_item[daily_item['ds'] > train_end].copy()

    logger.info(f"\nStep 2: Train/Test Split")
    logger.info(f"  Train: {len(train_df):,} records ({train_df['ds'].min().date()} to {train_df['ds'].max().date()})")
    logger.info(f"  Test:  {len(test_df):,} records ({test_df['ds'].min().date()} to {test_df['ds'].max().date()})")

    # ========================================================================
    # STEP 3: Feature Engineering
    # ========================================================================
    logger.info("\nStep 3: Feature engineering...")

    # Prepare features for training (fit encoder)
    train_df, encoder = prepare_features_item_level(
        train_df,
        encoder=None,
        fit_encoder=True,
        clip_outliers=clip_outliers
    )

    # Prepare features for test (use fitted encoder)
    test_df, _ = prepare_features_item_level(
        test_df,
        encoder=encoder,
        fit_encoder=False,
        clip_outliers=False  # Don't clip test data
    )

    # Define feature columns (exclude target and identifiers)
    feature_cols = [col for col in train_df.columns if col not in ['ds', 'item_name', 'y']]
    logger.info(f"  Features: {len(feature_cols)}")

    # Show top features by type
    item_features = [col for col in feature_cols if 'item' in col]
    temporal_features = [col for col in feature_cols if any(x in col for x in ['day', 'month', 'weekend'])]
    lag_features = [col for col in feature_cols if 'lag' in col or 'rolling' in col]
    external_features = [col for col in feature_cols if any(x in col for x in ['weather', 'discount', 'rain', 'temp'])]

    logger.info(f"    Item features: {len(item_features)} ({', '.join(item_features[:5])})")
    logger.info(f"    Temporal features: {len(temporal_features)}")
    logger.info(f"    Lag features: {len(lag_features)}")
    logger.info(f"    External features: {len(external_features)}")

    # ========================================================================
    # STEP 4: Train XGBoost
    # ========================================================================
    logger.info("\nStep 4: Training XGBoost...")

    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.9,        # Regularization (prevent overfitting)
        colsample_bytree=0.9,
        reg_lambda=5,         # L2 regularization
        random_state=42,
        verbosity=0
    )

    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['y']

    logger.info(f"  Training on {len(X_train):,} samples...")
    model.fit(X_train, y_train)
    logger.info(f"  ✓ Training complete")

    # ========================================================================
    # STEP 5: Evaluate
    # ========================================================================
    logger.info("\nStep 5: Evaluation...")

    # Train MAPE (in-sample)
    train_pred = model.predict(X_train)
    train_pred = np.maximum(train_pred, 0)  # Clip negatives

    # Calculate MAPE (avoid division by zero)
    train_mape = np.mean(np.abs((y_train - train_pred) / (y_train + 1e-10))) * 100

    # Test MAPE (holdout)
    X_test = test_df[feature_cols].fillna(0)
    y_test = test_df['y']
    test_pred = model.predict(X_test)
    test_pred = np.maximum(test_pred, 0)

    test_mape = np.mean(np.abs((y_test - test_pred) / (y_test + 1e-10))) * 100

    logger.info(f"  Train MAPE (in-sample): {train_mape:.2f}%")
    logger.info(f"  Test MAPE (holdout):    {test_mape:.2f}%")

    # ========================================================================
    # STEP 6: Per-Item MAPE Analysis
    # ========================================================================
    logger.info(f"\nStep 6: Per-item accuracy analysis...")

    test_df['pred'] = test_pred
    item_mape = []

    for item in test_df['item_name'].unique():
        item_data = test_df[test_df['item_name'] == item]
        y_true = item_data['y'].values
        y_pred = item_data['pred'].values

        # Only calculate MAPE for days item was actually sold (qty > 0)
        mask = y_true > 0
        if mask.sum() > 0:
            mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / (y_true[mask] + 1e-10))) * 100
            item_mape.append({
                'item': item,
                'mape': mape,
                'total_qty': y_true.sum(),
                'n_days_sold': mask.sum()
            })

    item_mape_df = pd.DataFrame(item_mape).sort_values('total_qty', ascending=False)

    logger.info(f"\n  Top 20 items MAPE (by volume):")
    logger.info(f"  {'Item':<45s} {'MAPE':>8s} {'Total Qty':>10s} {'Days Sold':>10s}")
    logger.info("  " + "-"*78)

    for idx, row in item_mape_df.head(20).iterrows():
        logger.info(
            f"  {row['item'][:45]:<45s} "
            f"{row['mape']:>7.1f}% "
            f"{row['total_qty']:>10.0f} "
            f"{row['n_days_sold']:>10.0f}"
        )

    # Weighted MAPE (by volume)
    total_qty = item_mape_df['total_qty'].sum()
    weighted_mape = (item_mape_df['mape'] * item_mape_df['total_qty']).sum() / total_qty

    logger.info(f"\n  Weighted MAPE (by volume): {weighted_mape:.2f}%")

    # Distribution analysis
    logger.info(f"\n  MAPE Distribution:")
    logger.info(f"    Mean:   {item_mape_df['mape'].mean():.2f}%")
    logger.info(f"    Median: {item_mape_df['mape'].median():.2f}%")
    logger.info(f"    Std:    {item_mape_df['mape'].std():.2f}%")
    logger.info(f"    Min:    {item_mape_df['mape'].min():.2f}%")
    logger.info(f"    Max:    {item_mape_df['mape'].max():.2f}%")

    # ========================================================================
    # STEP 7: Feature Importance
    # ========================================================================
    logger.info(f"\nStep 7: Feature importance analysis...")

    feature_importance = dict(zip(feature_cols, model.feature_importances_))
    top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:20]

    logger.info(f"\n  Top 20 features:")
    for feat, imp in top_features:
        logger.info(f"    {feat:35s} {imp*100:>6.2f}%")

    # Check if item_encoded is important
    item_encoded_rank = None
    for rank, (feat, imp) in enumerate(top_features, 1):
        if feat == 'item_encoded':
            item_encoded_rank = rank
            logger.info(f"\n  ✓ item_encoded is rank #{item_encoded_rank} (importance: {imp*100:.2f}%)")
            break

    if item_encoded_rank is None or item_encoded_rank > 10:
        logger.warning(f"\n  ⚠️  item_encoded not in top 10 features - encoding may not be effective")

    # ========================================================================
    # STEP 8: Save Model
    # ========================================================================
    logger.info(f"\nStep 8: Saving model...")

    metadata = {
        'version': version,
        'description': description or f'Item-level XGBoost with target encoding',
        'model_type': 'XGBoost Item-Level',
        'created_at': datetime.now().isoformat(),
        'train_mape': float(train_mape),
        'test_mape': float(test_mape),
        'weighted_mape': float(weighted_mape),
        'training_data_size': len(train_df),
        'n_items': int(daily_item['item_name'].nunique()),
        'n_features': len(feature_cols),
        'date_range': {
            'start': train_df['ds'].min().isoformat(),
            'end': train_df['ds'].max().isoformat()
        },
        'test_date_range': {
            'start': test_df['ds'].min().isoformat(),
            'end': test_df['ds'].max().isoformat()
        },
        'item_encoded_rank': item_encoded_rank,
        'top_10_features': [feat for feat, _ in top_features[:10]]
    }

    model_dict = {
        'model': model,
        'encoder': encoder,
        'feature_cols': feature_cols,
        'metadata': metadata
    }

    save_item_level_model(model_dict, version)

    logger.info(f"  ✓ Saved to /models/{version}/")
    logger.info("="*80)

    return model_dict


def save_item_level_model(model_dict: Dict, version: str):
    """Save item-level model with encoder"""
    model_dir = Path(__file__).parent.parent.parent / 'models' / version
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    model_path = model_dir / 'model.joblib'
    joblib.dump(model_dict['model'], model_path, compress=3)
    logger.info(f"  Saved model: {model_path}")

    # Save encoder
    encoder_path = model_dir / 'encoder.json'
    model_dict['encoder'].save(encoder_path)
    logger.info(f"  Saved encoder: {encoder_path}")

    # Save features
    features_path = model_dir / 'features.json'
    with open(features_path, 'w') as f:
        json.dump(model_dict['feature_cols'], f, indent=2)
    logger.info(f"  Saved features: {features_path}")

    # Save metadata
    metadata_path = model_dir / 'metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(model_dict['metadata'], f, indent=2)
    logger.info(f"  Saved metadata: {metadata_path}")

    # Feature importance
    importance_df = pd.DataFrame({
        'feature': model_dict['feature_cols'],
        'importance': model_dict['model'].feature_importances_
    }).sort_values('importance', ascending=False)

    importance_path = model_dir / 'feature_importance.csv'
    importance_df.to_csv(importance_path, index=False)
    logger.info(f"  Saved feature importance: {importance_path}")


def load_item_level_model(version: str = 'latest') -> Dict[str, Any]:
    """
    Load item-level model

    Args:
        version: Model version to load (or 'latest' for most recent)

    Returns:
        Model dictionary with model, encoder, features, metadata
    """
    models_dir = Path(__file__).parent.parent.parent / 'models'

    if version == 'latest':
        # Find latest version directory
        version_dirs = [d for d in models_dir.iterdir() if d.is_dir() and d.name.startswith('v')]
        if not version_dirs:
            raise ValueError("No model versions found")

        # Sort by modification time
        version = max(version_dirs, key=lambda p: p.stat().st_mtime).name

    model_dir = models_dir / version

    if not model_dir.exists():
        raise ValueError(f"Model version {version} not found at {model_dir}")

    logger.info(f"Loading model from: {model_dir}")

    # Load model
    model = joblib.load(model_dir / 'model.joblib')

    # Load encoder
    encoder = ItemTargetEncoder.load(model_dir / 'encoder.json')

    # Load features
    with open(model_dir / 'features.json', 'r') as f:
        feature_cols = json.load(f)

    # Load metadata
    with open(model_dir / 'metadata.json', 'r') as f:
        metadata = json.load(f)

    logger.info(f"  Loaded model version: {metadata['version']}")
    logger.info(f"  Test MAPE: {metadata['test_mape']:.2f}%")
    logger.info(f"  Weighted MAPE: {metadata['weighted_mape']:.2f}%")

    return {
        'model': model,
        'encoder': encoder,
        'feature_cols': feature_cols,
        'metadata': metadata
    }


def main():
    parser = argparse.ArgumentParser(
        description='Train item-level demand forecasting model',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--lexis-file',
        type=str,
        default='/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx',
        help='Path to Lexis Excel export file'
    )

    parser.add_argument(
        '--version',
        type=str,
        default='v2.0',
        help='Model version string (e.g., v2.0, v2.1)'
    )

    parser.add_argument(
        '--description',
        type=str,
        default=None,
        help='Optional description for model metadata'
    )

    parser.add_argument(
        '--train-end',
        type=str,
        default='2025-11-30',
        help='End date for training split (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--no-clip',
        action='store_true',
        help='Disable outlier clipping'
    )

    args = parser.parse_args()

    try:
        model_dict = train_item_level_model(
            lexis_file=args.lexis_file,
            version=args.version,
            description=args.description,
            train_end_date=args.train_end,
            clip_outliers=not args.no_clip
        )

        # Success summary
        logger.info("\n" + "="*80)
        logger.info("TRAINING COMPLETE ✓")
        logger.info("="*80)
        logger.info(f"Model version: {model_dict['metadata']['version']}")
        logger.info(f"Test MAPE: {model_dict['metadata']['test_mape']:.2f}%")
        logger.info(f"Weighted MAPE: {model_dict['metadata']['weighted_mape']:.2f}%")

        if model_dict['metadata']['weighted_mape'] < 60:
            logger.info("\n✅ SUCCESS: Weighted MAPE < 60% (better than hierarchical 76-89%)")
        else:
            logger.info(f"\n⚠️  WARNING: Weighted MAPE > 60% (worse than target)")

        logger.info("="*80 + "\n")

        sys.exit(0)

    except Exception as e:
        logger.error(f"\n✗ Training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
