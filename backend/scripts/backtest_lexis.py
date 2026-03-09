"""
Backtest ML Models on Lexis Data

Tests forecasting accuracy on real Lexis restaurant data (Oct 1 - Dec 31, 2025).

Usage:
    # Quick test (no hyperparameter tuning)
    python scripts/backtest_lexis.py

    # With hyperparameter tuning (slower but better accuracy)
    python scripts/backtest_lexis.py --tune

    # Test specific ingredient
    python scripts/backtest_lexis.py --ingredient-id chicken_breast_001

    # Save detailed results
    python scripts/backtest_lexis.py --output results.json
"""

import asyncio
import sys
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import pandas as pd
import numpy as np

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.ml.models import ProphetForecaster, SARIMAForecaster, XGBoostForecaster
from app.services.ml.ensemble_predictor import EnsemblePredictor
from app.services.ml.tier_based_forecaster import TierBasedForecaster
from app.services.ml.hyperparameter_tuner import HyperparameterTuner
from app.services.feature_engineering import FeatureEngineeringService
from app.services.data_quality import get_outlier_detector
from app.core.database import get_database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate forecasting accuracy metrics"""
    # Remove NaN values
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    if len(y_true) == 0:
        return {"mae": 999, "rmse": 999, "mape": 999, "r2": 0}

    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    mape = np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-10))) * 100

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    return {
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "mape": round(float(mape), 2),
        "r2": round(float(r2), 4)
    }


async def load_lexis_data(
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    """
    Load Lexis order data from database

    Args:
        start_date: Start date (Oct 1, 2025)
        end_date: End date (Dec 31, 2025)

    Returns:
        DataFrame with daily aggregated order data
    """
    logger.info(f"Loading Lexis data: {start_date.date()} to {end_date.date()}")

    db = get_database()
    feature_service = FeatureEngineeringService(db)

    # Load orders data with features
    df = await feature_service.build_ml_features(
        start_date=start_date,
        end_date=end_date,
        include_lags=True
    )

    if df.empty:
        raise ValueError("No data loaded! Check database connection and date range.")

    # Ensure required columns
    if "ds" not in df.columns:
        df["ds"] = pd.to_datetime(df["order_date"])

    if "y" not in df.columns:
        # Use total order count as proxy (replace with actual ingredient data)
        if "quantity" in df.columns:
            df["y"] = df["quantity"]
        else:
            # Aggregate by date
            df["y"] = 1  # Each row is an order

    # Aggregate by date if multiple rows per day
    if len(df) > (end_date - start_date).days:
        # Only aggregate numeric columns with mean, exclude string columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        agg_dict = {"y": "sum"}
        for col in numeric_cols:
            if col not in ["y"] and col in df.columns:
                agg_dict[col] = "mean"

        df = df.groupby("ds").agg(agg_dict).reset_index()

    logger.info(f"✓ Loaded {len(df)} days of data")
    logger.info(f"  Date range: {df['ds'].min().date()} to {df['ds'].max().date()}")
    logger.info(f"  Total consumption: {df['y'].sum():.1f}")
    logger.info(f"  Features: {len(df.columns)}")

    return df


async def backtest_prophet(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    hyperparameter_tuning: bool = False
) -> dict:
    """Backtest Prophet model"""
    logger.info("Testing Prophet...")

    try:
        # Hyperparameter tuning if requested
        if hyperparameter_tuning:
            logger.info("  Running hyperparameter tuning (this may take 5-10 minutes)...")
            tuner = HyperparameterTuner(n_splits=3, n_iter=20)
            tuning_result = tuner.tune_prophet(train_df)
            best_params = tuning_result["best_params"]
            logger.info(f"  ✓ Best params: {best_params}")
        else:
            best_params = {}

        # Train Prophet
        prophet = ProphetForecaster(data_tier="tier_4", **best_params)
        prophet.fit(train_df, target_column="y", date_column="ds")

        # Predict on test set
        predictions = prophet.predict(horizon=len(test_df), return_confidence=True)

        # Calculate metrics
        y_true = test_df["y"].values
        y_pred = predictions["yhat"].values

        metrics = calculate_metrics(y_true, y_pred)

        logger.info(f"  ✓ Prophet MAPE: {metrics['mape']:.2f}%")

        return {
            "model": "prophet",
            "metrics": metrics,
            "predictions": predictions.to_dict(orient="records")[:7],  # First 7 days
            "hyperparameter_tuning": hyperparameter_tuning,
            "best_params": best_params if hyperparameter_tuning else None
        }

    except Exception as e:
        logger.error(f"  ✗ Prophet failed: {e}")
        return {"model": "prophet", "error": str(e)}


async def backtest_sarima(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame
) -> dict:
    """Backtest SARIMA model"""
    logger.info("Testing SARIMA...")

    try:
        # Train SARIMA
        sarima = SARIMAForecaster(seasonal_period=7, auto_arima=True)
        sarima.fit(train_df, target_column="y", date_column="ds")

        # Predict on test set
        predictions = sarima.predict(horizon=len(test_df), return_confidence=True)

        # Calculate metrics
        y_true = test_df["y"].values
        y_pred = predictions["yhat"].values

        metrics = calculate_metrics(y_true, y_pred)

        logger.info(f"  ✓ SARIMA MAPE: {metrics['mape']:.2f}%")

        return {
            "model": "sarima",
            "metrics": metrics,
            "predictions": predictions.to_dict(orient="records")[:7],
            "order": sarima.order,
            "seasonal_order": sarima.seasonal_order
        }

    except Exception as e:
        logger.error(f"  ✗ SARIMA failed: {e}")
        return {"model": "sarima", "error": str(e)}


async def backtest_xgboost(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    hyperparameter_tuning: bool = False
) -> dict:
    """Backtest XGBoost model"""
    logger.info("Testing XGBoost...")

    try:
        # Get feature columns
        feature_cols = [col for col in train_df.columns if col not in ["ds", "y", "_id", "order_date"]]

        # Hyperparameter tuning if requested
        if hyperparameter_tuning:
            logger.info("  Running hyperparameter tuning (this may take 10-15 minutes)...")
            tuner = HyperparameterTuner(n_splits=3, n_iter=30)
            tuning_result = tuner.tune_xgboost(train_df, feature_columns=feature_cols)
            best_params = tuning_result["best_params"]
            logger.info(f"  ✓ Best params: max_depth={best_params.get('max_depth')}, n_estimators={best_params.get('n_estimators')}")
        else:
            best_params = {}

        # Train XGBoost
        xgboost = XGBoostForecaster(**best_params)
        xgboost.fit(train_df, target_column="y", date_column="ds", exogenous_features=feature_cols)

        # Predict on test set
        test_features = test_df[["ds"] + feature_cols].copy()
        predictions = xgboost.predict(horizon=len(test_df), exogenous_future=test_features, return_confidence=True)

        # Calculate metrics
        y_true = test_df["y"].values
        y_pred = predictions["yhat"].values

        metrics = calculate_metrics(y_true, y_pred)

        # Get feature importance
        feature_importance = xgboost.get_top_features(n=10)

        logger.info(f"  ✓ XGBoost MAPE: {metrics['mape']:.2f}%")

        return {
            "model": "xgboost",
            "metrics": metrics,
            "predictions": predictions.to_dict(orient="records")[:7],
            "top_features": feature_importance,
            "hyperparameter_tuning": hyperparameter_tuning,
            "best_params": best_params if hyperparameter_tuning else None
        }

    except Exception as e:
        logger.error(f"  ✗ XGBoost failed: {e}")
        return {"model": "xgboost", "error": str(e)}


async def backtest_ensemble(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    prophet_result: dict,
    sarima_result: dict,
    xgboost_result: dict
) -> dict:
    """Backtest ensemble combining all models"""
    logger.info("Testing Ensemble (Prophet + SARIMA + XGBoost)...")

    try:
        # Extract MAPE from individual models
        mapes = {}
        if "metrics" in prophet_result:
            mapes["prophet"] = prophet_result["metrics"]["mape"]
        if "metrics" in sarima_result:
            mapes["sarima"] = sarima_result["metrics"]["mape"]
        if "metrics" in xgboost_result:
            mapes["xgboost"] = xgboost_result["metrics"]["mape"]

        # Calculate ensemble weights (inverse MAPE)
        inverse_mapes = {name: 1.0 / max(mape, 0.1) for name, mape in mapes.items()}
        total_inverse = sum(inverse_mapes.values())
        weights = {name: inv / total_inverse for name, inv in inverse_mapes.items()}

        logger.info(f"  Ensemble weights: {weights}")

        # Combine predictions
        ensemble_pred = np.zeros(len(test_df))

        if "predictions" in prophet_result:
            prophet_pred = np.array([p["yhat"] for p in prophet_result["predictions"]])
            ensemble_pred[:len(prophet_pred)] += weights.get("prophet", 0) * prophet_pred

        if "predictions" in sarima_result:
            sarima_pred = np.array([p["yhat"] for p in sarima_result["predictions"]])
            ensemble_pred[:len(sarima_pred)] += weights.get("sarima", 0) * sarima_pred

        if "predictions" in xgboost_result:
            xgboost_pred = np.array([p["yhat"] for p in xgboost_result["predictions"]])
            ensemble_pred[:len(xgboost_pred)] += weights.get("xgboost", 0) * xgboost_pred

        # Calculate metrics
        y_true = test_df["y"].values[:len(ensemble_pred)]
        metrics = calculate_metrics(y_true, ensemble_pred)

        logger.info(f"  ✓ Ensemble MAPE: {metrics['mape']:.2f}%")

        # Calculate improvement over best individual model
        best_individual_mape = min(mapes.values())
        improvement = best_individual_mape - metrics["mape"]

        return {
            "model": "ensemble",
            "metrics": metrics,
            "weights": weights,
            "improvement_over_best": round(improvement, 2),
            "best_individual_mape": round(best_individual_mape, 2)
        }

    except Exception as e:
        logger.error(f"  ✗ Ensemble failed: {e}")
        return {"model": "ensemble", "error": str(e)}


async def run_backtest(
    hyperparameter_tuning: bool = False,
    output_file: Optional[str] = None
):
    """Run complete backtest"""
    logger.info("="*70)
    logger.info("LEXIS DATA BACKTEST - ML Demand Forecasting")
    logger.info("="*70)

    # Connect to database
    from app.core.database import connect_to_database
    await connect_to_database()

    start_time = datetime.now()

    # Lexis data date range: Oct 1 - Dec 31, 2025
    data_start = datetime(2025, 10, 1)
    data_end = datetime(2025, 12, 31)

    # Train-test split
    train_end = datetime(2025, 12, 14)  # 75 days training
    test_start = datetime(2025, 12, 15)  # 17 days testing

    logger.info(f"\nData period: {data_start.date()} to {data_end.date()} (92 days)")
    logger.info(f"Training: {data_start.date()} to {train_end.date()} (75 days)")
    logger.info(f"Testing: {test_start.date()} to {data_end.date()} (17 days)")
    logger.info(f"Hyperparameter tuning: {'Yes (slow)' if hyperparameter_tuning else 'No (fast)'}")
    logger.info("")

    try:
        # Load data
        logger.info("Step 1/6: Loading Lexis data...")
        full_df = await load_lexis_data(data_start, data_end)

        # Split train-test
        train_df = full_df[full_df["ds"] <= train_end].copy()
        test_df = full_df[full_df["ds"] >= test_start].copy()

        logger.info(f"\n✓ Data loaded: {len(train_df)} train, {len(test_df)} test")

        # Test individual models
        logger.info("\nStep 2/6: Testing Prophet...")
        prophet_result = await backtest_prophet(train_df, test_df, hyperparameter_tuning)

        logger.info("\nStep 3/6: Testing SARIMA...")
        sarima_result = await backtest_sarima(train_df, test_df)

        logger.info("\nStep 4/6: Testing XGBoost...")
        xgboost_result = await backtest_xgboost(train_df, test_df, hyperparameter_tuning)

        logger.info("\nStep 5/6: Testing Ensemble...")
        ensemble_result = await backtest_ensemble(
            train_df, test_df,
            prophet_result, sarima_result, xgboost_result
        )

        # Generate report
        logger.info("\nStep 6/6: Generating report...")

        duration = (datetime.now() - start_time).total_seconds()

        report = {
            "test_date": datetime.now().isoformat(),
            "duration_seconds": round(duration, 2),
            "data_info": {
                "start_date": data_start.strftime("%Y-%m-%d"),
                "end_date": data_end.strftime("%Y-%m-%d"),
                "total_days": 92,
                "train_days": 75,
                "test_days": 17
            },
            "hyperparameter_tuning": hyperparameter_tuning,
            "results": {
                "prophet": prophet_result,
                "sarima": sarima_result,
                "xgboost": xgboost_result,
                "ensemble": ensemble_result
            }
        }

        # Print summary
        print_summary(report)

        # Save to file if requested
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"\n✓ Results saved to {output_file}")

        return report

    except Exception as e:
        logger.error(f"\n✗ Backtest failed: {e}", exc_info=True)
        return {"error": str(e)}


def print_summary(report: dict):
    """Print formatted summary"""
    print("\n" + "="*70)
    print("BACKTEST RESULTS SUMMARY")
    print("="*70)

    results = report.get("results", {})

    print("\n📊 ACCURACY COMPARISON (Lower MAPE = Better):\n")
    print(f"{'Model':<15} {'MAPE':<10} {'MAE':<10} {'RMSE':<10} {'R²':<10}")
    print("-" * 55)

    for model_name in ["prophet", "sarima", "xgboost", "ensemble"]:
        result = results.get(model_name, {})
        if "error" in result:
            print(f"{model_name.upper():<15} {'FAILED':<10}")
        else:
            metrics = result.get("metrics", {})
            print(f"{model_name.upper():<15} "
                  f"{metrics.get('mape', 0):.2f}%{'':5} "
                  f"{metrics.get('mae', 0):.2f}{'':5} "
                  f"{metrics.get('rmse', 0):.2f}{'':5} "
                  f"{metrics.get('r2', 0):.4f}")

    # Ensemble analysis
    ensemble = results.get("ensemble", {})
    if "metrics" in ensemble:
        print("\n" + "="*70)
        print("🎯 ENSEMBLE PERFORMANCE")
        print("="*70)
        print(f"Final MAPE: {ensemble['metrics']['mape']:.2f}%")
        print(f"Improvement over best model: {ensemble.get('improvement_over_best', 0):.2f}%")
        print(f"\nModel weights:")
        for model, weight in ensemble.get("weights", {}).items():
            print(f"  - {model.upper()}: {weight*100:.1f}%")

    # Target comparison
    print("\n" + "="*70)
    print("🎯 TARGET COMPARISON")
    print("="*70)

    ensemble_mape = ensemble.get("metrics", {}).get("mape", 999)

    if ensemble_mape <= 15:
        status = "✓ TARGET MET"
        emoji = "🎉"
    elif ensemble_mape <= 20:
        status = "⚠ CLOSE TO TARGET"
        emoji = "⚡"
    else:
        status = "✗ NEEDS IMPROVEMENT"
        emoji = "📈"

    print(f"{emoji} Ensemble MAPE: {ensemble_mape:.2f}%")
    print(f"   Target: 10-15% (Industry excellent)")
    print(f"   Status: {status}")

    print("\n" + "="*70)
    print(f"Test duration: {report.get('duration_seconds', 0):.1f}s")
    print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Backtest ML models on Lexis data")

    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run hyperparameter tuning (slow but better accuracy)"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Save results to JSON file"
    )

    args = parser.parse_args()

    try:
        report = asyncio.run(run_backtest(
            hyperparameter_tuning=args.tune,
            output_file=args.output
        ))

        # Exit code based on success
        if "error" in report:
            sys.exit(1)

        # Check if target met
        ensemble_mape = report.get("results", {}).get("ensemble", {}).get("metrics", {}).get("mape", 999)
        sys.exit(0 if ensemble_mape <= 20 else 1)

    except KeyboardInterrupt:
        logger.info("\nBacktest interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
