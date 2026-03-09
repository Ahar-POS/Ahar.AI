"""
XGBoost Forecaster

Implements BaseForecaster using XGBoost Regressor.

Best for:
- Complex feature interactions
- Non-linear relationships
- External signals (weather, PyTrends, events)
- High-dimensional feature spaces

Advantages:
- Uses ALL engineered features (60+ features)
- Handles non-linear patterns
- Built-in feature importance
- Fast training and prediction

Tier compatibility:
- Tier 3+ (30+ days): Can use XGBoost
- Heavy reliance on external features for Tier 2-3
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Any
import joblib

from xgboost import XGBRegressor
from sklearn.preprocessing import StandardScaler

from app.services.ml.base_forecaster import BaseForecaster

logger = logging.getLogger(__name__)


class XGBoostForecaster(BaseForecaster):
    """
    XGBoost-based forecaster with full feature set

    Features:
    - Uses all engineered features
    - Non-linear modeling
    - Feature importance analysis
    - Handles missing values
    - Regularization
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        min_child_weight: int = 1,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        reg_alpha: float = 0.0,
        reg_lambda: float = 1.0,
        scale_features: bool = True
    ):
        """
        Initialize XGBoost forecaster

        Args:
            n_estimators: Number of boosting rounds
            max_depth: Maximum tree depth
            learning_rate: Learning rate (eta)
            min_child_weight: Minimum sum of instance weight in child
            subsample: Subsample ratio of training instances
            colsample_bytree: Subsample ratio of columns
            reg_alpha: L1 regularization
            reg_lambda: L2 regularization
            scale_features: Whether to scale features
        """
        super().__init__(model_name="xgboost")
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.min_child_weight = min_child_weight
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.reg_alpha = reg_alpha
        self.reg_lambda = reg_lambda
        self.scale_features = scale_features

        self.xgb_model: Optional[XGBRegressor] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: List[str] = []
        self.feature_importance_dict: Dict[str, float] = {}

    def fit(
        self,
        train_data: pd.DataFrame,
        target_column: str = "y",
        date_column: str = "ds",
        exogenous_features: Optional[List[str]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Train XGBoost model

        Args:
            train_data: Training data
            target_column: Target variable column
            date_column: Date column (used for sorting, not as feature)
            exogenous_features: List of feature columns
            hyperparameters: XGBoost hyperparameters

        Returns:
            Training metrics
        """
        # Validate data
        is_valid, error_msg = self.validate_data(train_data, target_column, date_column)
        if not is_valid:
            raise ValueError(f"Invalid training data: {error_msg}")

        # Update hyperparameters if provided
        if hyperparameters:
            for key, value in hyperparameters.items():
                if hasattr(self, key):
                    setattr(self, key, value)

        # Prepare features
        y = train_data[target_column].values

        if exogenous_features:
            # Use provided feature list
            self.feature_names = exogenous_features
        else:
            # Use all columns except target and date
            self.feature_names = [
                col for col in train_data.columns
                if col not in [target_column, date_column, "_id"]
            ]

        # Extract feature matrix
        X = train_data[self.feature_names].copy()

        # Handle missing values (XGBoost can handle NaN, but prefer to fill)
        X = X.fillna(X.mean())

        # Scale features if requested
        if self.scale_features:
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            X = pd.DataFrame(X_scaled, columns=self.feature_names)

        # Initialize XGBoost model
        self.xgb_model = XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            min_child_weight=self.min_child_weight,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            reg_alpha=self.reg_alpha,
            reg_lambda=self.reg_lambda,
            random_state=42,
            n_jobs=-1  # Use all cores
        )

        # Fit model
        logger.info(f"Training XGBoost with {len(self.feature_names)} features")

        self.xgb_model.fit(X, y)

        # Calculate training metrics
        y_pred = self.xgb_model.predict(X)
        metrics = self.calculate_metrics(y, y_pred)

        # Get feature importance
        self.feature_importance_dict = dict(
            zip(self.feature_names, self.xgb_model.feature_importances_)
        )

        # Sort by importance
        self.feature_importance_dict = dict(
            sorted(
                self.feature_importance_dict.items(),
                key=lambda x: x[1],
                reverse=True
            )
        )

        # Store metadata
        self.training_metadata = {
            "data_points": len(train_data),
            "features_count": len(self.feature_names),
            "features_used": self.feature_names,
            "hyperparameters": {
                "n_estimators": self.n_estimators,
                "max_depth": self.max_depth,
                "learning_rate": self.learning_rate,
                "min_child_weight": self.min_child_weight,
                "subsample": self.subsample,
                "colsample_bytree": self.colsample_bytree,
                "reg_alpha": self.reg_alpha,
                "reg_lambda": self.reg_lambda
            },
            "metrics": metrics,
            "top_features": list(self.feature_importance_dict.keys())[:10]
        }

        self.is_fitted = True

        logger.info(
            f"XGBoost trained on {len(train_data)} points with {len(self.feature_names)} features, "
            f"MAPE: {metrics['mape']:.2f}%"
        )

        return metrics

    def predict(
        self,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame] = None,
        return_confidence: bool = True
    ) -> pd.DataFrame:
        """
        Make predictions

        Args:
            horizon: Number of periods to forecast
            exogenous_future: Future feature values (REQUIRED for XGBoost)
            return_confidence: Whether to return confidence intervals

        Returns:
            DataFrame with predictions
        """
        if not self.is_fitted or self.xgb_model is None:
            raise ValueError("Model not fitted. Call fit() first.")

        if exogenous_future is None:
            raise ValueError(
                "XGBoost requires future feature values. "
                "Provide exogenous_future DataFrame with all features."
            )

        # Validate future features
        missing_features = set(self.feature_names) - set(exogenous_future.columns)
        if missing_features:
            raise ValueError(
                f"Missing features in exogenous_future: {missing_features}"
            )

        # Extract features
        X_future = exogenous_future[self.feature_names].copy()
        X_future = X_future.fillna(X_future.mean())

        # Scale if needed
        if self.scale_features and self.scaler is not None:
            X_future_scaled = self.scaler.transform(X_future)
            X_future = pd.DataFrame(X_future_scaled, columns=self.feature_names)

        # Make predictions
        y_pred = self.xgb_model.predict(X_future)

        # Create result dataframe
        if "ds" in exogenous_future.columns:
            forecast_dates = exogenous_future["ds"].values
        else:
            forecast_dates = pd.date_range(
                start=pd.Timestamp.now(),
                periods=horizon,
                freq="D"
            )

        result = pd.DataFrame({
            "ds": forecast_dates,
            "yhat": y_pred
        })

        # XGBoost doesn't provide confidence intervals natively
        # Use simple heuristic: ±15% of prediction
        if return_confidence:
            result["yhat_lower"] = y_pred * 0.85
            result["yhat_upper"] = y_pred * 1.15

        return result

    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """
        Get feature importance scores

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if not self.is_fitted:
            return None

        return self.feature_importance_dict

    def serialize(self, filepath: str) -> bool:
        """
        Save model to disk

        Args:
            filepath: Path to save model (pickle format)

        Returns:
            True if successful
        """
        if not self.is_fitted or self.xgb_model is None:
            logger.error("Cannot serialize unfitted model")
            return False

        try:
            model_data = {
                "xgb_model": self.xgb_model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "feature_importance": self.feature_importance_dict,
                "scale_features": self.scale_features,
                "training_metadata": self.training_metadata
            }

            joblib.dump(model_data, filepath)
            logger.info(f"Saved XGBoost model to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to serialize XGBoost model: {e}")
            return False

    def deserialize(self, filepath: str) -> bool:
        """
        Load model from disk

        Args:
            filepath: Path to load model from

        Returns:
            True if successful
        """
        try:
            model_data = joblib.load(filepath)

            self.xgb_model = model_data["xgb_model"]
            self.scaler = model_data.get("scaler")
            self.feature_names = model_data["feature_names"]
            self.feature_importance_dict = model_data.get("feature_importance", {})
            self.scale_features = model_data.get("scale_features", True)
            self.training_metadata = model_data.get("training_metadata", {})

            self.is_fitted = True

            logger.info(f"Loaded XGBoost model from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to deserialize XGBoost model: {e}")
            return False

    def get_top_features(self, n: int = 10) -> List[tuple]:
        """
        Get top N most important features

        Args:
            n: Number of top features to return

        Returns:
            List of (feature_name, importance_score) tuples
        """
        if not self.feature_importance_dict:
            return []

        return list(self.feature_importance_dict.items())[:n]
