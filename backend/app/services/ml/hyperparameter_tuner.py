"""
Hyperparameter Tuning for Forecasting Models

Uses RandomizedSearchCV with TimeSeriesSplit for cross-validation.
Optimizes hyperparameters to minimize MAPE on validation sets.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Any
from sklearn.model_selection import TimeSeriesSplit
from itertools import product

logger = logging.getLogger(__name__)


class HyperparameterTuner:
    """
    Hyperparameter tuning for time series forecasting models

    Uses:
    - TimeSeriesSplit for temporal cross-validation
    - Random search for efficiency
    - MAPE as optimization metric
    """

    def __init__(
        self,
        n_splits: int = 5,
        n_iter: int = 50,
        random_state: int = 42
    ):
        """
        Initialize hyperparameter tuner

        Args:
            n_splits: Number of cross-validation splits
            n_iter: Number of parameter combinations to try
            random_state: Random seed
        """
        self.n_splits = n_splits
        self.n_iter = n_iter
        self.random_state = random_state
        self.best_params: Dict[str, Any] = {}
        self.best_score: float = float('inf')
        self.cv_results: List[Dict[str, Any]] = []

    def tune_prophet(
        self,
        train_data: pd.DataFrame,
        target_column: str = "y",
        date_column: str = "ds"
    ) -> Dict[str, Any]:
        """
        Tune Prophet hyperparameters

        Args:
            train_data: Training data
            target_column: Target variable column
            date_column: Date column

        Returns:
            Best hyperparameters and tuning results
        """
        logger.info("Starting Prophet hyperparameter tuning...")

        # Parameter grid
        param_grid = {
            "changepoint_prior_scale": [0.001, 0.01, 0.05, 0.1, 0.5],
            "seasonality_prior_scale": [0.01, 0.1, 1.0, 10.0],
            "seasonality_mode": ["additive", "multiplicative"]
        }

        # Random sampling
        param_combinations = self._random_sample_params(param_grid, self.n_iter)

        # TimeSeriesSplit
        tscv = TimeSeriesSplit(n_splits=self.n_splits)

        best_mape = float('inf')
        best_params = None
        results = []

        for i, params in enumerate(param_combinations):
            logger.info(f"Testing combination {i+1}/{len(param_combinations)}: {params}")

            fold_mapes = []

            for fold, (train_idx, val_idx) in enumerate(tscv.split(train_data)):
                try:
                    train_fold = train_data.iloc[train_idx]
                    val_fold = train_data.iloc[val_idx]

                    # Train Prophet with these parameters
                    from app.services.ml.prophet_enhanced import ProphetEnhanced

                    model = ProphetEnhanced(**params)
                    model.fit(train_fold[[date_column, target_column]])

                    # Predict on validation
                    forecast = model.predict(periods=len(val_fold), freq="D")

                    # Calculate MAPE
                    y_true = val_fold[target_column].values
                    y_pred = forecast["yhat"].values[-len(val_fold):]

                    mape = np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-10))) * 100
                    fold_mapes.append(mape)

                except Exception as e:
                    logger.warning(f"Fold {fold} failed: {e}")
                    fold_mapes.append(999.0)  # High penalty

            # Average MAPE across folds
            avg_mape = np.mean(fold_mapes)

            results.append({
                "params": params,
                "mape": avg_mape,
                "std": np.std(fold_mapes)
            })

            if avg_mape < best_mape:
                best_mape = avg_mape
                best_params = params
                logger.info(f"✓ New best MAPE: {best_mape:.2f}%")

        self.best_params = best_params
        self.best_score = best_mape
        self.cv_results = results

        logger.info(f"Tuning complete. Best MAPE: {best_mape:.2f}%")
        logger.info(f"Best params: {best_params}")

        return {
            "best_params": best_params,
            "best_mape": round(best_mape, 2),
            "all_results": results
        }

    def tune_xgboost(
        self,
        train_data: pd.DataFrame,
        target_column: str = "y",
        feature_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Tune XGBoost hyperparameters

        Args:
            train_data: Training data
            target_column: Target variable column
            feature_columns: Feature columns (if None, uses all except target)

        Returns:
            Best hyperparameters and tuning results
        """
        logger.info("Starting XGBoost hyperparameter tuning...")

        # Parameter grid
        param_grid = {
            "n_estimators": [50, 100, 150, 200],
            "max_depth": [3, 4, 5, 6, 7],
            "learning_rate": [0.01, 0.05, 0.1, 0.2],
            "min_child_weight": [1, 3, 5],
            "subsample": [0.7, 0.8, 0.9, 1.0],
            "colsample_bytree": [0.7, 0.8, 0.9, 1.0],
            "reg_alpha": [0, 0.1, 1.0],
            "reg_lambda": [0.1, 1.0, 10.0]
        }

        # Random sampling
        param_combinations = self._random_sample_params(param_grid, self.n_iter)

        # Prepare features
        if feature_columns is None:
            feature_columns = [col for col in train_data.columns if col != target_column]

        X = train_data[feature_columns].fillna(0)
        y = train_data[target_column].values

        # TimeSeriesSplit
        tscv = TimeSeriesSplit(n_splits=self.n_splits)

        best_mape = float('inf')
        best_params = None
        results = []

        for i, params in enumerate(param_combinations):
            logger.info(f"Testing combination {i+1}/{len(param_combinations)}")

            fold_mapes = []

            for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
                try:
                    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                    y_train, y_val = y[train_idx], y[val_idx]

                    # Train XGBoost with these parameters
                    from xgboost import XGBRegressor

                    model = XGBRegressor(**params, random_state=self.random_state)
                    model.fit(X_train, y_train)

                    # Predict on validation
                    y_pred = model.predict(X_val)

                    # Calculate MAPE
                    mape = np.mean(np.abs((y_val - y_pred) / np.maximum(y_val, 1e-10))) * 100
                    fold_mapes.append(mape)

                except Exception as e:
                    logger.warning(f"Fold {fold} failed: {e}")
                    fold_mapes.append(999.0)

            # Average MAPE across folds
            avg_mape = np.mean(fold_mapes)

            results.append({
                "params": params,
                "mape": avg_mape,
                "std": np.std(fold_mapes)
            })

            if avg_mape < best_mape:
                best_mape = avg_mape
                best_params = params
                logger.info(f"✓ New best MAPE: {best_mape:.2f}%")

        self.best_params = best_params
        self.best_score = best_mape
        self.cv_results = results

        logger.info(f"Tuning complete. Best MAPE: {best_mape:.2f}%")
        logger.info(f"Best params: {best_params}")

        return {
            "best_params": best_params,
            "best_mape": round(best_mape, 2),
            "all_results": results
        }

    def _random_sample_params(
        self,
        param_grid: Dict[str, List],
        n_samples: int
    ) -> List[Dict[str, Any]]:
        """
        Randomly sample parameter combinations

        Args:
            param_grid: Parameter grid
            n_samples: Number of samples to generate

        Returns:
            List of parameter combinations
        """
        np.random.seed(self.random_state)

        samples = []
        param_names = list(param_grid.keys())

        for _ in range(n_samples):
            sample = {}
            for param_name in param_names:
                sample[param_name] = np.random.choice(param_grid[param_name])
            samples.append(sample)

        return samples

    def get_tuning_summary(self) -> Dict[str, Any]:
        """Get summary of tuning results"""
        if not self.cv_results:
            return {"status": "not_tuned"}

        # Sort by MAPE
        sorted_results = sorted(self.cv_results, key=lambda x: x["mape"])

        return {
            "best_params": self.best_params,
            "best_mape": round(self.best_score, 2),
            "n_combinations_tested": len(self.cv_results),
            "top_5_results": sorted_results[:5],
            "improvement_over_default": None  # TODO: Calculate if default available
        }
