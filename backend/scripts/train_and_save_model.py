"""
Train and Save Production Model

This script trains the best-performing model configuration and saves it for production use.

Usage:
    python scripts/train_and_save_model.py --version v1.0
    python scripts/train_and_save_model.py --version v1.0 --description "Production model with discounts"
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
from typing import Dict, Any

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from scripts.ensemble_backtest import load_lexis_data, prepare_features
from xgboost import XGBRegressor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def train_production_model(
    daily_df: pd.DataFrame,
    feature_cols: list,
    model_params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Train model on ALL available data for production use

    Args:
        daily_df: Full daily data
        feature_cols: List of feature column names
        model_params: XGBoost hyperparameters

    Returns:
        Dictionary with trained model and metadata
    """
    # Default to best-performing params (baseline)
    if model_params is None:
        model_params = {
            'n_estimators': 100,
            'max_depth': 4,
            'learning_rate': 0.1,
            'random_state': 42,
            'verbosity': 0
        }

    logger.info(f"Training production model on {len(daily_df)} days of data")
    logger.info(f"Features: {len(feature_cols)}")
    logger.info(f"Params: {model_params}")

    # Prepare data
    X = daily_df[feature_cols].fillna(0)
    y = daily_df['y']

    # Train model
    model = XGBRegressor(**model_params)
    model.fit(X, y)

    # Calculate training metrics
    train_pred = model.predict(X)
    train_mape = np.mean(np.abs((y - train_pred) / (y + 1e-10))) * 100

    logger.info(f"Training MAPE: {train_mape:.2f}%")

    # Get feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    logger.info("\nTop 10 Most Important Features:")
    for idx, row in feature_importance.head(10).iterrows():
        logger.info(f"  {row['feature']:30s}: {row['importance']:.4f}")

    return {
        'model': model,
        'feature_cols': feature_cols,
        'model_params': model_params,
        'train_mape': train_mape,
        'feature_importance': feature_importance.to_dict('records'),
        'training_data_size': len(daily_df),
        'date_range': {
            'start': daily_df['ds'].min().strftime('%Y-%m-%d'),
            'end': daily_df['ds'].max().strftime('%Y-%m-%d')
        }
    }


def save_model(
    model_dict: Dict[str, Any],
    version: str,
    description: str = None,
    model_dir: Path = None
) -> Path:
    """
    Save model with metadata and versioning

    Args:
        model_dict: Dictionary containing model and metadata
        version: Version string (e.g., 'v1.0', 'v2.1')
        description: Optional description
        model_dir: Directory to save models (default: /models/)

    Returns:
        Path to saved model directory
    """
    if model_dir is None:
        model_dir = backend_dir.parent / "models"

    # Create version directory
    version_dir = model_dir / version
    version_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    model_file = version_dir / "model.joblib"
    joblib.dump(model_dict['model'], model_file, compress=3)
    logger.info(f"✓ Saved model to: {model_file}")

    # Save feature columns
    feature_file = version_dir / "features.json"
    with open(feature_file, 'w') as f:
        json.dump(model_dict['feature_cols'], f, indent=2)
    logger.info(f"✓ Saved features to: {feature_file}")

    # Save metadata
    metadata = {
        'version': version,
        'created_at': datetime.now().isoformat(),
        'description': description or f"Production model {version}",
        'model_type': 'XGBoost',
        'model_params': model_dict['model_params'],
        'train_mape': model_dict['train_mape'],
        'training_data_size': model_dict['training_data_size'],
        'date_range': model_dict['date_range'],
        'n_features': len(model_dict['feature_cols']),
        'feature_importance_top10': model_dict['feature_importance'][:10]
    }

    metadata_file = version_dir / "metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"✓ Saved metadata to: {metadata_file}")

    # Save full feature importance
    importance_file = version_dir / "feature_importance.csv"
    pd.DataFrame(model_dict['feature_importance']).to_csv(importance_file, index=False)
    logger.info(f"✓ Saved feature importance to: {importance_file}")

    # Update latest symlink
    latest_link = model_dir / "latest"
    if latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(version_dir.name)
    logger.info(f"✓ Updated 'latest' to point to {version}")

    return version_dir


def load_model(version: str = "latest", model_dir: Path = None) -> Dict[str, Any]:
    """
    Load a saved model

    Args:
        version: Version to load (default: 'latest')
        model_dir: Directory containing models

    Returns:
        Dictionary with model and metadata
    """
    if model_dir is None:
        model_dir = backend_dir.parent / "models"

    version_dir = model_dir / version
    if not version_dir.exists():
        raise ValueError(f"Model version '{version}' not found at {version_dir}")

    # Load model
    model_file = version_dir / "model.joblib"
    model = joblib.load(model_file)
    logger.info(f"✓ Loaded model from: {model_file}")

    # Load features
    feature_file = version_dir / "features.json"
    with open(feature_file, 'r') as f:
        features = json.load(f)
    logger.info(f"✓ Loaded {len(features)} features")

    # Load metadata
    metadata_file = version_dir / "metadata.json"
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    logger.info(f"✓ Loaded metadata for version {metadata['version']}")

    return {
        'model': model,
        'feature_cols': features,
        'metadata': metadata,
        'version': version
    }


def main():
    parser = argparse.ArgumentParser(description='Train and save production model')
    parser.add_argument(
        '--version',
        type=str,
        required=True,
        help='Model version (e.g., v1.0, v2.1)'
    )
    parser.add_argument(
        '--description',
        type=str,
        default=None,
        help='Model description'
    )
    parser.add_argument(
        '--lexis-file',
        type=str,
        default='/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx',
        help='Path to Lexis data file'
    )
    parser.add_argument(
        '--custom-params',
        type=str,
        default=None,
        help='JSON string with custom XGBoost params'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info(f"TRAINING PRODUCTION MODEL: {args.version}")
    logger.info("="*80)

    # Load data
    daily = load_lexis_data(args.lexis_file)
    daily = prepare_features(daily)

    # Get feature columns
    feature_cols = [col for col in daily.columns if col not in ['ds', 'y']]

    # Custom params if provided
    model_params = None
    if args.custom_params:
        model_params = json.loads(args.custom_params)
        logger.info(f"Using custom params: {model_params}")

    # Train model
    model_dict = train_production_model(daily, feature_cols, model_params)

    # Save model
    version_dir = save_model(
        model_dict,
        version=args.version,
        description=args.description
    )

    logger.info(f"\n{'='*80}")
    logger.info(f"MODEL SAVED SUCCESSFULLY")
    logger.info(f"{'='*80}\n")
    logger.info(f"Version: {args.version}")
    logger.info(f"Location: {version_dir}")
    logger.info(f"Training MAPE: {model_dict['train_mape']:.2f}%")
    logger.info(f"Data: {model_dict['date_range']['start']} to {model_dict['date_range']['end']}")
    logger.info(f"Features: {len(feature_cols)}")

    logger.info(f"\nTo load this model:")
    logger.info(f"  from scripts.train_and_save_model import load_model")
    logger.info(f"  model_dict = load_model('{args.version}')")

    logger.info(f"\nTo load latest model:")
    logger.info(f"  model_dict = load_model('latest')")


if __name__ == "__main__":
    main()
